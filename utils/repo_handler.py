"""
utils/repo_handler.py
─────────────────────
Handles loading a codebase into a temporary directory from either:

  - A public GitHub URL  → shallow git clone (depth=1)
  - A .zip file upload   → extract + unwrap single top-level folder

Both public entry points return a Path to the repo root.
Temp-dir lifecycle (create / cleanup) is managed by the caller (app.py).

Security note:
  extract_zip() validates every zip member path to prevent directory-
  traversal attacks (e.g. members named "../../etc/passwd").
"""

import re
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath

from git import GitCommandError, InvalidGitRepositoryError, Repo

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Directories to ignore when walking the repo (applied by count_files and
# future file-tree / language-detector modules that import this set).
NOISE_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__",
    ".venv", "venv", "env", ".env",
    "dist", "build", ".next", ".nuxt",
    "target",       # Rust / Maven build output
    ".gradle", ".idea", ".vscode",
})

# Maximum uncompressed size we'll accept from a zip upload (500 MB).
# Prevents zip-bomb attacks that decompress to enormous sizes.
_MAX_ZIP_UNCOMPRESSED_BYTES: int = 500 * 1024 * 1024


# ─────────────────────────────────────────────────────────────────────────────
# URL VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

# Matches: https://github.com/owner/repo  (with optional .git suffix / trailing slash)
_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


def validate_github_url(url: str) -> str:
    """
    Validate and normalise a GitHub HTTPS URL.

    Strips a trailing '.git' suffix and trailing slash so GitPython
    always receives a canonical URL.

    Args:
        url: Raw string from the Streamlit text input.

    Returns:
        Normalised URL string, e.g. "https://github.com/owner/repo"

    Raises:
        ValueError: With a human-readable message if the URL is invalid.
    """
    url = url.strip()
    if not url:
        raise ValueError("Please enter a GitHub URL.")

    match = _GITHUB_URL_RE.match(url)
    if not match:
        raise ValueError(
            "Invalid GitHub URL. Expected format:\n"
            "  https://github.com/owner/repo\n\n"
            f"Got: {url}"
        )

    owner = match.group("owner")
    repo  = match.group("repo")
    return f"https://github.com/{owner}/{repo}"


# ─────────────────────────────────────────────────────────────────────────────
# GITHUB CLONE
# ─────────────────────────────────────────────────────────────────────────────

def clone_github_repo(github_url: str, target_dir: str) -> Path:
    """
    Shallow-clone a public GitHub repository into *target_dir*.

    Uses depth=1 so only the latest commit is fetched — keeps clone times
    fast even for large repos (no full history needed for static analysis).

    Args:
        github_url: Full HTTPS URL, e.g. "https://github.com/owner/repo".
                    May include a trailing '.git'; it will be stripped.
        target_dir: Absolute path to an *existing* empty temp directory.

    Returns:
        Path to the cloned repo root (a subdirectory of target_dir named
        after the repository, e.g. /tmp/swiftscan_xyz/repo).

    Raises:
        ValueError:   If the URL format is invalid (see validate_github_url).
        RuntimeError: If the clone fails — wraps GitCommandError with a
                      plain-English message (private repo, bad URL, no network).
    """
    canonical_url = validate_github_url(github_url)

    # Derive the repo name from the URL to use as the clone destination folder.
    # e.g. "https://github.com/psf/requests" → "requests"
    repo_name  = canonical_url.rstrip("/").split("/")[-1]
    clone_dest = Path(target_dir) / repo_name

    try:
        Repo.clone_from(
            url=canonical_url,
            to_path=str(clone_dest),
            depth=1,             # shallow clone — latest snapshot only
            single_branch=True,  # skip fetching all remote branches
        )
    except GitCommandError as exc:
        stderr = (exc.stderr or "").strip()
        _raise_clone_error(canonical_url, stderr)
    except InvalidGitRepositoryError as exc:
        raise RuntimeError(
            f"The cloned directory does not appear to be a valid git repo: {exc}"
        ) from exc

    return clone_dest


