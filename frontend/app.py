"""Streamlit dashboard entry point.

Run (from the project root, with the backend already running):
    streamlit run frontend/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from frontend import api_client as api  # noqa: E402
from frontend.theme import STATUS_COLOR, apply_theme, pill  # noqa: E402
from frontend.views import (adaptive, analytics, comparison, home, live, monitoring,  # noqa: E402
                            reports)

st.set_page_config(page_title="VAC Adaptive Traffic Control", page_icon=":material/traffic:",
                   layout="wide", initial_sidebar_state="expanded")
apply_theme()

pages = [
    st.Page(home.render, title="Home Dashboard", icon=":material/dashboard:", default=True),
    st.Page(live.render, title="Live Simulation", icon=":material/traffic:", url_path="live"),
    st.Page(monitoring.render, title="Traffic Monitoring", icon=":material/monitoring:", url_path="monitoring"),
    st.Page(adaptive.render, title="Adaptive Control", icon=":material/tune:", url_path="adaptive"),
    st.Page(comparison.render, title="Controller Comparison", icon=":material/compare_arrows:", url_path="comparison"),
    st.Page(analytics.render, title="Analytics", icon=":material/insights:", url_path="analytics"),
    st.Page(reports.render, title="Reports", icon=":material/description:", url_path="reports"),
]
nav = st.navigation(pages)

with st.sidebar:
    st.markdown("### :material/hub: VAC Traffic Control")
    st.caption("Epic 1 · SUMO + TraCI + FastAPI + Streamlit")
    health, err = api.try_get("/health")
    if health is None:
        st.markdown(pill("Backend offline", STATUS_COLOR["error"]), unsafe_allow_html=True)
        st.caption(err)
    else:
        st.markdown(pill("Backend online", STATUS_COLOR["running"]), unsafe_allow_html=True)
        sumo_ok = health.get("sumo") == "ok"
        st.markdown(pill("SUMO " + ("ready" if sumo_ok else "missing"),
                         STATUS_COLOR["running" if sumo_ok else "error"]), unsafe_allow_html=True)
        ls = health.get("live_status", "idle")
        st.markdown(pill(f"Simulation: {ls}", STATUS_COLOR.get(ls, "#6b7f9e")), unsafe_allow_html=True)
        st.caption(health.get("sumo_version", ""))

nav.run()
