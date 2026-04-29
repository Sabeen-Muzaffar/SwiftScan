"""
utils/code_viewer_tab.py
────────────────────────
Renders the "💻 Code Viewer" dashboard tab — polished UI version.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from utils.language_detector import detect_language
from utils.llm_wrapper import (
    DEFAULT_MODEL,
    explain_file,
    explain_snippet,
    is_ai_available,
    get_backend_name,
    list_local_models,
)

_MAX_VIEW_BYTES = 5 * 1024 * 1024
_MAX_VIEW_LINES = 5_000

_LANG_HINTS: dict[str, str] = {
    "py": "python", "pyi": "python",
    "js": "javascript", "mjs": "javascript", "jsx": "javascript",
    "ts": "typescript", "tsx": "typescript",
    "html": "html", "htm": "html",
    "css": "css", "scss": "css", "sass": "css",
    "json": "json", "jsonc": "json",
    "yaml": "yaml", "yml": "yaml",
    "toml": "toml",
    "md": "markdown", "mdx": "markdown",
    "sh": "bash", "bash": "bash", "zsh": "bash",
    "sql": "sql", "rs": "rust", "go": "go",
    "java": "java", "kt": "kotlin",
    "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "hpp": "cpp",
    "c": "c", "h": "c", "cs": "csharp",
    "rb": "ruby", "php": "php", "swift": "swift",
    "tf": "hcl", "tfvars": "hcl", "xml": "xml",
    "dockerfile": "dockerfile", "r": "r", "lua": "lua",
}

_LANG_COLOURS: dict[str, str] = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Java": "#b07219", "Rust": "#dea584", "Go": "#00ADD8",
    "C++": "#f34b7d", "C#": "#178600", "Ruby": "#701516",
    "PHP": "#4F5D95", "Kotlin": "#A97BFF", "Swift": "#F05138",
    "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051",
    "SQL": "#e38c00", "Markdown": "#083fa1", "YAML": "#cb171e",
    "JSON": "#292929", "Dockerfile": "#384d54",
}


def _lang_hint(file_path: Path) -> str:
    if file_path.name.lower() == "dockerfile":
        return "dockerfile"
    return _LANG_HINTS.get(file_path.suffix.lstrip(".").lower(), "")


def _ensure_viewer_state() -> None:
    defaults = {
        "viewer_file":         None,
        "viewer_explanation":  None,
        "viewer_model":        DEFAULT_MODEL,
        "viewer_line_start":   1,
        "viewer_line_end":     1,
        "viewer_explain_mode": "file",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def render_code_viewer_tab(repo_root: Path) -> None:
    _ensure_viewer_state()

    # Sync from Explorer: only fire once per Explorer click, then clear
    # selected_file so it doesn't keep overwriting the viewer's own selection.
    explorer_selection = st.session_state.get("selected_file")
    if explorer_selection:
        st.session_state.viewer_file = explorer_selection
        st.session_state.viewer_explanation = None
        # Clear so this only fires once — viewer manages its own file from here
        st.session_state.selected_file = None

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        _render_file_selector(repo_root)
        _render_code_panel(repo_root)

    with col_right:
        _render_ai_panel(repo_root)


# ─────────────────────────────────────────────────────────────────────────────
# FILE SELECTOR
# ─────────────────────────────────────────────────────────────────────────────

def _render_file_selector(repo_root: Path) -> None:
    all_files = _collect_text_files(repo_root)

    if not all_files:
        st.warning("No text files found in this repository.")
        return

    current = st.session_state.viewer_file
    current_idx = all_files.index(current) if current in all_files else 0

    st.markdown('<p style="font-size:0.75rem; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:4px;">Select File</p>', unsafe_allow_html=True)

    selected = st.selectbox(
        label="file_selector",
        options=all_files,
        index=current_idx,
        key="viewer_selectbox",
        label_visibility="collapsed",
        help="Or click any file in the Explorer tab",
    )

    # Update state without rerun — Streamlit rerenders automatically
    if selected != st.session_state.viewer_file:
        st.session_state.viewer_file = selected
        st.session_state.viewer_explanation = None


def _collect_text_files(repo_root: Path, max_files: int = 1_000) -> list[str]:
    from utils.repo_handler import NOISE_DIRS
    results: list[str] = []
    _walk_for_files(repo_root, repo_root, results, NOISE_DIRS, max_files)
    return sorted(results)


def _walk_for_files(
    directory: Path,
    repo_root: Path,
    results: list[str],
    noise_dirs: frozenset[str],
    max_files: int,
) -> None:
    if len(results) >= max_files:
        return
    try:
        entries = list(directory.iterdir())
    except PermissionError:
        return
    for entry in sorted(entries, key=lambda e: e.name.lower()):
        if entry.is_symlink():
            continue
        if entry.is_dir():
            if entry.name not in noise_dirs:
                _walk_for_files(entry, repo_root, results, noise_dirs, max_files)
        elif entry.is_file():
            if len(results) >= max_files:
                return
            try:
                if entry.stat().st_size <= _MAX_VIEW_BYTES:
                    results.append(entry.relative_to(repo_root).as_posix())
            except OSError:
                continue


# ─────────────────────────────────────────────────────────────────────────────
# CODE PANEL
# ─────────────────────────────────────────────────────────────────────────────

def _render_code_panel(repo_root: Path) -> None:
    rel_path = st.session_state.viewer_file
    if not rel_path:
        st.markdown("""
        <div style="
            background:linear-gradient(135deg,#111827,#1F2937);
            border:1px dashed #374151; border-radius:12px;
            padding:3rem; text-align:center; margin-top:1rem;
            color:#475569;
        ">
            <div style="font-size:2.5rem; margin-bottom:0.8rem;">💻</div>
            <div style="font-size:0.9rem; color:#64748B;">
                Select a file above to view its source code
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    file_path = repo_root / rel_path
    if not file_path.exists():
        st.error(f"File not found: `{rel_path}`")
        return

    try:
        raw = file_path.read_bytes()
    except Exception as exc:
        st.error(f"Could not read file: {exc}")
        return

    sample = raw[:512]
    if sample:
        non_printable = sum(1 for b in sample if b < 9 or (14 <= b < 32))
        if non_printable / len(sample) > 0.20:
            st.markdown(f"""
            <div style="
                background:#1C1A0D; border:1px solid #854D0E;
                border-radius:10px; padding:1.2rem 1.4rem; margin-top:1rem;
            ">
                <div style="font-size:0.9rem; font-weight:600; color:#FCD34D; margin-bottom:4px;">
                    ⚠️ Binary file
                </div>
                <div style="font-size:0.8rem; color:#92400E;">
                    Cannot display as text · {len(raw):,} bytes
                </div>
            </div>
            """, unsafe_allow_html=True)
            return

    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    total_lines = len(lines)
    language = detect_language(file_path)
    size_str = f"{len(raw)/1024:.1f} KB" if len(raw) >= 1024 else f"{len(raw)} B"
    lang_colour = _LANG_COLOURS.get(language, "#00B4C8")

    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#111827,#1F2937);
        border:1px solid #1F2937; border-radius:10px;
        padding:10px 14px; margin: 0.8rem 0;
        display:flex; align-items:center; gap:12px; flex-wrap:wrap;
    ">
        <span style="
            background:{lang_colour}22; border:1px solid {lang_colour}55;
            color:{lang_colour}; border-radius:20px;
            padding:2px 10px; font-size:0.72rem; font-weight:700;
        ">{language}</span>
        <span style="font-size:0.78rem; color:#94A3B8; font-family:'JetBrains Mono',monospace;">
            {Path(rel_path).name}
        </span>
        <span style="font-size:0.72rem; color:#475569; margin-left:auto;">
            {total_lines:,} lines · {size_str}
        </span>
    </div>
    """, unsafe_allow_html=True)

    clipped = False
    if total_lines > _MAX_VIEW_LINES:
        lines = lines[:_MAX_VIEW_LINES]
        clipped = True

    display_text = "\n".join(lines)
    if clipped:
        display_text += f"\n\n... (showing first {_MAX_VIEW_LINES:,} of {total_lines:,} lines)"

    st.code(display_text, language=_lang_hint(file_path) or None, line_numbers=True)
    st.session_state["_viewer_total_lines"] = total_lines


# ─────────────────────────────────────────────────────────────────────────────
# AI PANEL
# ─────────────────────────────────────────────────────────────────────────────

def _render_ai_panel(repo_root: Path) -> None:
    st.markdown("""
    <div style="
        background:linear-gradient(135deg,#111827,#1F2937);
        border:1px solid #1F2937; border-left:3px solid #0EA5E9;
        border-radius:12px; padding:1rem 1.2rem; margin-bottom:1rem;
    ">
        <div style="font-size:1.1rem; font-weight:700; color:#E2E8F0; margin-bottom:2px;">
            🤖 AI Explanation
        </div>
        <div style="font-size:0.75rem; color:#64748B;">
            Understand any file or selection instantly
        </div>
    </div>
    """, unsafe_allow_html=True)

    rel_path = st.session_state.viewer_file
    if not rel_path:
        st.markdown("""
        <div style="
            background:#111827; border:1px dashed #374151;
            border-radius:10px; padding:1.5rem; text-align:center;
            color:#475569; font-size:0.82rem;
        ">
            Select a file on the left to enable AI features
        </div>
        """, unsafe_allow_html=True)
        return

    file_path = repo_root / rel_path
    language  = detect_language(file_path)
    ai_ok     = is_ai_available()
    backend   = get_backend_name()

    # Backend status
    if ai_ok:
        st.markdown(f"""
        <div style="
            background:linear-gradient(135deg,#0D2318,#0F1C14);
            border:1px solid #166534; border-radius:10px;
            padding:10px 14px; margin-bottom:1rem;
            display:flex; align-items:center; gap:8px;
        ">
            <span>✅</span>
            <div>
                <div style="font-size:0.68rem; color:#4ADE80; text-transform:uppercase; letter-spacing:0.05em;">AI Connected</div>
                <div style="font-size:0.88rem; font-weight:600; color:#E2E8F0;">{backend}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="
            background:#1C1A0D; border:1px solid #854D0E;
            border-radius:10px; padding:10px 14px; margin-bottom:1rem;
        ">
            <div style="font-size:0.85rem; font-weight:600; color:#FCD34D; margin-bottom:4px;">
                ⚠️ No AI backend
            </div>
            <div style="font-size:0.78rem; color:#92400E; line-height:1.6;">
                Add GROQ_API_KEY to .streamlit/secrets.toml
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Model selector (only shown for Ollama)
    local_models = list_local_models()
    if local_models:
        try:
            current_idx = local_models.index(st.session_state.viewer_model)
        except ValueError:
            current_idx = 0
        st.markdown('<p style="font-size:0.72rem; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:4px;">Model</p>', unsafe_allow_html=True)
        selected_model = st.selectbox(
            "model",
            options=local_models,
            index=current_idx,
            key="viewer_model_select",
            disabled=not ai_ok,
            label_visibility="collapsed",
        )
        st.session_state.viewer_model = selected_model
    else:
        selected_model = st.session_state.viewer_model

    st.markdown("<div style='margin:0.8rem 0'></div>", unsafe_allow_html=True)

    # ── Explain full file button ──────────────────────────────────────────────
    fname = Path(rel_path).name
    if st.button(
        f"✨ Explain {fname}",
        use_container_width=True,
        type="primary",
        disabled=not ai_ok,
        key="btn_explain_file",
    ):
        with st.spinner(f"Asking {backend}…"):
            try:
                result = explain_file(file_path, language, model=selected_model)
            except Exception as exc:
                result = f"⚠️ Exception: {exc}"
        if not result or not result.strip():
            result = "⚠️ Got empty response."
        st.session_state.viewer_explanation = result
        st.session_state.viewer_explain_mode = "file"
        # No st.rerun() — Streamlit rerenders automatically after button click

    # ── Snippet selector ──────────────────────────────────────────────────────
    st.markdown("<div style='margin:0.6rem 0'></div>", unsafe_allow_html=True)
    with st.expander("✂️ Explain a snippet", expanded=False):
        total_lines = st.session_state.get("_viewer_total_lines", 100)
        c1, c2 = st.columns(2)
        with c1:
            start = st.number_input(
                "Start line", min_value=1, max_value=total_lines,
                value=min(st.session_state.viewer_line_start, total_lines),
                step=1, key="snippet_start",
            )
        with c2:
            end = st.number_input(
                "End line", min_value=1, max_value=total_lines,
                value=min(st.session_state.viewer_line_end, total_lines),
                step=1, key="snippet_end",
            )
        st.session_state.viewer_line_start = int(start)
        st.session_state.viewer_line_end   = int(end)

        if st.button(
            f"✨ Explain lines {int(start)}–{int(end)}",
            use_container_width=True,
            disabled=not ai_ok,
            key="btn_explain_snippet",
        ):
            snippet = _extract_lines(file_path, int(start), int(end))
            with st.spinner(f"Asking {backend}…"):
                result = explain_snippet(
                    file_path, snippet, int(start), int(end),
                    model=selected_model,
                )
            st.session_state.viewer_explanation = result or "⚠️ Got empty response."
            st.session_state.viewer_explain_mode = "snippet"
            # No st.rerun() — Streamlit rerenders automatically

    # ── Explanation output ────────────────────────────────────────────────────
    # expl = st.session_state.get("viewer_explanation")
    # if expl:
    #     st.divider()
    #     mode  = st.session_state.get("viewer_explain_mode", "file")
    #     label = "📄 File Explanation" if mode == "file" else "✂️ Snippet Explanation"
    #     st.markdown(f"""
    #     <div style="font-size:0.7rem; font-weight:700; color:#00B4C8;
    #         text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.5rem;">
    #         ✦ {label}
    #     </div>
    #     """, unsafe_allow_html=True)
    #     if expl.startswith("⚠️"):
    #         st.error(expl)
    #     else:
    #         st.markdown(expl)
    #     if st.button("🗑️ Clear", key="btn_clear_explanation", use_container_width=True):
    #         st.session_state.viewer_explanation = None
    #         st.rerun()
        # ── Explanation output ────────────────────────────────────────────────────
    expl = st.session_state.get("viewer_explanation")
    if expl:
        st.divider()
        mode = st.session_state.get("viewer_explain_mode", "file")
        _render_visual_explanation(expl, mode, file_path)


# ─────────────────────────────────────────────────────────────────────────────
# VISUAL EXPLANATION RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def _render_visual_explanation(explanation: str, mode: str, file_path: Path) -> None:
    """Render AI explanation in an interactive visual format"""
    
    if explanation.startswith("⚠️"):
        st.error(explanation)
        if st.button("🗑️ Clear", key="btn_clear_explanation", use_container_width=True):
            st.session_state.viewer_explanation = None
            st.rerun()
        return
    
    # Header
    label = "📄 File Explanation" if mode == "file" else "✂️ Snippet Explanation"
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #0D1F2D, #111827);
        border: 1px solid #164E63; border-left: 3px solid #00B4C8;
        border-radius: 10px; padding: 10px 14px; margin-bottom: 12px;
    ">
        <div style="font-size: 0.85rem; font-weight: 700; color: #00B4C8;">
            {label}
        </div>
        <div style="font-size: 0.7rem; color: #64748B;">
            {file_path.name}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Parse explanation into sections
    sections = _parse_explanation_sections(explanation)
    
    # Render each section as an interactive card
    for i, section in enumerate(sections):
        _render_explanation_card(section, i)
    
    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🗑️ Clear", key="btn_clear_explanation", use_container_width=True):
            st.session_state.viewer_explanation = None
            st.rerun()
    with col2:
        if st.button("📋 Copy Text", key="btn_copy_explanation", use_container_width=True):
            st.code(explanation, language=None)
    with col3:
        st.download_button(
            "💾 Save",
            explanation,
            file_name=f"explanation_{file_path.stem}.md",
            mime="text/markdown",
            use_container_width=True,
            key="btn_download_explanation"
        )


def _parse_explanation_sections(text: str) -> list[dict]:
    """Parse explanation text into structured sections"""
    sections = []
    
    # Common section headers to look for
    section_markers = [
        "**Purpose**", "**Key components**", "**Key Components**",
        "**Dependencies**", "**How it fits in**", "**How it fits**",
        "**Step by step**", "**Step by Step**", "**What it does**",
        "**Why it exists**", "**Overview**", "**Summary**",
        "**Details**", "**Architecture**", "**Patterns**",
    ]
    
    # Try to split by markdown headers
    lines = text.split('\n')
    current_section = {"title": "📋 Overview", "content": []}
    
    for line in lines:
        # Check if line is a section header
        is_header = False
        for marker in section_markers:
            if line.strip().startswith(marker):
                # Save previous section
                if current_section["content"]:
                    current_section["content"] = '\n'.join(current_section["content"]).strip()
                    sections.append(current_section)
                # Start new section
                title = line.strip().replace('**', '').strip(':# ')
                current_section = {"title": f"📌 {title}", "content": []}
                is_header = True
                break
        
        if not is_header:
            current_section["content"].append(line)
    
    # Add last section
    if current_section["content"]:
        current_section["content"] = '\n'.join(current_section["content"]).strip()
        if current_section["content"]:
            sections.append(current_section)
    
    # If no sections found, treat whole text as one section
    if not sections:
        sections = [{"title": "📋 Explanation", "content": text.strip()}]
    
    return sections


def _render_explanation_card(section: dict, index: int) -> None:
    """Render a single explanation section as an expandable card"""
    
    # Color scheme based on section type
    title_lower = section["title"].lower()
    if "purpose" in title_lower or "what it does" in title_lower:
        accent_color = "#4ADE80"
        bg_color = "#0D2318"
        border_color = "#166534"
        icon = "🎯"
    elif "component" in title_lower or "architecture" in title_lower:
        accent_color = "#60A5FA"
        bg_color = "#0D1F3C"
        border_color = "#1E3A5F"
        icon = "🧩"
    elif "depend" in title_lower or "import" in title_lower:
        accent_color = "#F59E0B"
        bg_color = "#1C1A0D"
        border_color = "#854D0E"
        icon = "🔗"
    elif "step" in title_lower:
        accent_color = "#A78BFA"
        bg_color = "#1C1235"
        border_color = "#4C1D95"
        icon = "🪜"
    elif "why" in title_lower:
        accent_color = "#FB923C"
        bg_color = "#1C140D"
        border_color = "#9A3412"
        icon = "💡"
    elif "fit" in title_lower or "connect" in title_lower:
        accent_color = "#38BDF8"
        bg_color = "#0D1F2D"
        border_color = "#164E63"
        icon = "🔌"
    else:
        accent_color = "#00B4C8"
        bg_color = "#111827"
        border_color = "#1F2937"
        icon = "📌"
    
    # Extract any code blocks from content
    content = section["content"]
    code_blocks = []
    text_parts = []
    
    if "```" in content:
        parts = content.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 1:  # Code block
                code_blocks.append(part.strip())
            else:  # Text
                if part.strip():
                    text_parts.append(part.strip())
    else:
        text_parts = [content]
    
    # Render as expander card
    with st.expander(f"{icon} {section['title']}", expanded=(index == 0)):
        # Section card background
        st.markdown(f"""
        <div style="
            background: {bg_color};
            border: 1px solid {border_color};
            border-left: 3px solid {accent_color};
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
        ">
        """, unsafe_allow_html=True)
        
        # Render text content
        for text in text_parts:
            # Highlight key terms
            text = _highlight_key_terms(text)
            st.markdown(text)
        
        # Render code blocks with syntax highlighting
        for i, code in enumerate(code_blocks):
            # Try to detect language from first line
            lines = code.split('\n')
            lang = ""
            if lines and lines[0].strip() in ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'bash', 'json', 'yaml', 'sql']:
                lang = lines[0].strip()
                code = '\n'.join(lines[1:])
            
            st.markdown(f"""
            <div style="
                background: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                margin: 8px 0;
            ">
            """, unsafe_allow_html=True)
            st.code(code, language=lang or None)
            st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)


def _highlight_key_terms(text: str) -> str:
    """Highlight important technical terms in the text"""
    import re
    
    # Patterns to highlight
    patterns = [
        (r'\b(function|class|method|module|package|import|export|const|let|var)\b', 
         r'<code style="background:#1F2937;color:#60A5FA;padding:1px 4px;border-radius:3px;font-size:0.85em;">\1</code>'),
        (r'\b(Python|JavaScript|TypeScript|Java|Go|Rust|React|Node\.js|API|REST|GraphQL|SQL|Docker|Git)\b',
         r'<code style="background:#1F2937;color:#F59E0B;padding:1px 4px;border-radius:3px;font-size:0.85em;">\1</code>'),
        (r'`([^`]+)`',
         r'<code style="background:#1F2937;color:#4ADE80;padding:1px 4px;border-radius:3px;font-size:0.85em;">\1</code>'),
    ]
    
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    
    return text
# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _extract_lines(file_path: Path, start: int, end: int) -> str:
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        all_lines = text.splitlines()
        return "\n".join(all_lines[max(0, start-1): min(len(all_lines), end)])
    except Exception:
        return ""