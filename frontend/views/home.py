"""A. Home dashboard - headline KPIs of the running simulation (all from the backend)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend import api_client as api
from frontend.components import network_geometry
from frontend.theme import (CONTROLLER_LABEL, LEVEL_COLOR, STATUS_COLOR, fmt, header, kpi, kpi_row,
                            pill, section)


def render():
    header("Home Dashboard", "Real-time overview of the SUMO traffic network", "dashboard")
    status, err = api.try_get("/simulation/status")
    if status is None:
        st.error(err, icon=":material/error:")
        return

    try:
        n_tls = len(network_geometry()["tls"])
    except api.ApiError:
        n_tls = None

    @st.fragment(run_every=2 if status["status"] == "running" else None)
    def live_block():
        state, _ = api.try_get("/simulation/state")
        stt = api.get("/simulation/status")
        s = stt["status"]
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(pill(f"Simulation {s.upper()}", STATUS_COLOR.get(s, "#6b7f9e")), unsafe_allow_html=True)
        with c2:
            if stt["duration"]:
                st.progress(min(stt["progress"], 1.0), text=f"t = {stt['sim_time']:.0f} / {stt['duration']} s")
        if not state:
            st.info("No simulation is running. Go to **Live Simulation** and press **Start** to "
                    "populate these indicators with live SUMO data.", icon=":material/info:")
            kpi_row([kpi("Active intersections", n_tls, "", "traffic", "signalized junctions in the network"),
                     kpi("Controller running", "None", "", "memory", "")])
            return
        k = state["kpis"]
        level = state["congestion_level"]
        kpi_row([
            kpi("Total vehicles", fmt(k["vehicles_departed"]), "", "directions_car",
                f"{k['vehicles_in_network']} in network now"),
            kpi("Average waiting time", fmt(k["avg_waiting_time"]), "s", "hourglass_top",
                "completed trips"),
            kpi("Average queue length", fmt(k["avg_queue_per_lane"], 2), "veh/lane", "format_list_numbered",
                f"{k['current_total_queue']} vehicles queued now"),
            kpi("Throughput", fmt(k["vehicles_completed"]), "veh", "trending_up", "trips completed"),
        ])
        st.write("")
        kpi_row([
            kpi("Traffic condition", f"<span style='color:{LEVEL_COLOR.get(level, '#fff')}'>{level}</span>", "",
                "speed", f"worst-approach score {state['condition_score']:.1f}/100 · lane index {state['congestion_index']:.1f}"),
            kpi("Active intersections", state["active_intersections"], "", "traffic", "signalized junctions"),
            kpi("Controller running", CONTROLLER_LABEL.get(state["controller"], state["controller"]), "",
                "memory", f"scenario: {state['scenario']}"),
            kpi("Phase changes", fmt(k["phase_changes"]), "", "sync_alt",
                f"starvation events: {k['starvation_events']}"),
        ])
        section("Intersections")
        rows = []
        for tid, i in state["intersections"].items():
            rows.append({"Intersection": tid, "Phase": i["signal"]["phase_name"], "Mode": i["signal"]["mode"],
                         "Green (s)": i["signal"]["elapsed_green"],
                         "Most congested approach": i["most_congested_approach"],
                         "Condition": i["congestion_level"],
                         "Queued": sum(i["phase_queue"])})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    live_block()

    section("Latest stored experiments")
    exps, e2 = api.try_get("/experiments", limit=5)
    if exps:
        df = pd.DataFrame(exps)[["id", "created_at", "mode", "scenario", "controller", "seed", "duration",
                                 "avg_waiting_time", "throughput", "mean_queue_length"]]
        df["controller"] = df["controller"].map(lambda c: CONTROLLER_LABEL.get(c, c))
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.caption("No experiments stored yet.")
