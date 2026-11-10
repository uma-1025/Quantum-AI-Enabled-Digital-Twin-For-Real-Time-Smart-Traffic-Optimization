"""Fair controller comparison: identical network, demand, duration and seed.

For every seed, the SAME route file is generated once per controller from the
same (scenario, seed, duration), and SUMO is started with the same --seed.
Only the controller differs.
"""
from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime, timezone

import numpy as np

from backend.database import db
from backend.simulation.engine import SimulationRunner
from backend.simulation.sumo_utils import sumo_version

COMPARE_METRICS = ["avg_waiting_time", "mean_queue_length", "max_queue_length", "throughput",
                   "avg_travel_time", "stops_per_vehicle", "phase_changes", "latency_mean_ms",
                   "starvation_events", "avg_speed"]
LOWER_IS_BETTER = {"avg_waiting_time", "mean_queue_length", "max_queue_length", "avg_travel_time",
                   "stops_per_vehicle", "latency_mean_ms", "starvation_events"}


def run_single(scenario: str, controller: str, seed: int, duration: int,
               params: dict | None = None, group_id: str | None = None,
               mode: str = "batch", progress_cb=None) -> dict:
    runner = SimulationRunner(scenario, controller, seed, duration, controller_params=params,
                              label=f"exp_{controller}_{seed}_{uuid.uuid4().hex[:6]}")
    summary = runner.run_to_end(progress_cb)
    exp_id = db.save_experiment(
        {"group_id": group_id, "mode": mode, "scenario": scenario, "controller": controller,
         "seed": seed, "duration": duration, "params": runner.controller.params,
         "sumo_version": sumo_version()},
        summary, runner.metrics.timeseries, runner.stored_decisions)
    return {"experiment_id": exp_id, "controller": controller, "seed": seed, **summary}


def aggregate(rows: list[dict]) -> list[dict]:
    """Mean / std per controller across seeds, plus % change vs fixed-time (measured)."""
    by_ctrl: dict[str, list[dict]] = {}
    for r in rows:
        by_ctrl.setdefault(r["controller"], []).append(r)
    out = []
    for ctrl, rs in by_ctrl.items():
        entry = {"controller": ctrl, "runs": len(rs)}
        for m in COMPARE_METRICS:
            vals = [r[m] for r in rs if r.get(m) is not None]
            entry[m] = round(float(np.mean(vals)), 4) if vals else None
            entry[f"{m}_std"] = round(float(np.std(vals)), 4) if len(vals) > 1 else 0.0
        out.append(entry)
    base = next((e for e in out if e["controller"] == "fixed_time"), None)
    for e in out:
        e["vs_fixed_time_pct"] = {}
        if base is None:
            continue
        for m in COMPARE_METRICS:
            b, v = base.get(m), e.get(m)
            if b in (None, 0) or v is None:
                e["vs_fixed_time_pct"][m] = None
            else:
                e["vs_fixed_time_pct"][m] = round((v - b) / abs(b) * 100.0, 2)
    return out


class ComparisonJob:
    def __init__(self, scenario: str, controllers: list[str], seeds: list[int], duration: int,
                 params: dict | None = None):
        self.id = uuid.uuid4().hex[:10]
        self.scenario, self.controllers, self.seeds, self.duration = scenario, controllers, seeds, duration
        self.params = params or {}
        self.status = "queued"
        self.progress = 0.0
        self.current = ""
        self.results: list[dict] = []
        self.error: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def _run(self):
        self.status = "running"
        total = len(self.controllers) * len(self.seeds)
        done = 0
        try:
            for seed in self.seeds:
                for ctrl in self.controllers:
                    self.current = f"{ctrl} (seed {seed})"

                    def cb(frac, done=done):
                        self.progress = round((done + frac) / total, 3)

                    self.results.append(run_single(self.scenario, ctrl, seed, self.duration,
                                                   self.params.get(ctrl), group_id=self.id,
                                                   progress_cb=cb))
                    done += 1
                    self.progress = round(done / total, 3)
            self.status = "completed"
        except Exception as exc:
            self.status = "failed"
            self.error = f"{exc}\n{traceback.format_exc(limit=3)}"
        self.current = ""

    def to_dict(self) -> dict:
        return {"job_id": self.id, "status": self.status, "progress": self.progress,
                "current": self.current, "scenario": self.scenario, "controllers": self.controllers,
                "seeds": self.seeds, "duration": self.duration, "results": self.results,
                "aggregate": aggregate(self.results) if self.results else [], "error": self.error,
                "created_at": self.created_at}
