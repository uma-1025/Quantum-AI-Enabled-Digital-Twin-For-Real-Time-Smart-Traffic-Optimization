"""CSV and PDF report generation from stored experiment results.

PDF is built with Matplotlib (PdfPages): a title + summary table page, a metric
comparison page and a time-series page. Every value comes from the database.
"""
from __future__ import annotations

import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from backend.database import db  # noqa: E402

# Categorical slots 1-3 (light surface) in fixed controller order.
CONTROLLER_ORDER = ["fixed_time", "adaptive", "max_pressure"]
CONTROLLER_LABEL = {"fixed_time": "Fixed-Time", "adaptive": "Adaptive (VAC)", "max_pressure": "Max-Pressure"}
CONTROLLER_COLOR = {"fixed_time": "#2a78d6", "adaptive": "#eb6834", "max_pressure": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

CSV_COLUMNS = ["id", "created_at", "group_id", "mode", "scenario", "controller", "seed", "duration",
               "status", "vehicles_departed", "throughput", "throughput_per_hour", "vehicles_remaining",
               "avg_waiting_time", "avg_travel_time", "stops_per_vehicle", "mean_queue_length",
               "max_queue_length", "mean_total_queue", "avg_speed", "phase_changes", "latency_mean_ms",
               "latency_p95_ms", "latency_max_ms", "starvation_events", "teleports", "safety_rejections",
               "wall_time_s", "sumo_version"]

TABLE_METRICS = [("avg_waiting_time", "Avg waiting (s)"), ("avg_travel_time", "Avg travel (s)"),
                 ("mean_queue_length", "Mean queue/lane"), ("max_queue_length", "Max queue"),
                 ("throughput", "Throughput"), ("stops_per_vehicle", "Stops/veh"),
                 ("phase_changes", "Phase changes"), ("latency_mean_ms", "Latency (ms)"),
                 ("starvation_events", "Starvation")]


def experiments_frame(ids: list[int] | None = None) -> pd.DataFrame:
    rows = db.list_experiments(limit=10000)
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=CSV_COLUMNS)
    if ids:
        df = df[df["id"].isin(ids)]
    return df[[c for c in CSV_COLUMNS if c in df.columns]].sort_values("id")


def build_csv(ids: list[int] | None = None) -> bytes:
    return experiments_frame(ids).to_csv(index=False).encode("utf-8")


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    ax.spines[["top", "right"]].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def build_pdf(ids: list[int] | None = None) -> bytes:
    df = experiments_frame(ids)
    if df.empty:
        raise LookupError("No experiments found for the report. Run an experiment first.")
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # ---- Page 1: title + table
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.05, 0.93, "VAC-Inspired Adaptive Traffic Control System - Experiment Report",
                 fontsize=16, weight="bold", color=INK)
        fig.text(0.05, 0.895, f"Generated {datetime.now():%Y-%m-%d %H:%M}  |  {len(df)} experiment(s)  |  "
                              f"all values measured in SUMO via TraCI", fontsize=9, color=INK2)
        scen = ", ".join(sorted(df["scenario"].unique()))
        seeds = ", ".join(str(s) for s in sorted(df["seed"].unique()))
        durs = ", ".join(str(d) for d in sorted(df["duration"].unique()))
        fig.text(0.05, 0.865, f"Scenario(s): {scen}   Seed(s): {seeds}   Duration(s): {durs} s",
                 fontsize=9, color=INK2)
        ax = fig.add_axes([0.03, 0.08, 0.94, 0.75])
        ax.axis("off")
        show = df.head(28)
        cols = ["id", "controller", "scenario", "seed"] + [m for m, _ in TABLE_METRICS]
        header = ["ID", "Controller", "Scenario", "Seed"] + [l for _, l in TABLE_METRICS]
        cell = []
        for _, r in show.iterrows():
            row = []
            for c in cols:
                v = r.get(c)
                if c == "controller":
                    v = CONTROLLER_LABEL.get(v, v)
                elif isinstance(v, float):
                    v = "-" if pd.isna(v) else (f"{v:.4f}" if c == "latency_mean_ms" else f"{v:.2f}")
                row.append(str(v))
            cell.append(row)
        t = ax.table(cellText=cell, colLabels=header, loc="upper center", cellLoc="center")
        t.auto_set_font_size(False)
        t.set_fontsize(7)
        t.scale(1, 1.25)
        for (r, c), cobj in t.get_celld().items():
            cobj.set_edgecolor(GRID)
            if r == 0:
                cobj.set_facecolor("#0f1f3d")
                cobj.get_text().set_color("white")
        if len(df) > 28:
            fig.text(0.05, 0.04, f"(first 28 of {len(df)} rows shown - full data in the CSV export)",
                     fontsize=8, color=INK2)
        pdf.savefig(fig)
        plt.close(fig)

        # ---- Page 2: mean metric per controller
        agg = df.groupby("controller")[[m for m, _ in TABLE_METRICS]].mean(numeric_only=True)
        order = [c for c in CONTROLLER_ORDER if c in agg.index] + [c for c in agg.index if c not in CONTROLLER_ORDER]
        agg = agg.loc[order]
        fig, axes = plt.subplots(3, 3, figsize=(11.69, 8.27))
        fig.suptitle("Controller comparison (mean over selected experiments)", x=0.05, ha="left",
                     fontsize=13, weight="bold", color=INK)
        for ax, (m, label) in zip(axes.flat, TABLE_METRICS):
            vals = agg[m].values
            colors = [CONTROLLER_COLOR.get(c, "#888888") for c in agg.index]
            bars = ax.bar([CONTROLLER_LABEL.get(c, c) for c in agg.index], vals, color=colors, width=0.6)
            for b, v in zip(bars, vals):
                if not pd.isna(v):
                    ax.annotate(f"{v:.4f}" if m == "latency_mean_ms" else (f"{v:.2f}" if v < 100 else f"{v:.0f}"), (b.get_x() + b.get_width() / 2, v),
                                ha="center", va="bottom", fontsize=7, color=INK)
            _style(ax, label)
            ax.tick_params(axis="x", labelsize=7)
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        pdf.savefig(fig)
        plt.close(fig)

        # ---- Page 3: time series
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        fig.suptitle("Time series (one line per experiment)", x=0.05, ha="left", fontsize=13,
                     weight="bold", color=INK)
        specs = [("total_queue", "Total queued vehicles"), ("avg_waiting", "Mean accumulated wait of vehicles in network (s)"),
                 ("throughput", "Cumulative throughput (vehicles)"), ("avg_speed", "Mean speed (m/s)")]
        for _, r in df.head(9).iterrows():
            ts = pd.DataFrame(db.get_timeseries(int(r["id"])))
            if ts.empty:
                continue
            for ax, (col, _) in zip(axes.flat, specs):
                ax.plot(ts["sim_time"], ts[col], linewidth=1.5,
                        color=CONTROLLER_COLOR.get(r["controller"], "#888888"),
                        label=f"#{r['id']} {CONTROLLER_LABEL.get(r['controller'], r['controller'])} s{r['seed']}")
        for ax, (_, title) in zip(axes.flat, specs):
            _style(ax, title)
            ax.set_xlabel("simulation time (s)", fontsize=8, color=INK2)
        axes.flat[0].legend(fontsize=7, frameon=False)
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        pdf.savefig(fig)
        plt.close(fig)
    return buf.getvalue()
