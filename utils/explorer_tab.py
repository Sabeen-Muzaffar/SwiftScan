"""
utils/explorer_tab.py
─────────────────────
Renders the "🗂️ Explorer" dashboard tab — polished UI version.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from utils.file_tree import TreeNode, count_tree, search_nodes

_EXT_ICONS: dict[str, str] = {
    "py": "🐍", "pyi": "🐍", "pyw": "🐍",
    "js": "🟨", "mjs": "🟨", "cjs": "🟨", "jsx": "⚛️",
    "ts": "🔷", "tsx": "⚛️",
    "html": "🌐", "htm": "🌐",
    "css": "🎨", "scss": "🎨", "sass": "🎨", "less": "🎨",
    "json": "📋", "jsonc": "📋",
    "yaml": "📄", "yml": "📄", "toml": "📄", "xml": "📄",
    "csv": "📊", "sql": "🗄️",
    "md": "📝", "mdx": "📝", "rst": "📝", "txt": "📄", "pdf": "📕",
    "png": "🖼️", "jpg": "🖼️", "jpeg": "🖼️",
    "gif": "🖼️", "svg": "🖼️", "ico": "🖼️", "webp": "🖼️",
    "sh": "⚙️", "bash": "⚙️", "zsh": "⚙️", "ps1": "⚙️",
    "tf": "🏗️", "tfvars": "🏗️",
    "pyc": "⚙️", "pyd": "⚙️",
    "class": "☕", "jar": "☕",
    "exe": "⚙️", "dll": "⚙️", "so": "⚙️",
    "zip": "📦", "tar": "📦", "gz": "📦", "bz2": "📦",
    "ipynb": "📓",
    "rs": "🦀", "go": "🐹",
    "c": "⚙️", "h": "⚙️", "cpp": "⚙️", "hpp": "⚙️",
    "cs": "🔷", "java": "☕", "kt": "🟣",
    "swift": "🧡", "rb": "💎", "php": "🐘", "lua": "🌙", "r": "📊",
}

_FALLBACK_FILE_ICON = "📄"
_DIR_ICON_OPEN      = "📂"
_DIR_ICON_CLOSED    = "📁"


def _file_icon(node: TreeNode) -> str:
    name_lower = node.name.lower()
    if name_lower == "dockerfile":
        return "🐳"
    if name_lower in ("makefile", "rakefile", "gemfile"):
        return "⚙️"
    return _EXT_ICONS.get(node.extension, _FALLBACK_FILE_ICON)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_tree_state() -> None:
    if "tree_open_dirs" not in st.session_state:
        st.session_state.tree_open_dirs = set()
    if "selected_file" not in st.session_state:
        st.session_state.selected_file = None
    if "tree_search_query" not in st.session_state:
        st.session_state.tree_search_query = ""


def _select_file(rel_path: str) -> None:
    st.session_state.selected_file = rel_path


def _expand_all(root: TreeNode) -> None:
    from utils.file_tree import iter_nodes
    st.session_state.tree_open_dirs = {
        n.rel_path for n in iter_nodes(root, include_dirs=True) if n.is_dir
    }


def _collapse_all() -> None:
    st.session_state.tree_open_dirs = set()


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def render_explorer_tab(root: TreeNode, repo_root: Path, truncated: bool = False) -> None:
    _ensure_tree_state()

    file_count, dir_count = count_tree(root)

    # Header
    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#111827,#1F2937);
        border:1px solid #1F2937; border-left:3px solid #00B4C8;
        border-radius:12px; padding:1rem 1.2rem; margin-bottom:1rem;
        display:flex; align-items:center; justify-content:space-between;
    ">
        <div>
            <div style="font-size:1.1rem; font-weight:700; color:#E2E8F0;">
                🗂️ File Explorer
            </div>
            <div style="font-size:0.75rem; color:#64748B; margin-top:2px;">
                {file_count:,} files · {dir_count:,} folders
                {"· ⚠️ tree capped (very large repo)" if truncated else ""}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Controls row
    col_search, col_exp, col_col = st.columns([4, 1, 1])
    with col_search:
        st.markdown('<p style="font-size:0.72rem; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:4px;">Search files</p>', unsafe_allow_html=True)
        query = st.text_input(
            label="search",
            value=st.session_state.tree_search_query,
            placeholder="Type a filename to filter…",
            label_visibility="collapsed",
            key="tree_search_input",
        )
        st.session_state.tree_search_query = query

    with col_exp:
        st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
        if st.button("⬇️ All", use_container_width=True, key="tree_expand_all",
                     help="Expand all folders"):
            _expand_all(root)
            st.rerun()

    with col_col:
        st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
        if st.button("⬆️ All", use_container_width=True, key="tree_collapse_all",
                     help="Collapse all folders"):
            _collapse_all()
            st.rerun()

    st.markdown("<div style='margin:0.5rem 0'></div>", unsafe_allow_html=True)

    # Two-column layout
    col_tree, col_info = st.columns([3, 2], gap="medium")

    with col_tree:
        if query.strip():
            _render_search_results(root, query)
        else:
            _render_tree_children(root)

    with col_info:
        _render_file_info_panel(repo_root)


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH RESULTS
# ─────────────────────────────────────────────────────────────────────────────

def _render_search_results(root: TreeNode, query: str) -> None:
    matches = search_nodes(root, query)

    if not matches:
        st.markdown(f"""
        <div style="
            background:#111827; border:1px dashed #374151;
            border-radius:10px; padding:1.5rem; text-align:center; color:#64748B;
        ">
            <div style="font-size:1.5rem; margin-bottom:0.4rem;">🔍</div>
            <div style="font-size:0.85rem;">No files match <strong style="color:#00B4C8">{query}</strong></div>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f"""
    <div style="font-size:0.75rem; color:#00B4C8; font-weight:600;
        text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.5rem;">
        {len(matches)} result{"s" if len(matches) != 1 else ""} for "{query}"
    </div>
    """, unsafe_allow_html=True)

    for node in matches:
        icon = _file_icon(node)
        is_selected = st.session_state.selected_file == node.rel_path
        btn_type = "primary" if is_selected else "secondary"
        if st.button(
            f"{icon} {node.rel_path}",
            key=f"search_{node.rel_path}",
            type=btn_type,
            use_container_width=True,
        ):
            _select_file(node.rel_path)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# TREE RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def _render_tree_children(parent: TreeNode) -> None:
    for node in parent.children:
        if node.is_dir:
            _render_dir_node(node)
        else:
            _render_file_node(node)


