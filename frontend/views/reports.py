"""G. Reports - experiment history, CSV export and PDF report."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend import api_client as api
from frontend.theme import CONTROLLER_LABEL, header, section


def render():
    header("Reports", "Stored experiment history with CSV and PDF export", "description")
    exps, err = api.try_get("/experiments", limit=2000)
    if exps is None:
        st.error(err, icon=":material/error:")
        return
    if not exps:
        st.info("No experiments stored yet.", icon=":material/info:")
        return
    df = pd.DataFrame(exps)
    df["controller_label"] = df["controller"].map(lambda c: CONTROLLER_LABEL.get(c, c))

    c = st.columns(3)
    sc = c[0].multiselect("Scenario", sorted(df["scenario"].unique()))
    ct = c[1].multiselect("Controller", sorted(df["controller"].unique()), format_func=CONTROLLER_LABEL.get)
    gp = c[2].multiselect("Comparison batch", sorted(df["group_id"].dropna().unique()))
    view = df
    if sc:
        view = view[view["scenario"].isin(sc)]
    if ct:
        view = view[view["controller"].isin(ct)]
    if gp:
        view = view[view["group_id"].isin(gp)]

    section(f"Experiment history ({len(view)} rows)")
    cols = ["id", "created_at", "mode", "group_id", "scenario", "controller_label", "seed", "duration",
            "avg_waiting_time", "avg_travel_time", "mean_queue_length", "max_queue_length", "throughput",
            "stops_per_vehicle", "phase_changes", "latency_mean_ms", "starvation_events", "teleports"]
    st.dataframe(view[cols], hide_index=True, width="stretch", height=380,
                 column_config={"controller_label": "Controller"})

    ids = ",".join(str(i) for i in view["id"].tolist())
    section("Export")
    b = st.columns(3)
    try:
        b[0].download_button("Download CSV", data=api.download(f"/reports/csv?ids={ids}"),
                             file_name="vac_experiments.csv", mime="text/csv", icon=":material/table:",
                             width="stretch")
    except api.ApiError as exc:
        b[0].error(str(exc))
    if b[1].button("Generate PDF report", icon=":material/picture_as_pdf:", width="stretch"):
        with st.spinner("Building PDF from stored results..."):
            try:
                st.session_state["pdf"] = api.download(f"/reports/pdf?ids={ids}")
            except api.ApiError as exc:
                st.error(str(exc))
    if st.session_state.get("pdf"):
        b[2].download_button("Download PDF", data=st.session_state["pdf"], file_name="vac_report.pdf",
                             mime="application/pdf", icon=":material/download:", width="stretch", type="primary")

    with st.expander("Delete an experiment"):
        del_id = st.selectbox("Experiment", view["id"].tolist())
        if st.button("Delete", icon=":material/delete:"):
            try:
                api.delete(f"/experiments/{del_id}")
                st.success(f"Deleted experiment #{del_id}")
                st.rerun()
            except api.ApiError as exc:
                st.error(str(exc))
