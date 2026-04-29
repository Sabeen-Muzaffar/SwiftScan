"""
utils/overview_tab.py
─────────────────────
Renders the "📊 Overview" dashboard tab — polished UI version.
"""

from __future__ import annotations

from collections import defaultdict

import plotly.graph_objects as go
import streamlit as st

from utils.language_detector import RepoScan, StackItem

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_COLOURS: dict[str, str] = {
    "Python":             "#3572A5",
    "JavaScript":         "#f1e05a",
    "TypeScript":         "#3178c6",
    "Java":               "#b07219",
    "C":                  "#555555",
    "C++":                "#f34b7d",
    "C#":                 "#178600",
    "Rust":               "#dea584",
    "Go":                 "#00ADD8",
    "Ruby":               "#701516",
    "PHP":                "#4F5D95",
    "Kotlin":             "#A97BFF",
    "Swift":              "#F05138",
    "Scala":              "#c22d40",
    "Dart":               "#00B4AB",
    "Vue":                "#41b883",
    "Svelte":             "#ff3e00",
    "HTML":               "#e34c26",
    "CSS":                "#563d7c",
    "Shell":              "#89e051",
    "PowerShell":         "#012456",
    "Dockerfile":         "#384d54",
    "Makefile":           "#427819",
    "Jupyter Notebook":   "#DA5B0B",
    "YAML":               "#cb171e",
    "TOML":               "#9c4221",
    "JSON":               "#292929",
    "Markdown":           "#083fa1",
    "SQL":                "#e38c00",
    "GraphQL":            "#e10098",
    "Terraform":          "#7B42BC",
    "Elixir":             "#6e4a7e",
    "Erlang":             "#B83998",
    "Clojure":            "#db5855",
    "Lua":                "#000080",
    "R":                  "#198CE7",
    "MATLAB":             "#e16737",
    "Perl":               "#0298c3",
    "Groovy":             "#4298b8",
    "Assembly":           "#6E4C13",
    "HCL":                "#844FBA",
    "Protobuf":           "#00979c",
    "Other":              "#4B5563",
    "Config":             "#374151",
}

_FALLBACK_COLOURS = [
    "#00B4C8", "#0EA5E9", "#06B6D4", "#10B981",
    "#F59E0B", "#EF4444", "#EC4899", "#14B8A6",
]

# Category config: (gradient_start, gradient_end, emoji, label)
_CAT_CONFIG: dict[str, tuple[str, str, str, str]] = {
    "framework":        ("#00B4C8", "#0EA5E9", "🧩", "Frameworks & Libraries"),
    "tool":             ("#06B6D4", "#0284C7", "🔧", "Build Tools & Utilities"),
    "devops":           ("#10B981", "#059669", "⚙️", "DevOps & Infrastructure"),
    "language-runtime": ("#F59E0B", "#D97706", "🔤", "Language Runtimes"),
}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def render_overview_tab(scan: RepoScan) -> None:
    if scan.total_files == 0:
        st.warning("No files were found in this repository.")
        return

    _render_kpi_row(scan)
    _spacer()
    _render_language_and_stack_row(scan)
    _spacer()
    _render_top_files(scan)


