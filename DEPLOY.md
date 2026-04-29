# 🚀 Deploying SwiftScan to Streamlit Cloud

Streamlit Cloud is **free** and deploys directly from GitHub. Here's the complete guide.

---

## Step 1 — Push your code to GitHub

```bash
# One-time setup
git init
git add .
git commit -m "Initial SwiftScan commit"

# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/swiftscan.git
git branch -M main
git push -u origin main
```

> ⚠️ **Never commit `.streamlit/secrets.toml`** — it's already in `.gitignore`.
> Your API key goes in the Streamlit Cloud dashboard instead (Step 3).

---

## Step 2 — Deploy on Streamlit Cloud

1. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub
2. Click **"New app"**
3. Fill in:
   - **Repository:** `YOUR_USERNAME/swiftscan`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Click **"Deploy!"**

Streamlit will install `requirements.txt` and `packages.txt` (the `git` binary) automatically.

---

## Step 3 — Add your Anthropic API key

This enables the AI explanation features on the deployed app.

1. In the Streamlit Cloud dashboard, click your app → **"⋮" → Settings**
2. Click **"Secrets"**
3. Paste:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-YOUR-KEY-HERE"
   ```
4. Click **Save** — the app restarts automatically

Get a free key at **[console.anthropic.com](https://console.anthropic.com)**.
Free tier includes generous usage for a personal project.

---

## What works on Streamlit Cloud vs locally

| Feature | Streamlit Cloud | Local |
|---|---|---|
| GitHub URL clone | ✅ | ✅ |
| Zip upload | ✅ | ✅ |
| Language detection | ✅ | ✅ |
| File explorer | ✅ | ✅ |
| Code viewer | ✅ | ✅ |
| AI explanations | ✅ via Anthropic API | ✅ via Anthropic or Ollama |
| Static setup guide | ✅ | ✅ |
| AI setup guide | ✅ via Anthropic API | ✅ via Anthropic or Ollama |

---

## Troubleshooting cloud deployments

**"Module not found: git"**
→ Make sure `packages.txt` with the single line `git` is in your repo root.

**AI buttons show "No AI backend configured"**
→ Check your secret is named exactly `ANTHROPIC_API_KEY` (no spaces, correct case).

**App crashes on startup**
→ Check the logs in the Streamlit Cloud dashboard (click "Manage app" → "Logs").

**Clone fails for some repos**
→ Only public GitHub repos are supported. Private repos need a GitHub token
  (add `GITHUB_TOKEN` to secrets and pass it to GitPython — future enhancement).

**Slow cold start (~30 sec)**
→ Normal on Streamlit Cloud free tier. The app "sleeps" after inactivity
  and takes a moment to wake up.

---

## Local development with Anthropic API (no Ollama needed)

Create `.streamlit/secrets.toml`:
```toml
ANTHROPIC_API_KEY = "sk-ant-YOUR-KEY-HERE"
```

Then run normally:
```bash
streamlit run app.py
```

SwiftScan will use the Anthropic API automatically — no `ollama serve` needed.
