"""
app.py — SwiftScan entry point
"""
import os
import atexit
import shutil
import tempfile
import zipfile
from pathlib import Path
import streamlit as st

from utils.repo_handler import clone_github_repo, count_files, extract_zip
from utils.language_detector import RepoScan, scan_repo
from utils.file_tree import build_tree, MAX_NODES
from utils.overview_tab import render_overview_tab
from utils.explorer_tab import render_explorer_tab
from utils.code_viewer_tab import render_code_viewer_tab
from utils.setup_guide_tab import render_setup_guide_tab
from utils.chat_assistant import ChatAssistant, create_chat_ui, get_repo_context_for_chat

st.set_page_config(
    page_title="SwiftScan",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS injection ───────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base & fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D0E16 0%, #111827 100%) !important;
    border-right: 1px solid #1F2937 !important;
}
[data-testid="stSidebar"] .block-container {
    padding-top: 2rem !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] button {
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    padding: 0.5rem 1.2rem !important;
    border-radius: 8px 8px 0 0 !important;
    color: #94A3B8 !important;
    transition: all 0.2s ease !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00B4C8 !important;
    background: #111827 !important;
    border-bottom: 2px solid #00B4C8 !important;
}
[data-testid="stTabs"] button:hover {
    color: #E2E8F0 !important;
    background: #1F2937 !important;
}

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    transition: all 0.2s ease !important;
    border: 1px solid #374151 !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00B4C8, #0EA5E9) !important;
    border: none !important;
    color: white !important;
    box-shadow: 0 4px 15px rgba(0, 180, 200, 0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(0, 180, 200, 0.4) !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #00B4C8 !important;
    color: #00B4C8 !important;
}

