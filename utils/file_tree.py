"""
utils/file_tree.py
──────────────────
Builds an in-memory tree of TreeNode objects from a repo root path.

Public API
──────────
    build_tree(repo_root: Path) -> TreeNode
        Returns the root TreeNode for the entire repository.

    iter_nodes(node: TreeNode) -> Iterator[TreeNode]
        DFS iterator over every node in the tree (used for search/filter).

    find_node(root: TreeNode, rel_path: str) -> TreeNode | None
        Look up a node by its relative path string.

Design notes
────────────
- NOISE_DIRS (from repo_handler) are pruned at build time, not render time,
  so the resulting tree is clean and renderer-agnostic.
- Directories are sorted: dirs first, then files, both alphabetically
  (case-insensitive). This matches the convention used by VS Code / GitHub.
- The tree is built once and stored in st.session_state.file_tree so
  Streamlit reruns don't rebuild it on every interaction.
- TreeNode is a plain dataclass — no Streamlit imports here. The renderer
  lives entirely in explorer_tab.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from utils.repo_handler import NOISE_DIRS

# Maximum number of nodes (files + dirs) the builder will include.
# Prevents the UI from becoming unusable on massive repos.
MAX_NODES = 2_000


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TreeNode:
    """
    One node in the repository file tree — either a file or a directory.

    Attributes:
        name:       The file or directory name (not a full path).
        rel_path:   Path relative to the repo root, as a forward-slash string.
                    e.g. "src/utils/helpers.py"
                    Root node has rel_path == "".
        is_dir:     True for directories, False for files.
        children:   Ordered list of child nodes (empty for files).
        depth:      Nesting depth (0 = repo root children).
    """
    name:     str
    rel_path: str          # forward-slash relative path, "" for root
    is_dir:   bool
    depth:    int = 0
    children: list["TreeNode"] = field(default_factory=list)

    # ── Convenience properties ──────────────────────────────────────────────

    @property
    def is_file(self) -> bool:
        return not self.is_dir

    @property
    def extension(self) -> str:
        """Lowercase extension without dot, e.g. 'py'. Empty string if none."""
        return Path(self.name).suffix.lstrip(".").lower()

    @property
    def display_name(self) -> str:
        """Name with a trailing '/' for directories to match conventional style."""
        return f"{self.name}/" if self.is_dir else self.name

    def __repr__(self) -> str:
        kind = "dir" if self.is_dir else "file"
        return f"TreeNode({kind}, {self.rel_path!r})"


# ─────────────────────────────────────────────────────────────────────────────
# TREE BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_tree(repo_root: Path) -> tuple[TreeNode, int]:
    """
    Recursively build a TreeNode tree for the given repo root.

    Skips:
      - Symlinks (to avoid cycles)
      - Directories listed in NOISE_DIRS (.git, node_modules, etc.)
      - Everything beyond MAX_NODES total nodes

    Sort order within every directory:
      - Directories first, then files
      - Alphabetical, case-insensitive, within each group

    Args:
        repo_root: Absolute Path to the repo root directory.

    Returns:
        (root_node, total_node_count) tuple.
        root_node.children contains the top-level entries.
        total_node_count lets callers show a "tree truncated" warning.
    """
    counter = [0]   # mutable so the recursive helper can mutate it

    root = TreeNode(
        name=repo_root.name or str(repo_root),
        rel_path="",
        is_dir=True,
        depth=0,
    )

    _build_children(
        directory=repo_root,
        parent_node=root,
        repo_root=repo_root,
        depth=1,
        counter=counter,
    )

    return root, counter[0]


def _build_children(
    directory: Path,
    parent_node: TreeNode,
    repo_root: Path,
    depth: int,
    counter: list[int],
) -> None:
    """
    Populate parent_node.children from the contents of *directory*.

    Mutates parent_node.children and counter[0] in place.
    Returns early (without error) if MAX_NODES is reached.
    """
    if counter[0] >= MAX_NODES:
        return

    try:
        entries = list(directory.iterdir())
    except PermissionError:
        return

    # ── Sort: dirs first, then files; each group alphabetical (case-insensitive)
    dirs  = sorted(
        [e for e in entries if e.is_dir() and not e.is_symlink()],
        key=lambda e: e.name.lower(),
    )
    files = sorted(
        [e for e in entries if e.is_file() and not e.is_symlink()],
        key=lambda e: e.name.lower(),
    )

    for entry in dirs + files:
        if counter[0] >= MAX_NODES:
            break

        # Skip noise directories at build time
        if entry.is_dir() and entry.name in NOISE_DIRS:
            continue

        rel_path = entry.relative_to(repo_root).as_posix()
        node = TreeNode(
            name=entry.name,
            rel_path=rel_path,
            is_dir=entry.is_dir(),
            depth=depth,
        )
        parent_node.children.append(node)
        counter[0] += 1

        if entry.is_dir():
            _build_children(
                directory=entry,
                parent_node=node,
                repo_root=repo_root,
                depth=depth + 1,
                counter=counter,
            )


# ─────────────────────────────────────────────────────────────────────────────
# TREE UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def iter_nodes(node: TreeNode, include_dirs: bool = True) -> Iterator[TreeNode]:
    """
    Depth-first iterator over all nodes in the tree rooted at *node*.

    Args:
        node:         Root node to start from (not itself yielded).
        include_dirs: If False, only file nodes are yielded.

    Yields:
        TreeNode in DFS pre-order.
    """
    for child in node.children:
        if include_dirs or child.is_file:
            yield child
        if child.is_dir:
            yield from iter_nodes(child, include_dirs=include_dirs)


def find_node(root: TreeNode, rel_path: str) -> TreeNode | None:
    """
    Find a node by its rel_path string. Returns None if not found.

    Args:
        root:     The root TreeNode returned by build_tree.
        rel_path: Forward-slash relative path, e.g. "src/utils/helpers.py".

    Returns:
        Matching TreeNode or None.
    """
    for node in iter_nodes(root, include_dirs=True):
        if node.rel_path == rel_path:
            return node
    return None


def search_nodes(root: TreeNode, query: str) -> list[TreeNode]:
    """
    Return all file nodes whose name contains *query* (case-insensitive).

    Only searches file nodes, not directory nodes, to keep results clean.

    Args:
        root:  The root TreeNode.
        query: Search string (partial filename match).

    Returns:
        List of matching file TreeNodes, in DFS order.
    """
    query_lower = query.strip().lower()
    if not query_lower:
        return []
    return [
        node for node in iter_nodes(root, include_dirs=False)
        if query_lower in node.name.lower()
    ]


def count_tree(root: TreeNode) -> tuple[int, int]:
    """
    Count files and directories in the tree (excluding the root node itself).

    Returns:
        (file_count, dir_count) tuple.
    """
    files = sum(1 for n in iter_nodes(root, include_dirs=False))
    dirs  = sum(1 for n in iter_nodes(root, include_dirs=True) if n.is_dir)
    return files, dirs
