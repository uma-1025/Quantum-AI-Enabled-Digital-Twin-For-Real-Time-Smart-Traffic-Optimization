"""D. Adaptive control - what the controller selected, for how long, and why."""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend import api_client as api
from frontend.components import need_live_data
from frontend.theme import (ACCENT, CONTROLLER_LABEL, SIGNAL_COLOR, header, kpi, kpi_row, section,
                            style_fig)

MODE_COLOR = {"GREEN": SIGNAL_COLOR["G"], "YELLOW": SIGNAL_COLOR["y"], "ALL_RED": SIGNAL_COLOR["r"]}


def render():
    header("Adaptive Control", "Signal decisions, green times, demand, pressure and the reason behind "
                               "every decision", "tune")
    status, _ = api.try_get("/simulation/status")
    running = bool(status and status["status"] == "running")
    state0, _ = api.try_get("/simulation/state")
    tls_ids = sorted(state0["intersections"]) if state0 else ["C1", "C2", "C3", "C4"]
    tls = st.segmented_control("Intersection", tls_ids, default=tls_ids[0])

    @st.fragment(run_every=1 if running else None)
    def block():
        state = need_live_data("/simulation/state")
        if not state:
            return
        dec = api.get("/simulation/decisions", limit=150)
        it = state["intersections"][tls or tls_ids[0]]
        sig = it["signal"]
        names = it["phase_names"]
        latest = it.get("latest_decision") or {}
        mode_c = MODE_COLOR.get(sig["mode"], "#fff")
        kpi_row([
            kpi("Selected phase", sig["phase_name"], "", "alt_route",
                f"target: {names[sig['target_phase']]}" if sig["target_phase"] is not None else "no pending change"),
            kpi("Signal mode", f"<span style='color:{mode_c}'>{sig['mode']}</span>", "", "traffic",
                f"{sig['time_in_mode']:.0f}s in this mode"),
            kpi("Green time", f"{sig['elapsed_green']:.0f}", "s", "timer",
                "elapsed green of current phase"),
            kpi("Controller", CONTROLLER_LABEL.get(state["controller"], state["controller"]), "", "memory",
                f"safety rejections: {state['safety_rejections']}"),
        ])
        section("Why this decision")
        if latest:
            st.markdown(f"<div class='vac-reason'><b>[{latest['category']}] t={latest['sim_time']:.0f}s</b> — "
                        f"{html.escape(latest['reason'])}</div>", unsafe_allow_html=True)
        else:
            st.caption("Signal is in an amber / all-red transition; the controller decides again once the new "
                       "green starts.")

        c1, c2, c3 = st.columns(3)
        colors = [ACCENT if i == sig["phase_index"] else "#4b5f82" for i in range(len(names))]
        for col, key, title in [(c1, "phase_demand", "Demand (sum of lane congestion scores)"),
                                (c2, "phase_pressure", "Max-pressure (in-queue − out-queue)"),
                                (c3, "phase_queue", "Queued vehicles per phase")]:
            fig = go.Figure(go.Bar(x=names, y=it[key], marker=dict(color=colors, cornerradius=4),
                                   hovertemplate="%{x}: %{y:.1f}<extra></extra>"))
            col.plotly_chart(style_fig(fig, 260, title), width="stretch")
        wait = sig.get("demand_wait") or [0] * len(names)
        st.caption("Highlighted bar = phase currently served. Waiting-on-red time per phase: " +
                   ", ".join(f"{n} {w:.0f}s" for n, w in zip(names, wait)))

        c4, c5 = st.columns(2)
        with c4:
            section("Decision log (changes of decision type and every switch)")
            d = pd.DataFrame([x for x in dec["decisions"] if x["tls_id"] == (tls or tls_ids[0])])
            if not d.empty:
                st.dataframe(d[["sim_time", "category", "action", "from_phase", "to_phase", "accepted", "reason"]],
                             hide_index=True, width="stretch", height=330)
        with c5:
            section("Signal transitions (green → amber → all-red → green)")
            t = pd.DataFrame([x for x in dec["transitions"] if x["tls_id"] == (tls or tls_ids[0])])
            if not t.empty:
                st.dataframe(t[["time", "mode", "phase", "state", "note"]], hide_index=True, width="stretch",
                             height=330)
    block()
