"""
utils/llm_wrapper.py
────────────────────
LLM wrapper supporting two backends:

  1. Groq API   — free, extremely fast (~1 sec responses).
                  Requires GROQ_API_KEY in st.secrets or env var.
                  Uses llama-3.1-8b-instant (fast + free).

  2. Ollama     — local inference, completely free but slow on CPU.
                  Requires `ollama serve` running.

Priority: Groq is tried first (fast). Falls back to Ollama if no key set.

Public API:
    is_ai_available() -> bool
    get_backend_name() -> str
    list_local_models() -> list[str]
    explain_file(file_path, language, model) -> str
    explain_snippet(file_path, code, start, end, model) -> str
    generate_setup_guide(primary_language, stack_items, config_files, readme) -> str
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import streamlit as st

# ── Backend flags ──────────────────────────────────────────────────────────
try:
    from groq import Groq as _GroqClient
    _GROQ_PKG = True
except ImportError:
    _GROQ_PKG = False

try:
    import ollama as _ollama
    _OLLAMA_PKG = True
except ImportError:
    _OLLAMA_PKG = False

_GEMINI_PKG = False  # not used

# Default models
DEFAULT_OLLAMA_MODEL: str = os.environ.get("SWIFTSCAN_MODEL", "llama3.2:3b")
DEFAULT_MODEL = DEFAULT_OLLAMA_MODEL
_GROQ_MODEL = "llama-3.1-8b-instant"   # fast + free on Groq

_MAX_CODE_CHARS   = 8_000
_MAX_README_CHARS = 4_000


# ─────────────────────────────────────────────────────────────────────────────
# BACKEND DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _get_groq_key() -> str:
    # Try multiple ways to read the secret (Streamlit versions differ)
    try:
        key = st.secrets["GROQ_API_KEY"]
        if key:
            return str(key).strip()
    except Exception:
        pass
    try:
        key = st.secrets.get("GROQ_API_KEY", "")
        if key:
            return str(key).strip()
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY", "").strip()


def _groq_available() -> bool:
    if not _GROQ_PKG:
        return False
    return bool(_get_groq_key())


def _ollama_available() -> bool:
    if not _OLLAMA_PKG:
        return False
    try:
        result = _ollama.list()
        models = result.models if hasattr(result, "models") else result.get("models", [])
        return len(models) > 0
    except Exception:
        return False


def is_ai_available() -> bool:
    return _groq_available() or _ollama_available()


def get_backend_name() -> str:
    if _groq_available():
        return "Groq API"
    if _ollama_available():
        return "Ollama"
    return "None"


def list_local_models() -> list[str]:
    if not _OLLAMA_PKG:
        return []
    try:
        result = _ollama.list()
        models = result.models if hasattr(result, "models") else result.get("models", [])
        return [m.model if hasattr(m, "model") else m["name"] for m in models]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────

_EXPLAIN_FILE_PROMPT = textwrap.dedent("""\
    You are SwiftScan, an AI assistant helping junior developers understand
    unfamiliar codebases. Explain the following source file clearly and concisely.

    Your explanation must cover:
    1. **Purpose** — What does this file do? What problem does it solve?
    2. **Key components** — List the main functions, classes, or sections and describe each in 1-2 sentences.
    3. **Dependencies** — What does it import or depend on?
    4. **How it fits in** — How does this file connect to the rest of the project?

    Keep your explanation under 400 words. Use plain Markdown. Do NOT repeat the code.

    File: {filename}
    Language: {language}

    ```{lang_hint}
    {code}
    ```
""")

_EXPLAIN_SNIPPET_PROMPT = textwrap.dedent("""\
    You are SwiftScan, an AI assistant helping junior developers understand code.
    Explain the following snippet clearly.

    1. **What it does** — Plain-English description.
    2. **Step by step** — Walk through the logic block by block.
    3. **Why it exists** — Why would a developer write this?

    Keep your explanation under 300 words. Use plain Markdown. Do NOT repeat the code.

    File: {filename} (lines {start_line}-{end_line})

    ```{lang_hint}
    {code}
    ```
