"""E. Controller comparison - identical scenario/seed/duration for each controller."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend import api_client as api
from frontend.components import app_config
from frontend.theme import (CONTROLLER_COLOR, CONTROLLER_LABEL, CONTROLLER_ORDER, STATUS_COLOR, header,
                            pill, section, style_fig)

METRICS = [("avg_waiting_time", "Average waiting time (s)", True),
           ("avg_travel_time", "Average travel time (s)", True),
           ("mean_queue_length", "Mean queue per lane (veh)", True),
           ("max_queue_length", "Max lane queue (veh)", True),
           ("throughput", "Throughput (vehicles)", False),
           ("stops_per_vehicle", "Stops per vehicle", True),
           ("phase_changes", "Phase changes", None),
           ("latency_mean_ms", "Controller latency (ms)", True),
           ("starvation_events", "Starvation events", True)]


def show_results(agg: list[dict]):
    agg = sorted(agg, key=lambda a: CONTROLLER_ORDER.index(a["controller"]) if a["controller"] in CONTROLLER_ORDER else 9)
    runs = {a["runs"] for a in agg}
    st.caption(f"Mean over {', '.join(map(str, runs))} seed(s) per controller; error bars = standard deviation "
               "across seeds.")
    cols = st.columns(3)
    for i, (m, title, _) in enumerate(METRICS):
        fig = go.Figure(go.Bar(
            x=[CONTROLLER_LABEL.get(a["controller"], a["controller"]) for a in agg],
            y=[a[m] for a in agg],
            error_y=dict(type="data", array=[a.get(f"{m}_std") or 0 for a in agg], color="#9fb0cc", thickness=1),
            marker=dict(color=[CONTROLLER_COLOR.get(a["controller"], "#888") for a in agg], cornerradius=4),
            hovertemplate="%{x}: %{y:.3f}<extra></extra>"))
        cols[i % 3].plotly_chart(style_fig(fig, 260, title), width="stretch")

    section("Results table and change vs Fixed-Time (measured, not assumed)")
    rows = []
    for a in agg:
        r = {"Controller": CONTROLLER_LABEL.get(a["controller"], a["controller"]), "Runs": a["runs"]}
        for m, title, _ in METRICS:
            r[title] = a[m]
        rows.append(r)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    if any(a["controller"] == "fixed_time" for a in agg):
        lines = []
        for a in agg:
            if a["controller"] == "fixed_time":
                continue
            for m, title, lower_better in METRICS:
                pct = (a.get("vs_fixed_time_pct") or {}).get(m)
                if pct is None or lower_better is None:
                    continue
                better = (pct < 0) if lower_better else (pct > 0)
                word = "better" if better else ("worse" if pct != 0 else "equal")
                lines.append({"Controller": CONTROLLER_LABEL.get(a["controller"]), "Metric": title,
                              "Change vs Fixed-Time %": pct, "Verdict on this data": word})
        if lines:
            st.dataframe(pd.DataFrame(lines), hide_index=True, width="stretch")
        st.caption("Verdicts describe only these runs. With a single seed, differences may be due to chance – "
                   "use 3+ seeds and check the standard deviations before claiming an improvement.")


def render():
    header("Controller Comparison", "Fixed-Time vs Adaptive (VAC) vs Max-Pressure on identical traffic",
           "compare_arrows")
    try:
        cfg = app_config()
    except api.ApiError as exc:
        st.error(str(exc), icon=":material/error:")
        return

    with st.form("compare"):
        c = st.columns([1, 2, 1, 1])
        scenario = c[0].selectbox("Scenario", list(cfg["scenarios"]), index=1,
                                  format_func=lambda k: cfg["scenarios"][k]["label"])
        ctrls = c[1].multiselect("Controllers", list(cfg["controllers"]), default=list(cfg["controllers"]),
                                 format_func=lambda k: cfg["controllers"][k]["label"])
        seeds_txt = c[2].text_input("Seeds (comma separated)", "1,2,3")
        duration = c[3].number_input("Duration (s)", 60, 14400, 1800, step=60)
        submitted = st.form_submit_button("Run comparison", icon=":material/play_arrow:", type="primary")
    if submitted:
        try:
            seeds = [int(x) for x in seeds_txt.split(",") if x.strip()]
            job = api.post("/experiments/compare", {"scenario": scenario, "controllers": ctrls,
                                                    "seeds": seeds, "duration": int(duration)})
            st.session_state["job_id"] = job["job_id"]
        except ValueError:
            st.error("Seeds must be integers, e.g. 1,2,3")
        except api.ApiError as exc:
            st.error(str(exc), icon=":material/error:")

    job_id = st.session_state.get("job_id")
    if job_id:
        @st.fragment(run_every=2)
        def progress():
            job, err = api.try_get(f"/experiments/jobs/{job_id}")
            if not job:
                st.error(err)
                return
            st.markdown(pill(f"Job {job_id}: {job['status']}", STATUS_COLOR.get(job["status"], "#888")),
                        unsafe_allow_html=True)
            st.progress(job["progress"], text=f"{job['progress']*100:.0f}% · {job['current'] or ''}")
            if job["status"] == "failed":
                st.error(job["error"])
            if job["status"] in ("completed", "failed"):
                st.session_state["last_group"] = job_id
                st.session_state.pop("job_id", None)
                st.rerun()
        progress()

    section("Results")
    exps, _ = api.try_get("/experiments", limit=2000)
    groups = []
    if exps:
        df = pd.DataFrame(exps)
        df = df[df["group_id"].notna()]
        for g, sub in df.groupby("group_id", sort=False):
            groups.append((g, f"{g} · {sub['scenario'].iloc[0]} · {sub['duration'].iloc[0]}s · "
                              f"seeds {sorted(sub['seed'].unique().tolist())} · {len(sub)} runs"))
    if not groups:
        st.info("No comparison has been run yet. Choose settings above and press **Run comparison**.",
                icon=":material/info:")
        return
    keys = [g for g, _ in groups]
    default = keys.index(st.session_state["last_group"]) if st.session_state.get("last_group") in keys else 0
    sel = st.selectbox("Comparison batch", keys, index=default, format_func=dict(groups).get)
    agg = api.get(f"/experiments/groups/{sel}/aggregate")
    show_results(agg)
