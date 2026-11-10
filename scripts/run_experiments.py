"""Run repeated, fair controller comparisons from the command line and save a results report.

Example (from the project root):
    python scripts/run_experiments.py --scenarios low medium high --seeds 1 2 3 --duration 1800

Results are stored in the database (visible in the dashboard) and written to
docs/results/experiment_results.md and .json. Nothing is estimated: every value is
measured from SUMO.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.evaluation.experiment import aggregate, run_single  # noqa: E402
from backend.simulation.sumo_utils import sumo_version  # noqa: E402

LABEL = {"fixed_time": "Fixed-Time", "adaptive": "Adaptive (VAC)", "max_pressure": "Max-Pressure"}
COLS = [("avg_waiting_time", "Avg waiting (s)"), ("avg_travel_time", "Avg travel (s)"),
        ("mean_queue_length", "Mean queue/lane"), ("max_queue_length", "Max lane queue"),
        ("throughput", "Throughput"), ("stops_per_vehicle", "Stops/veh"),
        ("phase_changes", "Phase changes"), ("latency_mean_ms", "Latency ms"),
        ("starvation_events", "Starvation")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="+", default=["low", "medium", "high"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3])
    ap.add_argument("--duration", type=int, default=1800)
    ap.add_argument("--controllers", nargs="+", default=["fixed_time", "adaptive", "max_pressure"])
    ap.add_argument("--out", default=str(ROOT / "docs" / "results"))
    ap.add_argument("--render-only", action="store_true",
                    help="only rebuild the markdown from an existing experiment_results.json")
    a = ap.parse_args()
    if a.render_only:
        out = Path(a.out)
        write_markdown(json.loads((out / "experiment_results.json").read_text()), out)
        return

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"generated": datetime.now().isoformat(timespec="seconds"), "sumo": sumo_version(),
              "duration": a.duration, "seeds": a.seeds, "scenarios": {}}
    for sc in a.scenarios:
        group = f"{sc}_{uuid.uuid4().hex[:6]}"
        rows = []
        for seed in a.seeds:
            for ctrl in a.controllers:
                t0 = time.time()
                r = run_single(sc, ctrl, seed, a.duration, group_id=group)
                rows.append(r)
                print(f"[{sc:6}] seed {seed} {ctrl:13} wait={r['avg_waiting_time']}s "
                      f"thr={r['throughput']} ({time.time() - t0:.1f}s)", flush=True)
        report["scenarios"][sc] = {"group_id": group, "runs": rows, "aggregate": aggregate(rows)}

    (out / "experiment_results.json").write_text(json.dumps(report, indent=2))
    write_markdown(report, out)


def write_markdown(report: dict, out: Path) -> None:
    md = [f"# Experiment results (measured)\n",
          f"Generated {report['generated']} with {report['sumo']}. Duration {report['duration']} s, "
          f"seeds {report['seeds']}. Values are the mean over seeds (± standard deviation).\n"]
    for sc, d in report["scenarios"].items():
        md.append(f"\n## Scenario: {sc} (batch `{d['group_id']}`)\n")
        md.append("| Controller | " + " | ".join(t for _, t in COLS) + " |")
        md.append("|---" * (len(COLS) + 1) + "|")
        for g in d["aggregate"]:
            cells = []
            for k, _ in COLS:
                v, s = g.get(k), g.get(f"{k}_std")
                d_ = 4 if k == "latency_mean_ms" else 2
                cells.append("-" if v is None else (f"{v:.{d_}f} ± {s:.{d_}f}" if s else f"{v:.{d_}f}"))
            md.append(f"| {LABEL.get(g['controller'], g['controller'])} | " + " | ".join(cells) + " |")
        md.append("\nChange vs Fixed-Time (negative = lower value):\n")
        md.append("| Controller | Avg waiting | Avg travel | Mean queue | Throughput | Stops/veh |")
        md.append("|---|---|---|---|---|---|")
        for g in d["aggregate"]:
            if g["controller"] == "fixed_time":
                continue
            p = g["vs_fixed_time_pct"]
            md.append(f"| {LABEL[g['controller']]} | {p['avg_waiting_time']}% | {p['avg_travel_time']}% | "
                      f"{p['mean_queue_length']}% | {p['throughput']}% | {p['stops_per_vehicle']}% |")
    (out / "experiment_results.md").write_text("\n".join(md) + "\n")
    print(f"\nSaved {out / 'experiment_results.md'}")


if __name__ == "__main__":
    main()