/* ── Text inputs ── */
.stTextInput > div > div > input {
    background: #1F2937 !important;
    border: 1px solid #374151 !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
    font-size: 0.85rem !important;
    transition: border-color 0.2s ease !important;
}
.stTextInput > div > div > input:focus {
    border-color: #00B4C8 !important;
    box-shadow: 0 0 0 3px rgba(0, 180, 200, 0.15) !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: #1F2937 !important;
    border: 1px solid #374151 !important;
    border-radius: 8px !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #111827 !important;
    border: 1px solid #1F2937 !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #00B4C8 !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    color: #64748B !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

/* ── Alerts ── */
.stSuccess {
    background: #0D2318 !important;
    border: 1px solid #166534 !important;
    border-radius: 10px !important;
    color: #4ADE80 !important;
}
.stWarning {
    background: #1C1A0D !important;
    border: 1px solid #854D0E !important;
    border-radius: 10px !important;
}
.stError {
    background: #1C0D0D !important;
    border: 1px solid #991B1B !important;
    border-radius: 10px !important;
}
.stInfo {
    background: #0D1425 !important;
    border: 1px solid #1E3A5F !important;
    border-radius: 10px !important;
}

/* ── Code blocks ── */
.stCode, code {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
    border-radius: 8px !important;
}

/* ── Expanders ── */
.streamlit-expanderHeader {
    background: #111827 !important;
    border: 1px solid #1F2937 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}

/* ── Dividers ── */
hr {
    border-color: #1F2937 !important;
    margin: 1rem 0 !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0D1117; }
::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #00B4C8; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #1F2937 !important;
    border: 1px dashed #374151 !important;
    border-radius: 10px !important;
    padding: 0.5rem !important;
    transition: border-color 0.2s ease !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #00B4C8 !important;
}

/* ── Number inputs ── */
.stNumberInput > div > div > input {
    background: #1F2937 !important;
    border: 1px solid #374151 !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────
def _init_session_state() -> None:
    defaults = {
        "repo_root":        None,
        "file_count":       0,
        "temp_dir":         None,
        "repo_label":       "",
        "load_error":       None,
        "repo_scan":        None,
        "file_tree":        None,
        "tree_truncated":   False,
        "selected_file":    None,
        "tree_open_dirs":   set(),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

_init_session_state()


# ── Cleanup ────────────────────────────────────────────────────────────────
def _cleanup_temp_dir() -> None:
    if st.session_state.temp_dir and Path(st.session_state.temp_dir).exists():
        shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
    for key in ("temp_dir", "repo_root", "repo_scan", "file_tree", "load_error", "selected_file"):
        st.session_state[key] = None
    st.session_state.file_count     = 0
    st.session_state.repo_label     = ""
    st.session_state.tree_truncated = False
    st.session_state.tree_open_dirs = set()

atexit.register(_cleanup_temp_dir)


# ── Analysis ───────────────────────────────────────────────────────────────
def _run_analysis(repo_root: Path) -> None:
    st.session_state.repo_root  = repo_root
    st.session_state.file_count = count_files(repo_root)
    st.session_state.repo_scan  = scan_repo(repo_root)
    tree, node_count = build_tree(repo_root)
    st.session_state.file_tree      = tree
    st.session_state.tree_truncated = node_count >= MAX_NODES


def _handle_github_url(url: str) -> None:
    url = url.strip()
    _cleanup_temp_dir()
    tmp = tempfile.mkdtemp(prefix="swiftscan_")
    st.session_state.temp_dir = tmp
    try:
        repo_root = clone_github_repo(url, tmp)
        _run_analysis(repo_root)
        parts = [p for p in url.rstrip("/").split("/") if p]
        st.session_state.repo_label = "/".join(parts[-2:]) if len(parts) >= 2 else url
    except (ValueError, RuntimeError) as exc:
        st.session_state.load_error = str(exc)
        _cleanup_temp_dir()
    except Exception as exc:
        st.session_state.load_error = f"Unexpected error: {exc}"
        _cleanup_temp_dir()


def _handle_zip_upload(uploaded_file) -> None:
    _cleanup_temp_dir()
    tmp = tempfile.mkdtemp(prefix="swiftscan_")
    st.session_state.temp_dir = tmp
    try:
        zip_bytes = uploaded_file.read()
        repo_root = extract_zip(zip_bytes, tmp)
        _run_analysis(repo_root)
        st.session_state.repo_label = uploaded_file.name
    except (ValueError, zipfile.BadZipFile) as exc:
        st.session_state.load_error = f"Invalid zip: {exc}"
        _cleanup_temp_dir()
    except Exception as exc:
        st.session_state.load_error = f"Unexpected error: {exc}"
        _cleanup_temp_dir()



# ── Sidebar ────────────────────────────────────────────────────────────────
def render_sidebar() -> None:
    with st.sidebar:
        # Logo / brand
        st.markdown("""
        <div style="padding: 0.5rem 0 1.5rem 0;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">
                <div style="
                    background: linear-gradient(135deg, #00B4C8, #0EA5E9);
                    border-radius: 10px; width: 36px; height: 36px;
                    display:flex; align-items:center; justify-content:center;
                    font-size: 1.1rem; box-shadow: 0 4px 12px rgba(99,102,241,0.4);
                ">⚡</div>
                <div>
                    <div style="font-size:1.2rem; font-weight:700; color:#E2E8F0; line-height:1.2;">SwiftScan</div>
                    <div style="font-size:0.7rem; color:#64748B; letter-spacing:0.05em;">CODEBASE EXPLORER</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #1F2937, #111827);
            border: 1px solid #374151;
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 1.2rem;
            font-size: 0.78rem;
            color: #94A3B8;
            line-height: 1.5;
        ">
            📂 Paste a GitHub URL or upload a <strong style="color:#00B4C8">.zip</strong>
            to instantly understand any codebase with AI.
        </div>
        """, unsafe_allow_html=True)

        # GitHub URL input
        st.markdown('<p style="font-size:0.8rem; font-weight:600; color:#94A3B8; margin-bottom:4px; text-transform:uppercase; letter-spacing:0.05em;">GitHub URL</p>', unsafe_allow_html=True)
        # github_url = st.text_input(
        #     label="github_url",
        #     placeholder="https://github.com/user/repo",
        #     label_visibility="collapsed",
        #     key="github_url_input",
        # )

        query_params = st.query_params
        repo_from_url = query_params.get("repo")

        github_url = st.text_input( 
            label="github_url",
            placeholder="https://github.com/user/repo",
            value=repo_from_url if repo_from_url else "",
            label_visibility="collapsed",
            key="github_url_input",
            )
        
        if "analyzed" not in st.session_state:
            st.session_state.analyzed = False
        
        if repo_from_url and not st.session_state.analyzed:
            st.session_state.analyzed = True

            with st.spinner("Analyzing repository..."):
                _handle_github_url(repo_from_url)

            if not st.session_state.load_error:
                st.rerun()

        st.markdown('<p style="font-size:0.8rem; font-weight:600; color:#94A3B8; margin: 12px 0 4px 0; text-transform:uppercase; letter-spacing:0.05em;">Upload .zip</p>', unsafe_allow_html=True)
        uploaded_zip = st.file_uploader(
            label="zip_upload",
            type=["zip"],
            label_visibility="collapsed",
        )

        st.markdown("<div style='margin: 1rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)

        analyze_clicked = st.button(
            "⚡ Analyze Codebase",
            use_container_width=True,
            type="primary",
        )

        if analyze_clicked:
            if github_url and uploaded_zip:
                st.warning("Provide either a URL **or** a zip — not both.")
            elif not github_url and not uploaded_zip:
                st.warning("Enter a GitHub URL or upload a .zip file.")
            elif github_url:
                with st.spinner("Cloning repository…"):
                    _handle_github_url(github_url)
                if not st.session_state.load_error:
                    st.rerun()
            else:
                with st.spinner("Extracting zip…"):
                    _handle_zip_upload(uploaded_zip)
                if not st.session_state.load_error:
                    st.rerun()

        # Loaded repo badge
        if st.session_state.repo_root:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #0D2318, #0F1C14);
                border: 1px solid #166534;
                border-radius: 10px;
                padding: 10px 14px;
                margin: 0.8rem 0;
            ">
                <div style="font-size:0.7rem; color:#4ADE80; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:2px;">✅ Loaded</div>
                <div style="font-size:0.9rem; font-weight:600; color:#E2E8F0; word-break:break-all;">{st.session_state.repo_label}</div>
                <div style="font-size:0.75rem; color:#64748B; margin-top:2px;">{st.session_state.file_count:,} files scanned</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🗑️ Clear & Reset", use_container_width=True):
                _cleanup_temp_dir()
                st.rerun()

        if st.session_state.load_error:
            st.error(st.session_state.load_error)

        # Footer
        st.markdown("""
        <div style="
            position: fixed; bottom: 1.5rem;
            font-size: 0.7rem; color: #334155;
            text-align: center; width: 200px;
        ">
            Powered by Ollama · Streamlit
        </div>
        """, unsafe_allow_html=True)


# ── Main content ───────────────────────────────────────────────────────────
def render_main() -> None:
    if not st.session_state.repo_root:
        _render_landing()
        return

    # Repo loaded header
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #0D1425, #111827);
        border: 1px solid #1E3A5F;
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        gap: 12px;
    ">
        <div style="
            background: linear-gradient(135deg, #00B4C8, #0EA5E9);
            border-radius: 8px; width:32px; height:32px;
            display:flex; align-items:center; justify-content:center;
            font-size:1rem; flex-shrink:0;
        ">📦</div>
        <div>
            <div style="font-size:0.7rem; color:#64748B; text-transform:uppercase; letter-spacing:0.05em;">Repository loaded</div>
            <div style="font-size:1rem; font-weight:600; color:#E2E8F0;">{st.session_state.repo_label}
                <span style="font-size:0.78rem; font-weight:400; color:#64748B; margin-left:8px;">{st.session_state.file_count:,} files</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_overview, tab_explorer, tab_viewer, tab_setup = st.tabs([
        "📊  Overview",
        "🗂️  Explorer",
        "💻  Code Viewer",
        "📖  Setup Guide",
    ])

    with tab_overview:
        if st.session_state.repo_scan:
            render_overview_tab(st.session_state.repo_scan)
        else:
            st.info("Run Analyze to generate the overview.")

    with tab_explorer:
        if st.session_state.file_tree and st.session_state.repo_root:
            render_explorer_tab(
                root=st.session_state.file_tree,
                repo_root=st.session_state.repo_root,
                truncated=st.session_state.tree_truncated,
            )
        else:
            st.info("Run Analyze to load the file explorer.")

    with tab_viewer:
        if st.session_state.repo_root:
            render_code_viewer_tab(repo_root=st.session_state.repo_root)
        else:
            st.info("Run Analyze to enable the code viewer.")

    with tab_setup:
        if st.session_state.repo_scan and st.session_state.repo_root:
            render_setup_guide_tab(
                scan=st.session_state.repo_scan,
                repo_root=st.session_state.repo_root,
            )
        else:
            st.info("Run Analyze to generate the setup guide.")


def _render_landing() -> None:
    # Hero section
    st.markdown("""
    <div style="text-align:center; padding: 3rem 1rem 2rem 1rem;">
        <div style="
            display: inline-flex;
            background: linear-gradient(135deg, #00B4C8, #0EA5E9);
            border-radius: 20px; width: 72px; height: 72px;
            align-items: center; justify-content: center;
            font-size: 2rem; margin-bottom: 1.2rem;
            box-shadow: 0 8px 32px rgba(99, 102, 241, 0.4);
        ">⚡</div>
        <h1 style="
            font-size: 2.8rem; font-weight: 800;
            background: linear-gradient(135deg, #00B4C8, #0EA5E9);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin: 0 0 0.5rem 0; line-height: 1.2;
        ">SwiftScan</h1>
        <p style="
            font-size: 1.1rem; color: #64748B; max-width: 520px;
            margin: 0 auto 0.5rem auto; line-height: 1.6;
        ">
            Understand any codebase, instantly.
        </p>
        <p style="font-size:0.9rem; color:#475569; max-width:480px; margin: 0 auto;">
            Drop in a GitHub URL or zip file and get an AI-powered breakdown
            of languages, files, and what every piece of code does.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Feature cards
    cols = st.columns(4, gap="medium")
    cards = [
        ("📊", "Overview", "#00B4C8", "Language breakdown, tech stack detection, and repo stats at a glance."),
        ("🗂️", "Explorer", "#0EA5E9", "Clickable file tree with instant search across all files."),
        ("💻", "Code Viewer", "#06B6D4", "Syntax-highlighted source with AI explanations per file or selection."),
        ("📖", "Setup Guide", "#10B981", "Auto-generated install & run instructions for any project."),
    ]
    for col, (icon, title, color, desc) in zip(cols, cards):
        with col:
            st.markdown(f"""
            <div style="
                background: linear-gradient(160deg, #111827, #0D0E16);
                border: 1px solid #1F2937;
                border-top: 2px solid {color};
                border-radius: 12px;
                padding: 1.4rem 1.2rem;
                height: 160px;
                transition: transform 0.2s ease;
            ">
                <div style="font-size:1.8rem; margin-bottom:0.6rem;">{icon}</div>
                <div style="font-size:0.95rem; font-weight:700; color:#E2E8F0; margin-bottom:0.4rem;">{title}</div>
                <div style="font-size:0.78rem; color:#64748B; line-height:1.5;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    # Quick start
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #111827, #0D0E16);
        border: 1px solid #1F2937;
        border-radius: 14px;
        padding: 1.5rem 2rem;
        margin-top: 2rem;
        text-align: center;
    ">
        <div style="font-size:0.8rem; color:#64748B; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.8rem;">Quick Start</div>
        <div style="display:flex; justify-content:center; align-items:center; gap:1.5rem; flex-wrap:wrap;">
            <div style="text-align:center;">
                <div style="
                    background: #1F2937; border: 1px solid #374151;
                    border-radius: 50%; width:32px; height:32px;
                    display:inline-flex; align-items:center; justify-content:center;
                    font-weight:700; color:#00B4C8; font-size:0.85rem; margin-bottom:6px;
                ">1</div>
                <div style="font-size:0.8rem; color:#94A3B8;">Paste GitHub URL<br>or upload .zip</div>
            </div>
            <div style="color:#374151; font-size:1.2rem;">→</div>
            <div style="text-align:center;">
                <div style="
                    background: #1F2937; border: 1px solid #374151;
                    border-radius: 50%; width:32px; height:32px;
                    display:inline-flex; align-items:center; justify-content:center;
                    font-weight:700; color:#00B4C8; font-size:0.85rem; margin-bottom:6px;
                ">2</div>
                <div style="font-size:0.8rem; color:#94A3B8;">Click<br>⚡ Analyze</div>
            </div>
            <div style="color:#374151; font-size:1.2rem;">→</div>
            <div style="text-align:center;">
                <div style="
                    background: #1F2937; border: 1px solid #374151;
                    border-radius: 50%; width:32px; height:32px;
                    display:inline-flex; align-items:center; justify-content:center;
                    font-weight:700; color:#00B4C8; font-size:0.85rem; margin-bottom:6px;
                ">3</div>
                <div style="font-size:0.8rem; color:#94A3B8;">Explore the<br>4 tabs</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Chat Assistant ──────────────────────────────────────────────────────────
def init_chat_assistant():
    """Initialize the Gemini chat assistant if API key is available"""
    import os
    
    # Try to get API key from multiple sources
    gemini_api_key = (
        os.getenv("GEMINI_API_KEY") or 
        st.secrets.get("GEMINI_API_KEY", "")
    )
    
    if "chat_assistant_initialized" not in st.session_state:
        if gemini_api_key:
            try:
                st.session_state.chat_assistant = ChatAssistant(api_key=gemini_api_key)
                st.session_state.chat_assistant_initialized = True
                st.session_state.has_chat_api_key = True
            except Exception as e:
                st.session_state.chat_assistant = None
                st.session_state.chat_assistant_initialized = True
                st.session_state.has_chat_api_key = False
                print(f"Chat assistant initialization error: {e}")
        else:
            st.session_state.chat_assistant = None
            st.session_state.chat_assistant_initialized = True
            st.session_state.has_chat_api_key = False


def update_chat_context():
    """Update chat assistant with current repository context"""
    if (st.session_state.get("repo_root") and 
        st.session_state.get("chat_assistant") and 
        st.session_state.get("repo_scan")):
        
        repo_scan = st.session_state.repo_scan
        
        # Handle languages - could be dict, list, or custom objects
        languages_dict = {}
        primary_lang = "Unknown"
        
        if hasattr(repo_scan, 'languages') and repo_scan.languages:
            raw_languages = repo_scan.languages
            
            if isinstance(raw_languages, dict):
                for key, value in raw_languages.items():
                    # Convert key to string (in case it's a LanguageStat object)
                    lang_name = str(key)
                    
                    # Convert value to simple types
                    if hasattr(value, '__dict__'):
                        # It's a custom object - extract attributes
                        lang_data = {
                            'files': int(getattr(value, 'files', 0)),
                            'lines': int(getattr(value, 'lines', 0)),
                            'percentage': float(getattr(value, 'percentage', 0))
                        }
                    elif isinstance(value, (int, float)):
                        lang_data = {'files': int(value)}
                    else:
                        lang_data = str(value)
                    
                    languages_dict[lang_name] = lang_data
                    
            elif isinstance(raw_languages, (list, set)):
                # If it's a list, create a simple count
                for lang in raw_languages:
                    lang_name = str(lang)
                    languages_dict[lang_name] = languages_dict.get(lang_name, 0) + 1
            
            # Determine primary language
            if languages_dict:
                if isinstance(next(iter(languages_dict.values())), dict):
                    primary_lang = max(languages_dict.items(), 
                                     key=lambda x: x[1].get('files', 0))[0]
                else:
                    primary_lang = max(languages_dict.items(), 
                                     key=lambda x: x[1])[0]
        
        # Get total lines safely
        total_lines = 0
        if hasattr(repo_scan, 'total_lines'):
            total_lines = int(repo_scan.total_lines or 0)
        elif hasattr(repo_scan, 'line_count'):
            total_lines = int(repo_scan.line_count or 0)
        elif hasattr(repo_scan, 'total_lines_of_code'):
            total_lines = int(repo_scan.total_lines_of_code or 0)
        
        # If we couldn't find total_lines, calculate from languages
        if total_lines == 0 and languages_dict:
            for lang_data in languages_dict.values():
                if isinstance(lang_data, dict):
                    total_lines += lang_data.get('lines', 0)
        
        # Get tech stack safely
        tech_stack = []
        if hasattr(repo_scan, 'tech_stack'):
            raw_stack = repo_scan.tech_stack
            if isinstance(raw_stack, (list, set)):
                tech_stack = [str(item) for item in raw_stack]
        elif hasattr(repo_scan, 'stack'):
            raw_stack = repo_scan.stack
            if isinstance(raw_stack, (list, set)):
                tech_stack = [str(item) for item in raw_stack]
        
        # Get key files
        key_files = []
        if hasattr(repo_scan, 'key_files'):
            raw_files = repo_scan.key_files
            if isinstance(raw_files, (list, set)):
                key_files = [str(f) for f in raw_files][:10]
        
        # Build clean, serializable context
        repo_context = {
            "name": str(st.session_state.repo_label or "Unknown Repository"),
            "primary_language": str(primary_lang),
            "languages": languages_dict,
            "total_files": int(st.session_state.file_count),
            "total_lines": int(total_lines),
            "tech_stack": tech_stack,
            "project_type": str(getattr(repo_scan, 'project_type', 'General')),
            "key_files": key_files,
            "has_tests": bool(getattr(repo_scan, 'has_tests', False)),
            "has_docker": bool(getattr(repo_scan, 'has_docker', False)),
            "has_docs": bool(getattr(repo_scan, 'has_docs', False)),
        }
        
        # Update the chat assistant context
        try:
            st.session_state.chat_assistant.set_repo_context(repo_context)
            return True
        except Exception as e:
            st.sidebar.error(f"Failed to set chat context: {e}")
            # Try with all strings as fallback
            fallback_context = {k: str(v) for k, v in repo_context.items()}
            st.session_state.chat_assistant.set_repo_context(fallback_context)
            return True
    
    return False

def render_chat_integration():
    """Render the chat assistant UI if repo is loaded"""
    if st.session_state.get("repo_root"):
        if st.session_state.get("has_chat_api_key") and st.session_state.get("chat_assistant"):
            # Update context when repo changes
            if "last_repo_context" not in st.session_state:
                st.session_state.last_repo_context = None
            
            current_repo = st.session_state.repo_label
            if current_repo != st.session_state.last_repo_context:
                update_chat_context()
                st.session_state.last_repo_context = current_repo
            
            # Render the chat UI
            create_chat_ui(st.session_state.chat_assistant)
        else:
            # Show API key setup info
            with st.sidebar:
                st.markdown("---")
                with st.expander("🤖 Enable AI Chat Assistant", expanded=False):
                    st.markdown("""
                    **Add free Gemini API chat support!**
                    
                    1. Get key at [Google AI Studio](https://aistudio.google.com/apikey)
                    2. Create `.streamlit/secrets.toml`:
                    ```toml
                    GEMINI_API_KEY = "your-key-here"
                                """)
# ── Entry point ────────────────────────────────────────────────────────────
init_chat_assistant()

render_sidebar()
render_chat_integration()
render_main()