def _render_dir_node(node: TreeNode) -> None:
    is_open = node.rel_path in st.session_state.tree_open_dirs
    icon = _DIR_ICON_OPEN if is_open else _DIR_ICON_CLOSED

    with st.expander(f"{icon} **{node.name}/**", expanded=is_open):
        st.session_state.tree_open_dirs.add(node.rel_path)
        if not node.children:
            st.caption("*(empty directory)*")
        else:
            _render_tree_children(node)


def _render_file_node(node: TreeNode) -> None:
    icon = _file_icon(node)
    is_selected = st.session_state.selected_file == node.rel_path
    indent = "　" * max(0, node.depth - 1)
    label = f"{indent}{icon} {node.name}"
    btn_type = "primary" if is_selected else "secondary"

    if st.button(
        label,
        key=f"file_{node.rel_path}",
        type=btn_type,
        use_container_width=True,
        help=node.rel_path,
    ):
        _select_file(node.rel_path)
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# FILE INFO PANEL
# ─────────────────────────────────────────────────────────────────────────────

def _render_file_info_panel(repo_root: Path) -> None:
    selected = st.session_state.selected_file

    if not selected:
        st.markdown("""
        <div style="
            background:linear-gradient(135deg,#111827,#1F2937);
            border:1px dashed #374151; border-radius:12px;
            padding:2.5rem 1.5rem; text-align:center; color:#475569;
        ">
            <div style="font-size:2.5rem; margin-bottom:0.8rem;">📄</div>
            <div style="font-size:0.85rem; color:#64748B; line-height:1.5;">
                Click any file in the tree<br>to see its details here
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    file_path = repo_root / selected
    if not file_path.exists():
        st.warning(f"File not found: `{selected}`")
        return

    from utils.language_detector import detect_language, _count_lines
    language   = detect_language(file_path)
    line_count = _count_lines(file_path)

    try:
        byte_size = file_path.stat().st_size
    except OSError:
        byte_size = 0

    if byte_size >= 1024 * 1024:
        size_str = f"{byte_size / (1024*1024):.2f} MB"
    elif byte_size >= 1024:
        size_str = f"{byte_size / 1024:.1f} KB"
    else:
        size_str = f"{byte_size} B"

    icon = _file_icon(TreeNode(name=file_path.name, rel_path=selected, is_dir=False))

    # File card
    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#111827,#1F2937);
        border:1px solid #1F2937; border-top:3px solid #00B4C8;
        border-radius:12px; padding:1.2rem;
        margin-bottom:1rem;
    ">
        <div style="font-size:2rem; margin-bottom:0.5rem;">{icon}</div>
        <div style="font-weight:700; font-size:0.95rem; color:#E2E8F0;
            word-break:break-all; margin-bottom:4px;">{file_path.name}</div>
        <div style="font-size:0.72rem; color:#64748B; word-break:break-all;
            font-family:'JetBrains Mono',monospace;">{selected}</div>
    </div>
    """, unsafe_allow_html=True)

    # Metrics
    m1, m2 = st.columns(2)
    with m1:
        st.metric("Language", language)
        st.metric("Size", size_str)
    with m2:
        st.metric("Lines", f"{line_count:,}" if line_count else "—")
        st.metric("Extension", f".{file_path.suffix.lstrip('.')}" if file_path.suffix else "none")

    st.markdown("<div style='margin:0.5rem 0'></div>", unsafe_allow_html=True)

    # Tip
    st.markdown(f"""
    <div style="
        background:#0D1F2D; border:1px solid #164E63;
        border-radius:10px; padding:10px 14px;
        font-size:0.78rem; color:#67E8F9; line-height:1.5;
    ">
        💡 Go to <strong>💻 Code Viewer</strong> tab to view
        <strong>{file_path.name}</strong> with AI explanations.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin:0.5rem 0'></div>", unsafe_allow_html=True)

    # Quick preview
    _render_file_preview(file_path)


def _render_file_preview(file_path: Path) -> None:
    MAX_PREVIEW_BYTES = 8_000
    MAX_PREVIEW_LINES = 20

    try:
        raw = file_path.read_bytes()[:MAX_PREVIEW_BYTES]
        sample = raw[:512]
        if sample:
            non_printable = sum(1 for b in sample if b < 9 or (14 <= b < 32))
            if non_printable / len(sample) > 0.15:
                return
        text  = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()[:MAX_PREVIEW_LINES]
        preview = "\n".join(lines)
        if len(text.splitlines()) > MAX_PREVIEW_LINES:
            preview += f"\n... ({len(text.splitlines()) - MAX_PREVIEW_LINES} more lines)"
    except Exception:
        return

    with st.expander("👁️ Quick Preview", expanded=False):
        ext = file_path.suffix.lstrip(".").lower()
        lang_hint = ext if ext in {
            "py","js","ts","jsx","tsx","html","css","json","yaml","yml",
            "toml","md","sh","sql","rs","go","java","cpp","c","rb","php",
        } else ""
        st.code(preview, language=lang_hint or None)