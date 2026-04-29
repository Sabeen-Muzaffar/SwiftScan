"""
utils/language_detector.py
──────────────────────────
Single-pass repository scanner that collects:

  - Language breakdown  (file count + byte size per language)
  - Tech stack items    (frameworks/tools detected from config files)
  - Repo-level stats    (total files, total lines, total bytes, top files)

Public API
──────────
    scan_repo(repo_root: Path) -> RepoScan

Everything else in this module is an implementation detail.

Design note — single pass:
  We walk the directory tree exactly once (in scan_repo) and feed each
  file path into all collectors simultaneously.  Language detection,
  stats accumulation, and config-file detection all happen in the same
  loop, so there is no redundant I/O regardless of how many tabs end up
  consuming this data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from utils.repo_handler import NOISE_DIRS

# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LanguageStat:
    """Aggregated metrics for one language."""
    name: str
    file_count: int = 0
    byte_size: int = 0   # total uncompressed bytes across all files

    @property
    def kb(self) -> float:
        return self.byte_size / 1024

    @property
    def mb(self) -> float:
        return self.byte_size / (1024 * 1024)


@dataclass
class StackItem:
    """One detected framework, tool, or dependency manager."""
    name: str               # Display name, e.g. "React", "FastAPI"
    category: str           # "framework" | "tool" | "language-runtime" | "devops"
    source_file: str        # Which config file revealed this, e.g. "package.json"
    version: str = ""       # Version string if parseable, else ""


@dataclass
class FileInfo:
    """Lightweight metadata for a single file (used for top-files list)."""
    path: Path
    byte_size: int
    language: str

    @property
    def relative_str(self) -> str:
        """Return the path as stored — caller provides relative paths."""
        return str(self.path)


@dataclass
class RepoScan:
    """
    Complete result of a single scan_repo() call.

    All downstream UI components (Overview tab, Explorer tab, etc.) read
    from this dataclass — they never re-walk the filesystem themselves.
    """
    # Language breakdown — sorted by byte_size descending
    languages: list[LanguageStat] = field(default_factory=list)

    # Detected tech stack items — deduplicated by (name, category)
    stack: list[StackItem] = field(default_factory=list)

    # Aggregate counters
    total_files: int = 0
    total_bytes: int = 0
    total_lines: int = 0     # best-effort; binary files contribute 0

    # Top 10 largest files (sorted by byte_size descending)
    top_files: list[FileInfo] = field(default_factory=list)

    # Repo root stored for reference by other modules
    repo_root: Path | None = None

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def dominant_language(self) -> str:
        """Name of the language with the most bytes, or 'Unknown'."""
        if not self.languages:
            return "Unknown"
        return self.languages[0].name  # already sorted desc

    @property
    def total_kb(self) -> float:
        return self.total_bytes / 1024

    @property
    def total_mb(self) -> float:
        return self.total_bytes / (1024 * 1024)


# ─────────────────────────────────────────────────────────────────────────────
# EXTENSION → LANGUAGE MAP
# ─────────────────────────────────────────────────────────────────────────────
# Keys: lowercase file extension WITHOUT the leading dot.
# Values: canonical language display name.
#
# Ordering within the dict is irrelevant — lookups are O(1).

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    # Python
    "py": "Python", "pyi": "Python", "pyw": "Python",
    # JavaScript / TypeScript
    "js": "JavaScript", "mjs": "JavaScript", "cjs": "JavaScript",
    "jsx": "JavaScript",
    "ts": "TypeScript", "tsx": "TypeScript", "mts": "TypeScript",
    # Web
    "html": "HTML", "htm": "HTML",
    "css": "CSS", "scss": "CSS", "sass": "CSS", "less": "CSS",
    # Data / Config (not counted as "code" but worth knowing about)
    "json": "JSON", "jsonc": "JSON",
    "yaml": "YAML", "yml": "YAML",
    "toml": "TOML",
    "xml": "XML",
    "csv": "CSV",
    "sql": "SQL",
    # Systems languages
    "c": "C", "h": "C",
    "cpp": "C++", "cc": "C++", "cxx": "C++", "hpp": "C++", "hxx": "C++",
    "cs": "C#",
    "rs": "Rust",
    "go": "Go",
    "java": "Java",
    "kt": "Kotlin", "kts": "Kotlin",
    "swift": "Swift",
    # JVM / functional
    "scala": "Scala",
    "groovy": "Groovy",
    "clj": "Clojure", "cljs": "Clojure", "cljc": "Clojure",
    # Scripting
    "rb": "Ruby",
    "php": "PHP",
    "lua": "Lua",
    "pl": "Perl", "pm": "Perl",
    "r": "R", "rmd": "R",
    "m": "MATLAB",
    "ex": "Elixir", "exs": "Elixir",
    "erl": "Erlang", "hrl": "Erlang",
    # Shell
    "sh": "Shell", "bash": "Shell", "zsh": "Shell", "fish": "Shell",
    "ps1": "PowerShell", "psm1": "PowerShell",
    "bat": "Batch", "cmd": "Batch",
    # ML / data science
    "ipynb": "Jupyter Notebook",
    # Infrastructure / config
    "tf": "Terraform", "tfvars": "Terraform",
    "dockerfile": "Dockerfile",   # handled specially for extensionless files too
    "hcl": "HCL",
    # Docs
    "md": "Markdown", "mdx": "Markdown",
    "rst": "reStructuredText",
    "tex": "LaTeX",
    # Other
    "dart": "Dart",
    "vue": "Vue",
    "svelte": "Svelte",
    "graphql": "GraphQL", "gql": "GraphQL",
    "proto": "Protobuf",
    "asm": "Assembly", "s": "Assembly",
}

# Files whose name (not extension) identifies them as a known type.
# Checked as lowercase(filename) → language.
FILENAME_TO_LANGUAGE: dict[str, str] = {
    "dockerfile": "Dockerfile",
    "makefile": "Makefile",
    "gemfile": "Ruby",
    "gemfile.lock": "Ruby",
    "rakefile": "Ruby",
    "vagrantfile": "Ruby",
    "jenkinsfile": "Groovy",
    "procfile": "Config",
    ".env": "Config",
    ".env.example": "Config",
    ".editorconfig": "Config",
    ".gitignore": "Config",
    ".gitattributes": "Config",
    ".dockerignore": "Config",
}

# Languages considered "code" for the Lines of Code metric.
# Data / config formats are excluded to keep LoC meaningful.
_CODE_LANGUAGES: frozenset[str] = frozenset({
    "Python", "JavaScript", "TypeScript", "Java", "C", "C++", "C#",
    "Rust", "Go", "Ruby", "PHP", "Kotlin", "Swift", "Scala", "Dart",
    "Vue", "Svelte", "Elixir", "Erlang", "Clojure", "Lua", "Perl",
    "R", "Shell", "PowerShell", "Batch", "Groovy", "MATLAB",
    "Makefile", "Dockerfile", "SQL", "GraphQL", "Protobuf", "Assembly",
})


def detect_language(path: Path) -> str:
    """
    Return the display-name language for a single file path.

    Resolution order:
      1. Exact filename match (case-insensitive) in FILENAME_TO_LANGUAGE
      2. File extension (lowercase, without dot) in EXTENSION_TO_LANGUAGE
      3. "Other"

    Args:
        path: Any Path object; only the filename/suffix is examined.

    Returns:
        Language display name string, e.g. "Python", "Dockerfile", "Other".
    """
    name_lower = path.name.lower()

    if name_lower in FILENAME_TO_LANGUAGE:
        return FILENAME_TO_LANGUAGE[name_lower]

    suffix = path.suffix.lstrip(".").lower()
    if suffix:
        return EXTENSION_TO_LANGUAGE.get(suffix, "Other")

    return "Other"


# ─────────────────────────────────────────────────────────────────────────────
# TECH STACK DETECTION
# ─────────────────────────────────────────────────────────────────────────────

# Each entry:  config_filename → list of (display_name, category, regex_pattern)
# The regex is applied to the raw text of the config file.
# A match → that StackItem is added to the results.
#
# We use simple regex rather than full parsing (e.g. JSON.loads) to stay
# robust against malformed files and to keep dependencies minimal.

_STACK_RULES: dict[str, list[tuple[str, str, str]]] = {
    # ── Python ────────────────────────────────────────────────────────────────
    "requirements.txt": [
        ("FastAPI",     "framework",       r"(?im)^fastapi"),
        ("Flask",       "framework",       r"(?im)^flask"),
        ("Django",      "framework",       r"(?im)^django"),
        ("SQLAlchemy",  "framework",       r"(?im)^sqlalchemy"),
        ("Pydantic",    "framework",       r"(?im)^pydantic"),
        ("Celery",      "framework",       r"(?im)^celery"),
        ("NumPy",       "framework",       r"(?im)^numpy"),
        ("Pandas",      "framework",       r"(?im)^pandas"),
        ("Scikit-learn","framework",       r"(?im)^scikit.learn"),
        ("TensorFlow",  "framework",       r"(?im)^tensorflow"),
        ("PyTorch",     "framework",       r"(?im)^torch"),
        ("Streamlit",   "framework",       r"(?im)^streamlit"),
        ("Pytest",      "tool",            r"(?im)^pytest"),
        ("Uvicorn",     "tool",            r"(?im)^uvicorn"),
        ("Gunicorn",    "tool",            r"(?im)^gunicorn"),
    ],
    "pyproject.toml": [
        ("FastAPI",     "framework",       r"(?i)fastapi"),
        ("Flask",       "framework",       r"(?i)flask"),
        ("Django",      "framework",       r"(?i)django"),
        ("SQLAlchemy",  "framework",       r"(?i)sqlalchemy"),
        ("NumPy",       "framework",       r"(?i)numpy"),
        ("Pandas",      "framework",       r"(?i)pandas"),
        ("TensorFlow",  "framework",       r"(?i)tensorflow"),
        ("PyTorch",     "framework",       r"(?i)\btorch\b"),
        ("Streamlit",   "framework",       r"(?i)streamlit"),
        ("Poetry",      "tool",            r'(?i)\[tool\.poetry\]'),
        ("Hatch",       "tool",            r'(?i)\[tool\.hatch\]'),
    ],
    "setup.py": [
        ("Setuptools",  "tool",            r"(?i)setuptools"),
    ],
    # ── JavaScript / Node ────────────────────────────────────────────────────
    "package.json": [
        ("React",       "framework",       r'"react"\s*:'),
        ("Vue",         "framework",       r'"vue"\s*:'),
        ("Angular",     "framework",       r'"@angular/core"\s*:'),
        ("Svelte",      "framework",       r'"svelte"\s*:'),
        ("Next.js",     "framework",       r'"next"\s*:'),
        ("Nuxt",        "framework",       r'"nuxt"\s*:'),
        ("Express",     "framework",       r'"express"\s*:'),
        ("NestJS",      "framework",       r'"@nestjs/core"\s*:'),
        ("Vite",        "tool",            r'"vite"\s*:'),
        ("Webpack",     "tool",            r'"webpack"\s*:'),
        ("Jest",        "tool",            r'"jest"\s*:'),
        ("Vitest",      "tool",            r'"vitest"\s*:'),
        ("ESLint",      "tool",            r'"eslint"\s*:'),
        ("Prettier",    "tool",            r'"prettier"\s*:'),
        ("TypeScript",  "language-runtime",r'"typescript"\s*:'),
        ("Tailwind CSS","framework",       r'"tailwindcss"\s*:'),
        ("GraphQL",     "framework",       r'"graphql"\s*:'),
        ("Prisma",      "tool",            r'"@prisma/client"\s*:'),
    ],
    # ── Rust ─────────────────────────────────────────────────────────────────
    "Cargo.toml": [
        ("Tokio",       "framework",       r"(?i)tokio"),
        ("Actix-web",   "framework",       r"(?i)actix-web"),
        ("Axum",        "framework",       r"(?i)\baxum\b"),
        ("Serde",       "framework",       r"(?i)serde"),
        ("Diesel",      "framework",       r"(?i)diesel"),
        ("SQLx",        "framework",       r"(?i)sqlx"),
    ],
    # ── Go ───────────────────────────────────────────────────────────────────
    "go.mod": [
        ("Gin",         "framework",       r"gin-gonic/gin"),
        ("Echo",        "framework",       r"labstack/echo"),
        ("Fiber",       "framework",       r"gofiber/fiber"),
        ("GORM",        "framework",       r"go-gorm/gorm"),
        ("Chi",         "framework",       r"go-chi/chi"),
    ],
    # ── Java / JVM ───────────────────────────────────────────────────────────
    "pom.xml": [
        ("Spring Boot", "framework",       r"spring-boot"),
        ("Hibernate",   "framework",       r"hibernate"),
        ("Maven",       "tool",            r"<modelVersion>"),
        ("JUnit",       "tool",            r"junit"),
        ("Lombok",      "tool",            r"lombok"),
    ],
    "build.gradle": [
        ("Spring Boot", "framework",       r"(?i)spring-boot"),
        ("Gradle",      "tool",            r"(?i)gradle"),
        ("Kotlin",      "language-runtime",r"(?i)kotlin"),
        ("JUnit",       "tool",            r"(?i)junit"),
    ],
    # ── Ruby ─────────────────────────────────────────────────────────────────
    "Gemfile": [
        ("Ruby on Rails","framework",      r"(?i)rails"),
        ("Sinatra",     "framework",       r"(?i)sinatra"),
        ("RSpec",       "tool",            r"(?i)rspec"),
        ("Sidekiq",     "tool",            r"(?i)sidekiq"),
    ],
    # ── PHP ──────────────────────────────────────────────────────────────────
    "composer.json": [
        ("Laravel",     "framework",       r"laravel/framework"),
        ("Symfony",     "framework",       r"symfony/symfony"),
        ("PHPUnit",     "tool",            r"phpunit/phpunit"),
    ],
    # ── DevOps / infrastructure ───────────────────────────────────────────────
    "docker-compose.yml":  [("Docker Compose", "devops", r"(?i)version")],
    "docker-compose.yaml": [("Docker Compose", "devops", r"(?i)version")],
    ".github/workflows":   [],  # directory — presence alone signals GitHub Actions
    "terraform.tf":        [("Terraform", "devops", r"(?i)terraform")],
    "main.tf":             [("Terraform", "devops", r"(?i)resource|provider")],
    "serverless.yml":      [("Serverless Framework", "devops", r"(?i)service")],
    "k8s":                 [],  # directory presence
    "kubernetes":          [],  # directory presence
    ".circleci/config.yml":[("CircleCI", "devops", r"(?i)version")],
    "Jenkinsfile":         [("Jenkins", "devops", r"(?i)pipeline")],
}

# Simple presence-only detections (the mere existence of the file/dir signals a tool).
_PRESENCE_STACK: list[tuple[str, str, str, str]] = [
    # (filename_lower, display_name, category, source_file)
    ("dockerfile",              "Docker",           "devops",   "Dockerfile"),
    (".github/workflows",       "GitHub Actions",   "devops",   ".github/workflows/"),
    ("k8s",                     "Kubernetes",       "devops",   "k8s/"),
    ("kubernetes",              "Kubernetes",       "devops",   "kubernetes/"),
    (".travis.yml",             "Travis CI",        "devops",   ".travis.yml"),
    ("circle.yml",              "CircleCI",         "devops",   "circle.yml"),
    (".circleci",               "CircleCI",         "devops",   ".circleci/"),
    ("jest.config.js",          "Jest",             "tool",     "jest.config.js"),
    ("jest.config.ts",          "Jest",             "tool",     "jest.config.ts"),
    ("vite.config.js",          "Vite",             "tool",     "vite.config.js"),
    ("vite.config.ts",          "Vite",             "tool",     "vite.config.ts"),
    ("tailwind.config.js",      "Tailwind CSS",     "framework","tailwind.config.js"),
    ("tailwind.config.ts",      "Tailwind CSS",     "framework","tailwind.config.ts"),
    ("next.config.js",          "Next.js",          "framework","next.config.js"),
    ("next.config.ts",          "Next.js",          "framework","next.config.ts"),
    ("nuxt.config.js",          "Nuxt",             "framework","nuxt.config.js"),
    ("angular.json",            "Angular",          "framework","angular.json"),
    ("svelte.config.js",        "Svelte",           "framework","svelte.config.js"),
    ("pubspec.yaml",            "Flutter / Dart",   "framework","pubspec.yaml"),
    ("mix.exs",                 "Elixir / Phoenix", "framework","mix.exs"),
    ("rebar.config",            "Erlang",           "language-runtime","rebar.config"),
]


def _read_text_safe(path: Path, max_bytes: int = 256_000) -> str:
    """
    Read up to *max_bytes* of a text file, returning "" on any error.

    We cap at 256 KB so a huge auto-generated lockfile (e.g. package-lock.json)
    doesn't block the scan.  We only need to detect presence of a keyword, not
    parse the entire file.
    """
    try:
        raw = path.read_bytes()[:max_bytes]
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _detect_stack(repo_root: Path) -> list[StackItem]:
    """
    Walk known config-file locations and return all detected StackItems.

    Deduplicates by (name, category) — if React is found in both
    package.json and package-lock.json we only report it once.
    """
    found: dict[tuple[str, str], StackItem] = {}   # (name, category) → StackItem

    def _add(name: str, category: str, source: str, version: str = "") -> None:
        key = (name, category)
        if key not in found:
            found[key] = StackItem(
                name=name, category=category,
                source_file=source, version=version,
            )

    # ── Presence-only checks (case-insensitive on Linux) ──────────────────────
    # Build a set of lowercased filenames/dirnames actually present at repo root
    # so we can match "Dockerfile", "dockerfile", "DOCKERFILE" equally.
    try:
        root_names_lower: set[str] = {e.name.lower() for e in repo_root.iterdir()}
    except PermissionError:
        root_names_lower = set()

    for filename_lower, display, category, source in _PRESENCE_STACK:
        # Strip trailing slash used for display purposes
        lookup = filename_lower.rstrip("/").lower()
        if lookup in root_names_lower:
            _add(display, category, source)

    # ── Content-based checks ─────────────────────────────────────────────────
    for config_file, rules in _STACK_RULES.items():
        if not rules:
            continue   # directory-only entries handled above

        config_path = repo_root / config_file
        if not config_path.is_file():
            continue

        text = _read_text_safe(config_path)
        if not text:
            continue

        for display, category, pattern in rules:
            if re.search(pattern, text):
                _add(display, category, config_file)

    # ── Sort: frameworks first, then tools, then devops, then runtime ─────────
    _ORDER = {"framework": 0, "tool": 1, "devops": 2, "language-runtime": 3}
    return sorted(found.values(), key=lambda s: (_ORDER.get(s.category, 9), s.name))


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-PASS SCANNER
# ─────────────────────────────────────────────────────────────────────────────

# How many bytes we read per file to count lines (capped to keep it fast).
_LINE_COUNT_MAX_BYTES = 512_000   # 512 KB — plenty for line counting
# Top-N largest files to track
_TOP_FILES_N = 10


def scan_repo(repo_root: Path) -> RepoScan:
    """
    Walk *repo_root* exactly once and return a fully populated RepoScan.

    Skips:
      - Directories in NOISE_DIRS (same set used by repo_handler.count_files)
      - Symlinks (avoid cycles)
      - Files larger than 50 MB (binary assets, training data, etc.)

    Args:
        repo_root: Path to the cloned / extracted repo root.

    Returns:
        RepoScan dataclass with languages, stack, stats, and top_files.
    """
    MAX_FILE_BYTES = 50 * 1024 * 1024   # 50 MB hard cap per file

    lang_map: dict[str, LanguageStat] = {}
    total_files = 0
    total_bytes = 0
    total_lines = 0
    candidate_top: list[FileInfo] = []

    # ── Single directory walk ─────────────────────────────────────────────────
    # Use a mutable list so _walk_repo can accumulate counts in-place.
    # [total_files, total_bytes, total_lines]
    total_ref: list[int] = [0, 0, 0]
    _walk_repo(
        directory=repo_root,
        repo_root=repo_root,
        lang_map=lang_map,
        candidate_top=candidate_top,
        total_ref=total_ref,
        max_file_bytes=MAX_FILE_BYTES,
    )

    total_files  = total_ref[0]
    total_bytes  = total_ref[1]
    total_lines  = total_ref[2]

    # ── Post-process languages: sort by byte_size desc ─────────────────────
    sorted_langs = sorted(lang_map.values(), key=lambda ls: ls.byte_size, reverse=True)

    # ── Top files: keep the N largest ──────────────────────────────────────
    top_files = sorted(candidate_top, key=lambda f: f.byte_size, reverse=True)[:_TOP_FILES_N]

    # ── Tech stack detection (reads specific config files only) ────────────
    stack = _detect_stack(repo_root)

    return RepoScan(
        languages=sorted_langs,
        stack=stack,
        total_files=total_files,
        total_bytes=total_bytes,
        total_lines=total_lines,
        top_files=top_files,
        repo_root=repo_root,
    )


def _walk_repo(
    directory: Path,
    repo_root: Path,
    lang_map: dict[str, LanguageStat],
    candidate_top: list[FileInfo],
    total_ref: list[int],       # [total_files, total_bytes, total_lines]
    max_file_bytes: int,
) -> None:
    """
    Recursive DFS walk — accumulates all scan data in-place.

    Separated from scan_repo to keep the public function clean and to
    allow future parallelisation of subtrees if needed.
    """
    try:
        entries = list(directory.iterdir())
    except PermissionError:
        return

    for entry in entries:
        if entry.is_symlink():
            continue

        if entry.is_dir():
            if entry.name not in NOISE_DIRS:
                _walk_repo(
                    entry, repo_root, lang_map,
                    candidate_top, total_ref, max_file_bytes,
                )
            continue

        if not entry.is_file():
            continue

        # ── File-level processing ─────────────────────────────────────────
        try:
            byte_size = entry.stat().st_size
        except OSError:
            continue

        if byte_size > max_file_bytes:
            continue   # Skip very large binary/data files

        language = detect_language(entry)

        # Accumulate language stats
        if language not in lang_map:
            lang_map[language] = LanguageStat(name=language)
        lang_map[language].file_count += 1
        lang_map[language].byte_size  += byte_size

        # Accumulate totals
        total_ref[0] += 1    # file count
        total_ref[1] += byte_size

        # Line count — only for code languages, capped for performance
        if language in _CODE_LANGUAGES and byte_size > 0:
            lines = _count_lines(entry)
            total_ref[2] += lines

        # Track candidate top files (we trim to top-N after the walk)
        rel_path = entry.relative_to(repo_root)
        candidate_top.append(FileInfo(
            path=rel_path,
            byte_size=byte_size,
            language=language,
        ))


def _count_lines(path: Path) -> int:
    """
    Count newlines in a text file, reading at most _LINE_COUNT_MAX_BYTES.

    Returns 0 on any read error or if the file is binary.
    """
    try:
        raw = path.read_bytes()[:_LINE_COUNT_MAX_BYTES]
        # Quick binary check: if >30% of first 512 bytes are non-printable,
        # treat as binary and skip.
        sample = raw[:512]
        if sample:
            non_printable = sum(1 for b in sample if b < 9 or (14 <= b < 32))
            if non_printable / len(sample) > 0.30:
                return 0
        return raw.count(b"\n")
    except Exception:
        return 0
