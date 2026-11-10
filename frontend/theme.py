"""Smart-city visual theme: dark navy surfaces, blue accents, cards and status pills."""
from __future__ import annotations

import html

import plotly.graph_objects as go
import streamlit as st

NAVY = "#0a1628"
CARD = "#10213f"
CARD_BORDER = "#1d3560"
ACCENT = "#3b82f6"
TEXT = "#e6edf7"
TEXT2 = "#9fb0cc"
MUTED = "#6b7f9e"
GRID = "#1d3157"

# Categorical slots 1-3 (dark-surface steps), assigned to controllers in fixed order.
CONTROLLER_ORDER = ["fixed_time", "adaptive", "max_pressure"]
CONTROLLER_COLOR = {"fixed_time": "#3987e5", "adaptive": "#d95926", "max_pressure": "#199e70"}
CONTROLLER_LABEL = {"fixed_time": "Fixed-Time", "adaptive": "Adaptive (VAC)", "max_pressure": "Max-Pressure"}

# Traffic-signal & status colours (semantic, always shown with a text label)
SIGNAL_COLOR = {"G": "#22c55e", "g": "#22c55e", "y": "#facc15", "r": "#ef4444"}
LEVEL_COLOR = {"Free": "#22c55e", "Moderate": "#facc15", "Heavy": "#f97316", "Severe": "#ef4444"}
STATUS_COLOR = {"running": "#22c55e", "paused": "#facc15", "finished": "#3b82f6",
                "idle": "#6b7f9e", "error": "#ef4444", "completed": "#22c55e",
                "failed": "#ef4444", "queued": "#facc15"}

CSS = f"""
<style>
.block-container {{padding-top: 3.2rem; padding-bottom: 2rem; max-width: 1400px;}}
h1, h2, h3 {{letter-spacing: -0.01em;}}
.vac-header {{display:flex; align-items:center; gap:14px; margin-bottom: 0.4rem;}}
.vac-header .icon {{font-family: 'Material Symbols Rounded'; font-size: 34px; color:{ACCENT};
   background: rgba(59,130,246,0.12); border-radius: 12px; padding: 6px 8px;}}
.vac-header h1 {{font-size: 1.65rem; margin: 0; padding: 0; color:{TEXT};}}
.vac-header p {{margin: 0; color:{TEXT2}; font-size: 0.92rem;}}
.vac-card {{background:{CARD}; border:1px solid {CARD_BORDER}; border-radius:14px;
   padding:16px 18px; height:100%;}}
.vac-kpi-label {{color:{TEXT2}; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.06em;
   display:flex; align-items:center; gap:6px;}}
.vac-kpi-label .mi {{font-family:'Material Symbols Rounded'; font-size:18px; color:{ACCENT};}}
.vac-kpi-value {{color:{TEXT}; font-size:1.75rem; font-weight:650; margin-top:6px; line-height:1.15;}}
.vac-kpi-unit {{color:{TEXT2}; font-size:0.9rem; font-weight:400; margin-left:4px;}}
.vac-kpi-sub {{color:{MUTED}; font-size:0.78rem; margin-top:4px;}}
.vac-pill {{display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px;
   font-size:0.8rem; font-weight:600; border:1px solid; }}
.vac-dot {{width:8px; height:8px; border-radius:50%; display:inline-block;}}
.vac-reason {{background:#0c1a33; border-left:3px solid {ACCENT}; padding:10px 12px; border-radius:8px;
   color:{TEXT}; font-size:0.9rem;}}
.vac-section {{color:{TEXT2}; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.08em;
   margin: 1.2rem 0 0.4rem 0;}}
div[data-testid="stMetric"] {{background:{CARD}; border:1px solid {CARD_BORDER}; border-radius:14px; padding:12px 16px;}}
section[data-testid="stSidebar"] {{background:#081224; border-right:1px solid {CARD_BORDER};}}
</style>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded" rel="stylesheet"/>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str, icon: str) -> None:
    st.markdown(f"""<div class="vac-header"><span class="icon">{icon}</span>
        <div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div></div>""",
                unsafe_allow_html=True)


def kpi(label: str, value, unit: str = "", icon: str = "insights", sub: str = "") -> str:
    v = "—" if value is None else value
    return f"""<div class="vac-card"><div class="vac-kpi-label"><span class="mi">{icon}</span>{html.escape(label)}</div>
      <div class="vac-kpi-value">{v}<span class="vac-kpi-unit">{html.escape(unit)}</span></div>
      <div class="vac-kpi-sub">{html.escape(sub)}</div></div>"""


def kpi_row(items: list[str]) -> None:
    cols = st.columns(len(items))
    for c, item in zip(cols, items):
        c.markdown(item, unsafe_allow_html=True)


def pill(text: str, color: str) -> str:
    return (f'<span class="vac-pill" style="color:{color}; border-color:{color}55; background:{color}1a">'
            f'<span class="vac-dot" style="background:{color}"></span>{html.escape(text)}</span>')


def section(text: str) -> None:
    st.markdown(f'<div class="vac-section">{html.escape(text)}</div>', unsafe_allow_html=True)


def style_fig(fig: go.Figure, height: int = 320, title: str | None = None) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT2, size=12), margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        title=dict(text=title, x=0, font=dict(color=TEXT, size=14)) if title else None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=CARD, bordercolor=CARD_BORDER, font_color=TEXT),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    return fig


def fmt(v, digits: int = 1) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.{digits}f}"
    return f"{v:,}"
