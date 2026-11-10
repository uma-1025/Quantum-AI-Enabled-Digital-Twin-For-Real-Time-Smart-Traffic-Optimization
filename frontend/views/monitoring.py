"""C. Traffic monitoring - lane-wise measurements and congestion scores."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from frontend import api_client as api
from frontend.components import need_live_data
from frontend.theme import LEVEL_COLOR, fmt, header, kpi, kpi_row, section, style_fig


def _level(score: float) -> str:
    return "Free" if score < 25 else "Moderate" if score < 50 else "Heavy" if score < 75 else "Severe"


def render():
    header("Traffic Monitoring", "Lane-wise measurements collected from SUMO every simulation second",
           "monitoring")
    status, _ = api.try_get("/simulation/status")
    running = bool(status and status["status"] == "running")

    @st.fragment(run_every=2 if running else None)
    def block():
        state = need_live_data("/simulation/state")
        if not state:
            return
        lanes = [l for i in state["intersections"].values() for l in i["lanes"]]
        df = pd.DataFrame(lanes)
        df["level"] = df["congestion_score"].map(_level)
        bl = state["busiest_lane"]
        kpi_row([
            kpi("Busiest lane", bl["lane_id"], "", "warning",
                f"{bl['tls_id']} · approach {bl['approach']} · score {bl['congestion_score']:.1f}"),
            kpi("Its queue", bl["queue_length"], "veh", "format_list_numbered",
                f"waiting {bl['avg_waiting_time']:.0f}s avg"),
            kpi("Network congestion", f"{state['congestion_index']:.1f}", "/100", "speed",
                f"mean of all lanes · condition: {state['congestion_level']}"),
            kpi("Monitored lanes", len(df), "", "view_week", f"t = {state['sim_time']:.0f}s"),
        ])

        tls = st.segmented_control("Intersection", ["All"] + sorted(state["intersections"]), default="All")
        view = df if tls in (None, "All") else df[df["tls_id"] == tls]

        c1, c2 = st.columns([3, 2])
        with c1:
            top = view.sort_values("congestion_score", ascending=False).head(16)
            fig = go.Figure(go.Bar(
                x=top["congestion_score"], y=top["lane_id"], orientation="h",
                marker=dict(color=[LEVEL_COLOR[l] for l in top["level"]], cornerradius=4),
                customdata=top[["queue_length", "occupancy", "avg_waiting_time", "level"]],
                hovertemplate="%{y}<br>score %{x:.1f} (%{customdata[3]})<br>queue %{customdata[0]}"
                              "<br>occupancy %{customdata[1]:.1f}%<br>wait %{customdata[2]:.1f}s<extra></extra>"))
            fig.update_yaxes(autorange="reversed")
            fig.update_xaxes(range=[0, 100], title="congestion score (0-100)")
            st.plotly_chart(style_fig(fig, 430, "Most congested lanes"), width="stretch")
        with c2:
            appr = pd.DataFrame([{"tls": t, **i["approach_scores"]} for t, i in state["intersections"].items()]
                                ).set_index("tls")[["N", "E", "S", "W"]]
            hm = px.imshow(appr, text_auto=".0f", zmin=0, zmax=100, aspect="auto",
                           color_continuous_scale=[[0, "#10213f"], [1, "#5b9bf0"]],
                           labels=dict(x="approach", y="intersection", color="score"))
            st.plotly_chart(style_fig(hm, 430, "Approach congestion (mean lane score)"), width="stretch")

        section("Lane table")
        show = view[["lane_id", "tls_id", "approach", "vehicle_count", "queue_length", "occupancy",
                     "mean_speed", "avg_waiting_time", "arrival_rate", "congestion_score", "queue_pressure",
                     "level"]].sort_values("congestion_score", ascending=False)
        st.dataframe(show, hide_index=True, width="stretch", height=380, column_config={
            "lane_id": "Lane", "tls_id": "Intersection", "approach": "Approach",
            "vehicle_count": "Vehicles", "queue_length": "Queue",
            "occupancy": st.column_config.NumberColumn("Occupancy %", format="%.1f"),
            "mean_speed": st.column_config.NumberColumn("Speed m/s", format="%.2f"),
            "avg_waiting_time": st.column_config.NumberColumn("Avg wait s", format="%.1f"),
            "arrival_rate": st.column_config.NumberColumn("Arrivals /min", format="%.1f"),
            "congestion_score": st.column_config.ProgressColumn("Congestion", min_value=0, max_value=100,
                                                                format="%.1f"),
            "queue_pressure": st.column_config.NumberColumn("Queue pressure", format="%.1f"),
            "level": "Level"})
        st.caption("Congestion score = 100 × (0.40·queue/capacity + 0.20·occupancy + 0.25·wait/60s + "
                   "0.15·arrivals/12 per min). Queue pressure = lane queue − mean queue on the lanes it feeds.")
    block()
