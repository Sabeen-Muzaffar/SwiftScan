"""
utils/setup_guide_tab.py
────────────────────────
Renders the "📖 Setup Guide" dashboard tab — polished UI version.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from utils.language_detector import RepoScan, StackItem
from utils.llm_wrapper import (
    DEFAULT_MODEL,
    generate_setup_guide,
    is_ai_available,
    get_backend_name,
    list_local_models,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG FILES TO DETECT
# ─────────────────────────────────────────────────────────────────────────────

_CONFIG_FILENAMES: list[str] = [
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.toml", "go.mod", "go.sum",
    "pom.xml", "build.gradle", "build.gradle.kts",
    "Gemfile", "composer.json",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".env.example", ".env.sample",
    "Makefile", "justfile",
    "README.md", "README.rst", "README.txt",
]

_STATIC_TEMPLATES: dict[str, dict[str, str]] = {
    "Python": {
        "install": (
            "python -m venv .venv\n"
            "source .venv/bin/activate   # Windows: .venv\\Scripts\\activate\n"
            "pip install -r requirements.txt"
        ),
        "run":  "python main.py   # adjust entrypoint as needed",
        "test": "pytest",
    },
    "JavaScript": {
        "install": "npm install",
        "run":     "npm start",
        "test":    "npm test",
    },
    "TypeScript": {
        "install": "npm install",
        "run":     "npm run dev",
        "test":    "npm test",
    },
    "Go": {
        "install": "go mod download",
        "run":     "go run .",
        "test":    "go test ./...",
    },
    "Rust": {
        "install": "cargo build",
        "run":     "cargo run",
        "test":    "cargo test",
    },
    "Java": {
        "install": "mvn install   # or: gradle build",
        "run":     "mvn spring-boot:run   # or: java -jar target/app.jar",
        "test":    "mvn test",
    },
    "Ruby": {
        "install": "bundle install",
        "run":     "ruby app.rb   # or: rails server",
        "test":    "bundle exec rspec",
    },
    "PHP": {
        "install": "composer install",
        "run":     "php artisan serve   # or: php -S localhost:8000",
        "test":    "vendor/bin/phpunit",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def render_setup_guide_tab(scan: RepoScan, repo_root: Path) -> None:
    _ensure_state()

    config_files = _find_config_files(repo_root)
    readme_text  = _read_readme(repo_root)
    stack_names  = [s.name for s in scan.stack]

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        _render_static_guide(scan, config_files, readme_text)

    with col_right:
        _render_ai_panel(scan, config_files, readme_text, stack_names)


# ─────────────────────────────────────────────────────────────────────────────
# STATIC GUIDE  (left column)
# ─────────────────────────────────────────────────────────────────────────────

def _render_static_guide(
    scan: RepoScan,
    config_files: list[str],
    readme_text: str,
) -> None:
    # Header
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #111827, #1F2937);
        border: 1px solid #1F2937;
        border-left: 3px solid #00B4C8;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 1.2rem;
    ">
        <div style="font-size:1.1rem; font-weight:700; color:#E2E8F0; margin-bottom:2px;">
            📖 Project Setup Guide
        </div>
        <div style="font-size:0.75rem; color:#64748B;">
            Auto-generated from detected stack · no AI needed
        </div>
    </div>
    """, unsafe_allow_html=True)

    lang     = scan.dominant_language
    template = _STATIC_TEMPLATES.get(lang)

    # Prerequisites section
    _section_header("🔧", "Prerequisites", "#00B4C8")
    prereqs = _build_prereqs(lang, scan.stack)
    prereqs_html = "".join([
        f'<div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:6px;">'
        f'<span style="color:#00B4C8;margin-top:2px;">▸</span>'
        f'<span style="font-size:0.85rem;color:#CBD5E1;line-height:1.5;">{p}</span>'
        f'</div>'
        for p in prereqs
    ])
    st.markdown(f"""
    <div style="
        background:#111827; border:1px solid #1F2937;
        border-radius:10px; padding:1rem 1.2rem; margin-bottom:1rem;
    ">{prereqs_html}</div>
    """, unsafe_allow_html=True)

    # Key files detected
    if config_files:
        _section_header("📄", "Key Files Detected", "#06B6D4")
        cols = st.columns(3)
        for i, fname in enumerate(config_files):
            with cols[i % 3]:
                ext = fname.split(".")[-1].lower() if "." in fname else ""
                icon = {"json":"📋","toml":"📄","txt":"📄","yml":"⚙️",
                        "yaml":"⚙️","xml":"📄","md":"📝","lock":"🔒",
                        "dockerfile":"🐳","makefile":"⚙️"}.get(ext, "📄")
                if fname.lower() == "dockerfile":
                    icon = "🐳"
                st.markdown(f"""
                <div style="
                    background:#111827; border:1px solid #1F2937;
                    border-radius:8px; padding:8px 10px; margin-bottom:6px;
                    font-size:0.78rem; color:#94A3B8;
                    display:flex; align-items:center; gap:6px;
                ">
                    <span>{icon}</span>
                    <span style="word-break:break-all;">{fname}</span>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)

    # Install & run commands
    if template:
        _section_header("⬇️", "Installation", "#10B981")
        st.code(template["install"], language="bash")

        _section_header("▶️", "Running the App", "#F59E0B")
        st.code(template["run"], language="bash")

        test_tools  = {s.name.lower() for s in scan.stack if s.category == "tool"}
        show_tests  = any(
            t in test_tools
            for t in ("pytest", "jest", "vitest", "rspec", "phpunit", "junit")
        )
        if show_tests:
            _section_header("🧪", "Running Tests", "#0EA5E9")
            st.code(template["test"], language="bash")
    else:
        st.markdown(f"""
        <div style="
            background:linear-gradient(135deg,#111827,#1F2937);
            border:1px dashed #374151; border-radius:10px;
            padding:1.2rem; text-align:center; margin-bottom:1rem;
        ">
            <div style="font-size:1.5rem;margin-bottom:0.4rem;">🤖</div>
            <div style="font-size:0.85rem;color:#64748B;">
                No template for <strong style="color:#00B4C8">{lang}</strong> yet.
                Use the <strong style="color:#00B4C8">AI Guide</strong> on the right
                for a custom setup guide.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # README
    if readme_text:
        with st.expander("📄 View README", expanded=False):
            st.markdown(readme_text[:6_000])
            if len(readme_text) > 6_000:
                st.caption("*(README truncated)*")


# ─────────────────────────────────────────────────────────────────────────────
# AI PANEL  (right column)
# ─────────────────────────────────────────────────────────────────────────────

def _render_ai_panel(
    scan: RepoScan,
    config_files: list[str],
    readme_text: str,
    stack_names: list[str],
) -> None:
    # Header
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #111827, #1F2937);
        border: 1px solid #1F2937;
        border-left: 3px solid #0EA5E9;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 1.2rem;
    ">
        <div style="font-size:1.1rem; font-weight:700; color:#E2E8F0; margin-bottom:2px;">
            🤖 AI Setup Guide
        </div>
        <div style="font-size:0.75rem; color:#64748B;">
            Richer, README-aware instructions powered by AI
        </div>
    </div>
    """, unsafe_allow_html=True)

    ai_ok   = is_ai_available()
    backend = get_backend_name()

    # Backend status badge
    if ai_ok:
        st.markdown(f"""
        <div style="
            background:linear-gradient(135deg,#0D2318,#0F1C14);
            border:1px solid #166534; border-radius:10px;
            padding:10px 14px; margin-bottom:1rem;
            display:flex; align-items:center; gap:8px;
        ">
            <span style="font-size:1rem;">✅</span>
            <div>
                <div style="font-size:0.7rem;color:#4ADE80;text-transform:uppercase;
                    letter-spacing:0.05em;">AI Connected</div>
                <div style="font-size:0.88rem;font-weight:600;color:#E2E8F0;">{backend}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="
            background:#1C1A0D; border:1px solid #854D0E;
            border-radius:10px; padding:10px 14px; margin-bottom:1rem;
        ">
            <div style="font-size:0.85rem;font-weight:600;color:#FCD34D;margin-bottom:4px;">
                ⚠️ Ollama is not running
            </div>
            <div style="font-size:0.78rem;color:#92400E;line-height:1.5;">
                Open a terminal and run:<br>
                <code style="color:#FCD34D;">ollama serve</code>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Model selector
    local_models  = list_local_models()
    model_options = local_models if local_models else [DEFAULT_MODEL]
    try:
        idx = model_options.index(st.session_state.setup_model)
    except ValueError:
        idx = 0

    st.markdown('<p style="font-size:0.75rem;color:#64748B;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">Model</p>', unsafe_allow_html=True)
    selected_model = st.selectbox(
        "model_select",
        model_options,
        index=idx,
        key="setup_model_select",
        disabled=not ai_ok,
        label_visibility="collapsed",
    )
    st.session_state.setup_model = selected_model

    st.markdown("<div style='margin:0.8rem 0'></div>", unsafe_allow_html=True)

    if st.button(
        "✨ Generate AI Setup Guide",
        use_container_width=True,
        type="primary",
        disabled=not ai_ok,
        key="btn_gen_setup",
    ):
        with st.spinner(f"Generating with {backend}…"):
            result = generate_setup_guide(
                primary_language=scan.dominant_language,
                stack_items=stack_names,
                config_files=config_files,
                readme_content=readme_text,
                model=selected_model,
            )
        st.session_state.setup_guide_result = result
        st.rerun()

    # Result
    if st.session_state.setup_guide_result:
        st.markdown("<div style='margin:1rem 0 0.5rem 0'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:0.7rem;color:#00B4C8;text-transform:uppercase;
            letter-spacing:0.08em;font-weight:700;margin-bottom:0.5rem;">
            ✦ AI Generated Guide
        </div>
        """, unsafe_allow_html=True)

        st.markdown(st.session_state.setup_guide_result)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Copy", key="btn_copy_setup", use_container_width=True):
                st.toast("Copied!", icon="✅")
                st.components.v1.html(
                    f"<script>navigator.clipboard.writeText({repr(st.session_state.setup_guide_result)})</script>",
                    height=0,
                )
        with col2:
            if st.button("🗑️ Clear", key="btn_clear_setup", use_container_width=True):
                st.session_state.setup_guide_result = None
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _section_header(icon: str, title: str, color: str) -> None:
    st.markdown(f"""
    <div style="
        display:flex; align-items:center; gap:8px;
        margin: 1rem 0 0.5rem 0;
    ">
        <span style="font-size:0.9rem;">{icon}</span>
        <span style="font-size:0.8rem; font-weight:700; color:{color};
            text-transform:uppercase; letter-spacing:0.08em;">{title}</span>
    </div>
    """, unsafe_allow_html=True)


def _ensure_state() -> None:
    if "setup_guide_result" not in st.session_state:
        st.session_state.setup_guide_result = None
    if "setup_model" not in st.session_state:
        st.session_state.setup_model = DEFAULT_MODEL


def _find_config_files(repo_root: Path) -> list[str]:
    if not repo_root.exists():
        return []
    root_names_lower = {e.name.lower(): e.name for e in repo_root.iterdir()}
    found = []
    for fname in _CONFIG_FILENAMES:
        if fname.lower() in root_names_lower:
            found.append(root_names_lower[fname.lower()])
    return found


def _read_readme(repo_root: Path) -> str:
    for name in ("README.md", "README.rst", "README.txt", "README"):
        path = repo_root / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return ""
    try:
        for entry in repo_root.iterdir():
            if entry.name.lower().startswith("readme") and entry.is_file():
                return entry.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return ""


def _build_prereqs(lang: str, stack: list[StackItem]) -> list[str]:
    prereqs: list[str] = []
    _LANG_PREREQS: dict[str, str] = {
        "Python":     "Python 3.10+ — [python.org](https://python.org)",
        "JavaScript": "Node.js 18+ — [nodejs.org](https://nodejs.org)",
        "TypeScript": "Node.js 18+ — [nodejs.org](https://nodejs.org)",
        "Go":         "Go 1.21+ — [go.dev](https://go.dev)",
        "Rust":       "Rust + Cargo — [rustup.rs](https://rustup.rs)",
        "Java":       "JDK 17+ — [adoptium.net](https://adoptium.net)",
        "Ruby":       "Ruby 3.2+ — [ruby-lang.org](https://ruby-lang.org)",
        "PHP":        "PHP 8.2+ — [php.net](https://php.net)",
        "Dart":       "Flutter SDK — [flutter.dev](https://flutter.dev)",
        "Kotlin":     "JDK 17+ + Kotlin — [kotlinlang.org](https://kotlinlang.org)",
    }
    if lang in _LANG_PREREQS:
        prereqs.append(_LANG_PREREQS[lang])

    stack_names = {s.name.lower() for s in stack}
    if "docker" in stack_names or "docker compose" in stack_names:
        prereqs.append("Docker — [docs.docker.com](https://docs.docker.com)")
    if "poetry" in stack_names:
        prereqs.append("Poetry — `pip install poetry`")
    if any(n in stack_names for n in ("react", "next.js", "vue", "angular", "svelte")):
        if not any("node" in p.lower() for p in prereqs):
            prereqs.append("Node.js 18+ — [nodejs.org](https://nodejs.org)")
    if "prisma" in stack_names:
        prereqs.append("A database (PostgreSQL / SQLite / MySQL)")
    if not prereqs:
        prereqs.append("Check the README for specific runtime requirements.")
    return prereqs