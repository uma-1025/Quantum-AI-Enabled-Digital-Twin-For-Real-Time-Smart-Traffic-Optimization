"""B. Live traffic simulation - controls + live map of vehicles and signal colours."""
from __future__ import annotations

import streamlit as st

from frontend import api_client as api
from frontend.components import app_config, network_figure, network_geometry
from frontend.theme import CONTROLLER_LABEL, STATUS_COLOR, header, kpi, kpi_row, pill, section


def _call(fn, *a):
    try:
        fn(*a)
        return True
    except api.ApiError as exc:
        st.error(str(exc), icon=":material/error:")
        return False


def render():
    header("Live Traffic Simulation", "SUMO simulation streamed through TraCI → FastAPI → dashboard",
           "traffic")
    try:
        cfg = app_config()
        net = network_geometry()
    except api.ApiError as exc:
        st.error(str(exc), icon=":material/error:")
        return
    status = api.get("/simulation/status")
    s = status["status"]

    with st.container(border=True):
        c = st.columns([1.1, 1.3, 0.8, 0.9, 0.9, 0.8])
        scenario = c[0].selectbox("Traffic scenario", list(cfg["scenarios"]), index=1,
                                  format_func=lambda k: cfg["scenarios"][k]["label"])
        controller = c[1].selectbox("Controller", list(cfg["controllers"]), index=1,
                                    format_func=lambda k: cfg["controllers"][k]["label"])
        seed = c[2].number_input("Random seed", 0, 99999, cfg["defaults"]["seed"])
        duration = c[3].number_input("Duration (s)", 60, 14400, 1800, step=60)
        speed = c[4].select_slider("Speed (sim s / s)", [1, 2, 5, 10, 20, 50, 100], value=10)
        gui = c[5].checkbox("Open sumo-gui", value=False,
                            help="Also open SUMO's own GUI window on the computer running the backend.")
        b = st.columns(5)
        if b[0].button("Start", icon=":material/play_arrow:", type="primary", width="stretch",
                       disabled=s in ("running", "paused")):
            if _call(api.post, "/simulation/start", {"scenario": scenario, "controller": controller,
                                                     "seed": int(seed), "duration": int(duration),
                                                     "speed": float(speed), "gui": gui}):
                st.rerun()
        if b[1].button("Pause", icon=":material/pause:", width="stretch", disabled=s != "running"):
            _call(api.post, "/simulation/pause") and st.rerun()
        if b[2].button("Resume", icon=":material/resume:", width="stretch", disabled=s != "paused"):
            _call(api.post, "/simulation/resume") and st.rerun()
        if b[3].button("Reset", icon=":material/restart_alt:", width="stretch"):
            _call(api.post, "/simulation/reset") and st.rerun()
        if b[4].button("Apply speed", icon=":material/speed:", width="stretch", disabled=s not in ("running", "paused")):
            _call(api.post, "/simulation/speed", {"speed": float(speed)})

    if status.get("error"):
        st.error(status["error"], icon=":material/error:")

    @st.fragment(run_every=1 if s == "running" else None)
    def live_view():
        stt = api.get("/simulation/status")
        if stt["status"] != s:
            # status changed (finished / error / paused elsewhere): redraw the whole page so the
            # buttons and any error message reflect the new state immediately
            st.rerun()
        snap, err = api.try_get("/simulation/snapshot")
        cfgd = stt.get("config") or {}
        ctrl = CONTROLLER_LABEL.get(cfgd.get("controller"), "—")
        cols = st.columns([1, 3])
        cols[0].markdown(pill(stt["status"].upper(), STATUS_COLOR.get(stt["status"], "#6b7f9e")),
                         unsafe_allow_html=True)
        if stt["duration"]:
            cols[1].progress(min(stt["progress"], 1.0),
                             text=f"Simulation time {stt['sim_time']:.0f} s of {stt['duration']} s")
        kpi_row([
            kpi("Vehicles on map", len(snap["vehicles"]) if snap else 0, "", "directions_car"),
            kpi("Simulation time", f"{stt['sim_time']:.0f}", "s", "schedule"),
            kpi("Active controller", ctrl, "", "memory", cfgd.get("scenario", "")),
            kpi("Vehicles scheduled", stt.get("loaded_vehicles", 0), "", "route", f"seed {cfgd.get('seed', '—')}"),
        ])
        if stt["status"] == "finished":
            st.success(f"Run finished and saved as experiment #{stt['experiment_id']}. "
                       "See Analytics / Reports.", icon=":material/check_circle:")
        st.plotly_chart(network_figure(net, snap), width="stretch", config={"displayModeBar": False})
        if snap:
            section("Signal states (G = green, y = amber, r = red; one character per controlled movement)")
            sc = st.columns(len(snap["signals"]))
            for col, (tid, sig) in zip(sc, sorted(snap["signals"].items())):
                col.markdown(f"**{tid}** · {sig['phase']} · {sig['mode']}  \n`{sig['state']}`")
        elif stt["status"] == "idle":
            st.caption("Press **Start** to launch SUMO. Squares at stop lines show the signal colour of "
                       "each approach lane; dots are vehicles coloured by speed.")
    live_view()
