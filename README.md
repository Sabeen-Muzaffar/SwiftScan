# 🔍 SwiftScan

> AI-powered codebase explorer for junior developers — built with Streamlit + Ollama.

Load any public GitHub repo or local zip file and instantly get:
- **Language breakdown** — pie chart + file stats
- **File explorer** — clickable tree with search
- **Code viewer** — syntax-highlighted source + AI explanations per file or line range
- **Setup guide** — auto-generated install instructions (+ AI-enriched version)

---

## System Setup Guide

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10+ | [python.org](https://python.org) |
| Git | any | [git-scm.com](https://git-scm.com) |
| Ollama | latest | [ollama.com](https://ollama.com) — **optional**, needed for AI features |

---

### Step 1 — Clone the project

```bash
git clone https://github.com/YOUR_USERNAME/swiftscan.git
cd swiftscan
```

Or unzip a downloaded copy:
```bash
unzip swiftscan.zip
cd swiftscan
```

---

### Step 2 — Create a virtual environment

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

You should see `(.venv)` in your terminal prompt.

---

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs: Streamlit, GitPython, Plotly, Pandas, Ollama SDK, and tree-sitter.

> **Note on tree-sitter:** If installation fails on Windows, install the
> [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
> first, then re-run the pip install.

---

### Step 4 — (Optional) Set up Ollama for AI features

The app works fully without Ollama — AI explanation buttons will be disabled
but everything else (language detection, file tree, setup guide) works offline.

**Install Ollama:**
- macOS: `brew install ollama` or download from [ollama.com](https://ollama.com)
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`
- Windows: Download installer from [ollama.com/download](https://ollama.com/download)

**Pull a model** (do this once — downloads ~5 GB):
```bash
ollama pull llama3.1:8b
```

Smaller/faster alternatives:
```bash
ollama pull llama3.2:3b    # ~2 GB, faster on CPU
ollama pull mistral:7b     # ~4 GB, good quality
ollama pull phi3:mini      # ~2 GB, great for code
```

**Start Ollama** (keep this running in a separate terminal):
```bash
ollama serve
```

---

### Step 5 — Run SwiftScan

```bash
streamlit run app.py
```

Your browser will open automatically at **http://localhost:8501**.

To use a different port:
```bash
streamlit run app.py --server.port 8502
```

---

### Step 6 — Use the app

1. **Paste a GitHub URL** in the sidebar, e.g.:
   ```
   https://github.com/pallets/flask
   https://github.com/tiangolo/fastapi
   https://github.com/streamlit/streamlit
   ```
   Or **upload a .zip** of your local project.

2. Click **🚀 Analyze**

3. Explore the four tabs:
   - **📊 Overview** — language chart, tech stack cards, top files
   - **🗂️ Explorer** — click folders to expand, click files to select; search by filename
   - **💻 Code Viewer** — select a file, view syntax-highlighted code, click **✨ Explain this file** (requires Ollama)
   - **📖 Setup Guide** — instant static guide + AI-enriched version (requires Ollama)

---

## Project Structure

```
swiftscan/
├── app.py                      # Streamlit entry point
├── requirements.txt
├── .gitignore
├── README.md
├── .streamlit/
│   └── config.toml             # Dark theme + server settings
├── utils/
│   ├── repo_handler.py         # GitHub clone + zip extract + file counting
│   ├── language_detector.py    # Single-pass scanner: languages, stack, stats
│   ├── file_tree.py            # TreeNode builder + search utilities
│   ├── overview_tab.py         # 📊 Overview tab renderer (Plotly charts)
│   ├── explorer_tab.py         # 🗂️ Explorer tab renderer (clickable tree)
│   ├── code_viewer_tab.py      # 💻 Code Viewer tab renderer
│   ├── llm_wrapper.py          # Ollama prompt templates + graceful degradation
│   └── setup_guide_tab.py      # 📖 Setup Guide tab renderer
└── tests/
    ├── test_repo_handler.py
    └── test_language_detector.py
```

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

Integration tests (require network + git):
```bash
pytest tests/ -v -m integration
```

---

## Troubleshooting

**`streamlit: command not found`**
→ Make sure your virtual environment is activated: `source .venv/bin/activate`

**`ModuleNotFoundError: No module named 'git'`**
→ Run `pip install gitpython` (or re-run `pip install -r requirements.txt`)

**Clone fails with "Repository not found"**
→ Only public GitHub repos are supported. Check the URL format:
`https://github.com/owner/repo` (no trailing slash, no tree/branch path)

**Ollama features show "not running"**
→ Start Ollama in a separate terminal: `ollama serve`
→ Then check it's responding: `ollama list`

**`tree-sitter` fails to install on Windows**
→ Install [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) first

**App is slow on first load of a large repo**
→ This is normal — the single-pass scan reads every file once. For very large
repos (>50k files) the scan may take 30–60 seconds. A progress bar will be
added in a future version.

**Zip upload gives "exceeds 500 MB" error**
→ The app limits uncompressed zip size to 500 MB to prevent memory issues.
For larger projects, use the GitHub URL option instead.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SWIFTSCAN_MODEL` | `llama3.1:8b` | Default Ollama model for AI features |

Example:
```bash
SWIFTSCAN_MODEL=phi3:mini streamlit run app.py
```

---

## Deploying to Streamlit Cloud

1. Push your repo to GitHub (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo.
3. Set **Main file path** to `app.py`.
4. Click **Deploy**.

> **Note:** Ollama AI features will not work on Streamlit Cloud (no local daemon).
> The app degrades gracefully — all non-AI features work normally.