def _raise_clone_error(url: str, stderr: str) -> None:
    """
    Convert a raw git error string into a user-friendly RuntimeError.

    Extracted as a helper so clone_github_repo stays readable.
    Never returns — always raises.
    """
    lower = stderr.lower()

    if "repository not found" in lower or "not found" in lower:
        raise RuntimeError(
            f"Repository not found: {url}\n"
            "Make sure the URL is correct and the repository is public."
        )
    if "authentication failed" in lower or "could not read" in lower:
        raise RuntimeError(
            f"Authentication required for: {url}\n"
            "SwiftScan only supports public repositories."
        )
    if "unable to connect" in lower or "could not resolve" in lower:
        raise RuntimeError(
            "Network error — could not reach GitHub.\n"
            "Check your internet connection and try again."
        )

    # Fallback: surface the raw git error so the user has something to act on.
    raise RuntimeError(
        f"Git clone failed for {url}\n\nDetails: {stderr or 'No details available.'}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# ZIP EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_zip(zip_bytes: bytes, target_dir: str) -> Path:
    """
    Extract a zip archive (provided as raw bytes) into *target_dir*.

    Handles the common "single top-level folder" pattern produced by:
      - GitHub's "Download ZIP" button  (produces  repo-main/)
      - Most OS zip utilities on macOS / Windows

    If the archive contains exactly one top-level directory and nothing
    else at the root level, that directory is returned as the repo root.

    Security:
      - Validates every member path against directory-traversal sequences.
      - Enforces a 500 MB uncompressed size cap to guard against zip bombs.

    Args:
        zip_bytes: Raw bytes from Streamlit's UploadedFile.read().
        target_dir: Absolute path to an *existing* temp directory.

    Returns:
        Path to the repo root (unwrapped if single top-level dir present).

    Raises:
        ValueError:         If zip_bytes is empty.
        zipfile.BadZipFile: If the bytes are not a valid zip archive.
        ValueError:         If a path-traversal or zip-bomb is detected.
    """
    if not zip_bytes:
        raise ValueError("The uploaded file is empty.")

    target = Path(target_dir)

    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        _validate_zip_members(zf)
        zf.extractall(target)

    return _unwrap_single_dir(target)


def _validate_zip_members(zf: zipfile.ZipFile) -> None:
    """
    Raise ValueError if any member path is unsafe or total size is too large.

    Checks:
      1. Absolute paths  (e.g. "/etc/passwd")
      2. Path traversal  (e.g. "../../evil")
      3. Zip bomb guard  (total uncompressed bytes > 500 MB)
    """
    total_uncompressed = 0

    for member in zf.infolist():
        member_path = PurePosixPath(member.filename)

        if member_path.is_absolute():
            raise ValueError(
                f"Unsafe zip entry (absolute path): {member.filename}"
            )
        if ".." in member_path.parts:
            raise ValueError(
                f"Unsafe zip entry (path traversal): {member.filename}"
            )

        total_uncompressed += member.file_size
        if total_uncompressed > _MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ValueError(
                f"Zip archive exceeds the 500 MB uncompressed size limit "
                f"({total_uncompressed / 1024 / 1024:.1f} MB so far). "
                "Please upload a smaller archive."
            )


def _unwrap_single_dir(target: Path) -> Path:
    """
    Return the single child directory of *target* if it is the only entry.

    Unwraps the common GitHub download pattern:
        upload.zip
        └── my-project-main/    ← only child
            ├── README.md
            └── src/

    Returns target unchanged when there are multiple entries or the
    single entry is a file.
    """
    children = list(target.iterdir())
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return target


# ─────────────────────────────────────────────────────────────────────────────
# FILE COUNTING  (shared utility — also imported by future modules)
# ─────────────────────────────────────────────────────────────────────────────

def count_files(repo_root: Path) -> int:
    """
    Recursively count all *files* under repo_root, skipping NOISE_DIRS.

    Prunes at the *directory* level — we skip entering a noise directory
    entirely rather than testing every file path component, which avoids
    false positives (e.g. a file literally named '.git') and is faster.

    Args:
        repo_root: Path returned by clone_github_repo or extract_zip.

    Returns:
        Integer file count (0 if repo_root is empty or non-existent).
    """
    if not repo_root or not repo_root.exists():
        return 0

    total_ref: list[int] = [0]
    _walk_and_count(repo_root, total_ref)
    return total_ref[0]


def _walk_and_count(directory: Path, total_ref: list[int]) -> None:
    """
    Recursive DFS helper for count_files.

    Uses a mutable list as a reference to accumulate the count without
    building an intermediate list of all file paths in memory.
    """
    try:
        entries = list(directory.iterdir())
    except PermissionError:
        return  # Skip unreadable directories gracefully

    for entry in entries:
        if entry.is_symlink():
            continue  # Avoid cycles and out-of-tree paths
        if entry.is_dir():
            if entry.name not in NOISE_DIRS:
                _walk_and_count(entry, total_ref)
        elif entry.is_file():
            total_ref[0] += 1