""")

_SETUP_GUIDE_PROMPT = textwrap.dedent("""\
    You are SwiftScan. Based on the project info below, write a clear Markdown
    setup guide for a junior developer who wants to run this project locally.

    Include these sections (## headings):
    ## Prerequisites
    ## Installation
    ## Configuration (if applicable)
    ## Running the App
    ## Running Tests (if a test framework is detected)
    ## Common Issues (2-3 beginner pitfalls)

    Use actual commands and filenames from the project info. Under 500 words.

    --- PROJECT INFO ---
    Primary language: {primary_language}
    Detected stack: {stack_items}
    Key config files: {config_files}

    README (first {readme_chars} chars):
    {readme_content}
    --- END ---
""")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def explain_file(
    file_path: Path,
    language: str,
    model: str = DEFAULT_OLLAMA_MODEL,
) -> str:
    code = _read_file_for_llm(file_path)
    if code.startswith("⚠️"):
        return code
    prompt = _EXPLAIN_FILE_PROMPT.format(
        filename=file_path.name,
        language=language,
        lang_hint=_lang_hint(file_path),
        code=code,
    )
    return _call_llm(prompt, model)


def explain_snippet(
    file_path: Path,
    code_snippet: str,
    start_line: int,
    end_line: int,
    model: str = DEFAULT_OLLAMA_MODEL,
) -> str:
    if not code_snippet.strip():
        return "⚠️ No code selected — select some lines first."
    snippet = code_snippet[:_MAX_CODE_CHARS]
    if len(code_snippet) > _MAX_CODE_CHARS:
        snippet += "\n... (truncated)"
    prompt = _EXPLAIN_SNIPPET_PROMPT.format(
        filename=file_path.name,
        start_line=start_line,
        end_line=end_line,
        lang_hint=_lang_hint(file_path),
        code=snippet,
    )
    return _call_llm(prompt, model)


def generate_setup_guide(
    primary_language: str,
    stack_items: list[str],
    config_files: list[str],
    readme_content: str,
    model: str = DEFAULT_OLLAMA_MODEL,
) -> str:
    readme_excerpt = readme_content[:_MAX_README_CHARS]
    if len(readme_content) > _MAX_README_CHARS:
        readme_excerpt += "\n... (truncated)"
    prompt = _SETUP_GUIDE_PROMPT.format(
        primary_language=primary_language,
        stack_items=", ".join(stack_items) if stack_items else "none detected",
        config_files=", ".join(config_files) if config_files else "none",
        readme_chars=_MAX_README_CHARS,
        readme_content=readme_excerpt or "(no README found)",
    )
    return _call_llm(prompt, model)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTING — Groq first (fast), Ollama fallback
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm(prompt: str, model: str) -> str:
    if _groq_available():
        return _call_groq(prompt)
    if _ollama_available():
        return _call_ollama(prompt, model)
    return _no_backend_msg()


def _call_groq(prompt: str) -> str:
    try:
        client = _GroqClient(api_key=_get_groq_key())
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        lower = str(exc).lower()
        if "api_key" in lower or "authentication" in lower or "401" in lower:
            return (
                "⚠️ **Invalid Groq API key.**\n\n"
                "Check your key at [console.groq.com](https://console.groq.com).\n\n"
                "In `.streamlit/secrets.toml`:\n"
                "```toml\nGROQ_API_KEY = \"your-key-here\"\n```"
            )
        if "rate" in lower or "429" in lower:
            return "⚠️ **Groq rate limit hit.** Wait a moment and try again."
        return f"⚠️ **Groq API error:** {exc}"


def _call_ollama(prompt: str, model: str) -> str:
    try:
        response = _ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.message.content if hasattr(response, "message") else response["message"]["content"]
        return content.strip()
    except Exception as exc:
        lower = str(exc).lower()
        if "connection" in lower or "refused" in lower:
            return (
                "⚠️ **Ollama is not running.**\n\n"
                "```bash\nollama serve\n```\n"
                f"```bash\nollama pull {model}\n```"
            )
        if "model" in lower and "not found" in lower:
            return (
                f"⚠️ **Model `{model}` not found.**\n\n"
                f"```bash\nollama pull {model}\n```"
            )
        return f"⚠️ **Ollama error:** {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _read_file_for_llm(file_path: Path) -> str:
    try:
        raw = file_path.read_bytes()
        sample = raw[:512]
        if sample:
            non_printable = sum(1 for b in sample if b < 9 or (14 <= b < 32))
            if non_printable / len(sample) > 0.20:
                return "⚠️ This file appears to be binary and cannot be explained."
        text = raw.decode("utf-8", errors="replace")
        if len(text) > _MAX_CODE_CHARS:
            return text[:_MAX_CODE_CHARS] + f"\n... (truncated at {_MAX_CODE_CHARS} chars)"
        return text
    except FileNotFoundError:
        return f"⚠️ File not found: {file_path}"
    except Exception as exc:
        return f"⚠️ Could not read file: {exc}"


def _lang_hint(file_path: Path) -> str:
    name = file_path.name.lower()
    if name == "dockerfile":
        return "dockerfile"
    return file_path.suffix.lstrip(".").lower()


def _no_backend_msg() -> str:
    return (
        "⚠️ **No AI backend configured.**\n\n"
        "**Option A — Groq API** (free, ~1 sec responses):\n"
        "Get a free key at [console.groq.com](https://console.groq.com)\n"
        "then add to `.streamlit/secrets.toml`:\n"
        "```toml\nGROQ_API_KEY = \"your-key-here\"\n```\n\n"
        "**Option B — Ollama** (local, free but slow on CPU):\n"
        "```bash\nollama serve\n```"
    )