def _spacer(height: int = 16) -> None:
    st.markdown(f"<div style='margin:{height}px 0'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ROW 1 — KPI CARDS
# ─────────────────────────────────────────────────────────────────────────────

def _render_kpi_row(scan: RepoScan) -> None:
    # Size string
    if scan.total_mb >= 1:
        size_str = f"{scan.total_mb:.1f} MB"
    else:
        size_str = f"{scan.total_kb:.0f} KB"

    # Lines string
    if scan.total_lines >= 1_000:
        lines_str = f"{scan.total_lines / 1000:.1f}k"
    else:
        lines_str = f"{scan.total_lines:,}"

    # Real language count
    real_langs = [
        ls for ls in scan.languages
        if ls.name not in ("Other", "Config") and ls.byte_size > 0
    ]

    cards = [
        ("📄", "Total Files",    f"{scan.total_files:,}", "#00B4C8", "#0EA5E9", "Files scanned in repo"),
        ("💾", "Codebase Size",  size_str,                "#06B6D4", "#0284C7", "Total uncompressed size"),
        ("📝", "Lines of Code",  lines_str,               "#10B981", "#059669", "In recognised code files"),
        ("🌐", "Languages",      str(len(real_langs)),    "#F59E0B", "#D97706", f"Primary: {scan.dominant_language}"),
    ]

    cols = st.columns(4, gap="medium")
    for col, (icon, label, value, c1, c2, subtitle) in zip(cols, cards):
        with col:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #111827, #1F2937);
                border: 1px solid #1F2937;
                border-top: 3px solid {c1};
                border-radius: 14px;
                padding: 1.2rem 1.3rem;
                position: relative;
                overflow: hidden;
            ">
                <div style="
                    position:absolute; top:-20px; right:-20px;
                    width:80px; height:80px; border-radius:50%;
                    background: radial-gradient(circle, {c1}22, transparent 70%);
                "></div>
                <div style="font-size:1.4rem; margin-bottom:0.4rem;">{icon}</div>
                <div style="
                    font-size:0.7rem; color:#64748B;
                    text-transform:uppercase; letter-spacing:0.08em;
                    margin-bottom:0.3rem; font-weight:600;
                ">{label}</div>
                <div style="
                    font-size:2rem; font-weight:800; line-height:1.1;
                    background: linear-gradient(135deg, {c1}, {c2});
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                    margin-bottom:0.3rem;
                ">{value}</div>
                <div style="font-size:0.72rem; color:#475569;">{subtitle}</div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ROW 2 — LANGUAGE CHART + TECH STACK
# ─────────────────────────────────────────────────────────────────────────────

def _render_language_and_stack_row(scan: RepoScan) -> None:
    col_chart, col_stack = st.columns([1, 1], gap="large")

    with col_chart:
        st.markdown("""
        <div style="font-size:1rem; font-weight:700; color:#E2E8F0; margin-bottom:1rem;
             letter-spacing:-0.01em;">
            📊 Language Breakdown
        </div>
        """, unsafe_allow_html=True)
        _render_language_donut(scan)
        _render_language_bar(scan)

    with col_stack:
        st.markdown("""
        <div style="font-size:1rem; font-weight:700; color:#E2E8F0; margin-bottom:1rem;
             letter-spacing:-0.01em;">
            🧰 Tech Stack
        </div>
        """, unsafe_allow_html=True)
        if scan.stack:
            _render_stack_cards(scan.stack)
        else:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #111827, #1F2937);
                border: 1px dashed #374151;
                border-radius: 12px;
                padding: 2rem;
                text-align: center;
                color: #475569;
            ">
                <div style="font-size:2rem; margin-bottom:0.6rem;">🔍</div>
                <div style="font-weight:600; color:#64748B; margin-bottom:0.4rem;">
                    No frameworks detected
                </div>
                <div style="font-size:0.78rem; line-height:1.6;">
                    SwiftScan checks for <code style="color:#00B4C8">requirements.txt</code>,
                    <code style="color:#00B4C8">package.json</code>,
                    <code style="color:#00B4C8">Cargo.toml</code>,
                    <code style="color:#00B4C8">pom.xml</code> and more.
                </div>
            </div>
            """, unsafe_allow_html=True)


def _get_colour(language: str, index: int) -> str:
    if language in LANGUAGE_COLOURS:
        return LANGUAGE_COLOURS[language]
    return _FALLBACK_COLOURS[index % len(_FALLBACK_COLOURS)]


def _render_language_donut(scan: RepoScan) -> None:
    MAX_SLICES = 8
    langs = [ls for ls in scan.languages if ls.byte_size > 0]

    if len(langs) > MAX_SLICES:
        top  = langs[:MAX_SLICES]
        rest = langs[MAX_SLICES:]
        other_bytes = sum(ls.byte_size for ls in rest)
        other_slice = next((ls for ls in top if ls.name == "Other"), None)
        if other_slice:
            other_slice.byte_size += other_bytes
        else:
            from utils.language_detector import LanguageStat
            top.append(LanguageStat(name="Other", byte_size=other_bytes))
        langs = top

    labels  = [ls.name      for ls in langs]
    values  = [ls.byte_size for ls in langs]
    colours = [_get_colour(ls.name, i) for i, ls in enumerate(langs)]

    # Calculate percentages for custom labels
    total = sum(values) or 1
    text_labels = [
        f"{v/total*100:.1f}%" if v/total > 0.04 else ""
        for v in values
    ]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.62,
        marker=dict(
            colors=colours,
            line=dict(color="#0D1117", width=3),
        ),
        text=text_labels,
        textinfo="text",
        textfont=dict(size=11, color="#E2E8F0"),
        hovertemplate="<b>%{label}</b><br>%{value:,} bytes (%{percent})<extra></extra>",
        sort=False,
        direction="clockwise",
    ))

    fig.update_layout(
        annotations=[dict(
            text=f"<b>{scan.dominant_language}</b>",
            x=0.5, y=0.52,
            font=dict(size=13, color="#E2E8F0", family="Inter"),
            showarrow=False,
        ), dict(
            text="primary",
            x=0.5, y=0.43,
            font=dict(size=10, color="#64748B", family="Inter"),
            showarrow=False,
        )],
        showlegend=True,
        legend=dict(
            orientation="h",
            x=0.5, y=-0.08,
            xanchor="center",
            font=dict(size=10, color="#94A3B8"),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(t=10, b=40, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0", family="Inter"),
        height=280,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_language_bar(scan: RepoScan) -> None:
    MAX_BARS = 8
    langs = [ls for ls in scan.languages if ls.file_count > 0][:MAX_BARS]
    if not langs:
        return

    labels  = [ls.name       for ls in reversed(langs)]
    counts  = [ls.file_count for ls in reversed(langs)]
    colours = [_get_colour(ls.name, i) for i, ls in enumerate(reversed(langs))]

    fig = go.Figure(go.Bar(
        x=counts,
        y=labels,
        orientation="h",
        marker=dict(
            color=colours,
            line=dict(color="rgba(0,0,0,0)", width=0),
        ),
        text=[f"  {c:,}" for c in counts],
        textposition="outside",
        textfont=dict(size=11, color="#94A3B8"),
        hovertemplate="<b>%{y}</b>: %{x:,} files<extra></extra>",
    ))

    fig.update_layout(
        xaxis=dict(
            title=dict(text="Files", font=dict(size=11, color="#64748B")),
            showgrid=True,
            gridcolor="#1F2937",
            tickfont=dict(size=10, color="#64748B"),
            zeroline=False,
        ),
        yaxis=dict(
            title="",
            tickfont=dict(size=11, color="#94A3B8"),
        ),
        margin=dict(t=8, b=8, l=10, r=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0", family="Inter"),
        height=max(160, len(langs) * 30),
        bargap=0.35,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_stack_cards(stack: list[StackItem]) -> None:
    by_category: dict[str, list[StackItem]] = defaultdict(list)
    for item in stack:
        by_category[item.category].append(item)

    for category in ["framework", "tool", "devops", "language-runtime"]:
        items = by_category.get(category, [])
        if not items:
            continue

        cfg = _CAT_CONFIG.get(category, ("#00B4C8", "#0EA5E9", "•", category.title()))
        c1, c2, emoji, label = cfg

        st.markdown(f"""
        <div style="
            font-size:0.72rem; font-weight:700; color:{c1};
            text-transform:uppercase; letter-spacing:0.1em;
            margin: 0.8rem 0 0.5rem 0;
        ">{emoji} {label}</div>
        """, unsafe_allow_html=True)

        # Render items in rows of 2
        for row_start in range(0, len(items), 2):
            row = items[row_start: row_start + 2]
            cols = st.columns(len(row))
            for col, item in zip(cols, row):
                with col:
                    version_str = f'<span style="font-size:0.7rem; color:#64748B; margin-left:4px;">v{item.version}</span>' if item.version else ""
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #111827, #1F2937);
                        border: 1px solid #1F2937;
                        border-left: 3px solid {c1};
                        border-radius: 10px;
                        padding: 0.7rem 0.9rem;
                        margin-bottom: 8px;
                        transition: all 0.2s ease;
                    ">
                        <div style="
                            font-weight:600; font-size:0.88rem; color:#E2E8F0;
                            display:flex; align-items:center; gap:4px;
                        ">
                            {item.name}{version_str}
                        </div>
                        <div style="font-size:0.68rem; color:#475569; margin-top:3px;">
                            📄 {item.source_file}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ROW 3 — TOP FILES
# ─────────────────────────────────────────────────────────────────────────────

def _render_top_files(scan: RepoScan) -> None:
    if not scan.top_files:
        return

    import pandas as pd

    st.markdown("""
    <div style="font-size:1rem; font-weight:700; color:#E2E8F0; margin-bottom:0.8rem;
         letter-spacing:-0.01em;">
        📁 Largest Files
    </div>
    """, unsafe_allow_html=True)

    rows = []
    for i, f in enumerate(scan.top_files, 1):
        if f.byte_size >= 1024 * 1024:
            size_str = f"{f.byte_size / (1024*1024):.2f} MB"
        elif f.byte_size >= 1024:
            size_str = f"{f.byte_size / 1024:.1f} KB"
        else:
            size_str = f"{f.byte_size} B"
        rows.append({
            "#":        i,
            "File":     str(f.path).replace("\\", "/").replace("\\", "/"),
            "Language": f.language,
            "Size":     size_str,
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#":        st.column_config.NumberColumn("#", width="small"),
            "File":     st.column_config.TextColumn("File", width="large"),
            "Language": st.column_config.TextColumn("Language", width="medium"),
            "Size":     st.column_config.TextColumn("Size", width="small"),
        },
    )