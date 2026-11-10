"""F. Analytics - interactive time series for the live run or stored experiments."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend import api_client as api
from frontend.theme import CONTROLLER_COLOR, CONTROLLER_LABEL, header, style_fig

CHARTS = [("avg_waiting", "Average waiting time of vehicles in network (s)"),
          ("total_queue", "Queue length – total halted vehicles"),
          ("throughput", "Vehicle throughput – cumulative completed trips"),
          ("avg_speed", "Average speed (m/s)"),
          ("congestion_index", "Congestion over time (index 0-100)"),
          ("phase_changes", "Signal phase changes (cumulative)"),
          ("latency_ms", "Controller computation time (ms, mean per 10 s)")]
DASHES = ["solid", "dash", "dot", "dashdot", "longdash"]


def render():
    header("Analytics", "Interactive performance graphs built from recorded simulation data", "insights")
    source = st.segmented_control("Data source", ["Stored experiments", "Current live run"],
                                  default="Stored experiments")
    series: list[tuple[str, str, pd.DataFrame]] = []
    if source == "Current live run":
        hist, err = api.try_get("/simulation/history")
        if not hist:
            st.info("No live run data. Start one on **Live Simulation**.", icon=":material/info:")
            return
        cfg = api.get("/simulation/status").get("config") or {}
        series.append((f"Live · {CONTROLLER_LABEL.get(cfg.get('controller'), '')}", cfg.get("controller", ""),
                       pd.DataFrame(hist["timeseries"])))
    else:
        exps, err = api.try_get("/experiments", limit=500)
        if not exps:
            st.info("No stored experiments yet. Run a comparison or finish a live run.", icon=":material/info:")
            return
        opts = {e["id"]: f"#{e['id']} {CONTROLLER_LABEL.get(e['controller'], e['controller'])} · "
                         f"{e['scenario']} · seed {e['seed']} · {e['duration']}s" for e in exps}
        short = {e["id"]: f"#{e['id']} {CONTROLLER_LABEL.get(e['controller'], e['controller'])} s{e['seed']}"
                 for e in exps}
        default = [e["id"] for e in exps[:3]]
        picked = st.multiselect("Experiments", list(opts), default=default, format_func=opts.get)
        ctrl_of = {e["id"]: e["controller"] for e in exps}
        for i in picked:
            series.append((short[i], ctrl_of[i], pd.DataFrame(api.get(f"/experiments/{i}/timeseries"))))

    if not series or all(s[2].empty for s in series):
        st.caption("Nothing to plot yet.")
        return
    seen: dict[str, int] = {}
    styled = []
    for name, ctrl, df in series:
        k = seen.get(ctrl, 0)
        seen[ctrl] = k + 1
        styled.append((name, ctrl, df, DASHES[k % len(DASHES)]))

    cols = st.columns(2)
    for idx, (col, title) in enumerate(CHARTS):
        fig = go.Figure()
        for name, ctrl, df, dash in styled:
            if df.empty or col not in df:
                continue
            fig.add_trace(go.Scatter(x=df["sim_time"], y=df[col], name=name, mode="lines",
                                     line=dict(color=CONTROLLER_COLOR.get(ctrl, "#9fb0cc"), width=2, dash=dash),
                                     hovertemplate="t=%{x:.0f}s: %{y:.2f}<extra>" + name + "</extra>"))
        style_fig(fig, 330, title)
        fig.update_layout(hovermode="x unified", margin=dict(l=10, r=10, t=40, b=10),
                          legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0))
        cols[idx % 2].plotly_chart(fig, width="stretch")
    st.caption("x-axis = simulation time in seconds. Colour = controller (Fixed-Time blue, Adaptive orange, Max-Pressure green); line style "
               "distinguishes several runs of the same controller.")
