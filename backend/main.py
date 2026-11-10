"""FastAPI backend - the ONLY component that talks to SUMO (through TraCI).

Run:  uvicorn backend.main:app --host 127.0.0.1 --port 8000
Docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from backend.config import (ADAPTIVE_DEFAULTS, ALL_RED_TIME_S, DEFAULT_DURATION_S, DEFAULT_SEED,
                            FIXED_TIME_DEFAULTS, MAX_PRESSURE_DEFAULTS, NET_FILE, SCENARIOS,
                            YELLOW_TIME_S, CONGESTION_WEIGHTS, STARVATION_THRESHOLD_S)
from backend.controllers import CONTROLLERS
from backend.database import db
from backend.evaluation.experiment import ComparisonJob, aggregate
from backend.reports.report_generator import build_csv, build_pdf
from backend.simulation.live_session import LiveSession
from backend.simulation.network_model import PHASE_NAMES, load_network, validate_phase_plan
from backend.simulation.sumo_utils import SumoNotFoundError, sumo_binary, sumo_version

app = FastAPI(title="VAC-Inspired Adaptive Traffic Control API", version="1.0.0",
              description="Epic 1 backend: SUMO + TraCI simulation, adaptive / max-pressure / "
                          "fixed-time signal control, metrics, experiments and reports.")

live = LiveSession()
jobs: dict[str, ComparisonJob] = {}


# ---------------------------------------------------------------- schemas
class StartRequest(BaseModel):
    scenario: str = "medium"
    controller: str = "adaptive"
    seed: int = DEFAULT_SEED
    duration: int = Field(DEFAULT_DURATION_S, ge=60, le=14400)
    speed: float = Field(10.0, ge=0, le=1000, description="simulated seconds per wall second; 0 = max")
    gui: bool = False
    params: Optional[dict] = None

    @field_validator("scenario")
    @classmethod
    def _sc(cls, v):
        if v not in SCENARIOS:
            raise ValueError(f"scenario must be one of {list(SCENARIOS)}")
        return v

    @field_validator("controller")
    @classmethod
    def _ct(cls, v):
        if v not in CONTROLLERS:
            raise ValueError(f"controller must be one of {list(CONTROLLERS)}")
        return v


class SpeedRequest(BaseModel):
    speed: float = Field(..., ge=0, le=1000)


class CompareRequest(BaseModel):
    scenario: str = "medium"
    controllers: list[str] = Field(default_factory=lambda: list(CONTROLLERS))
    seeds: list[int] = Field(default_factory=lambda: [DEFAULT_SEED])
    duration: int = Field(DEFAULT_DURATION_S, ge=60, le=14400)
    params: Optional[dict] = None

    @field_validator("scenario")
    @classmethod
    def _sc(cls, v):
        if v not in SCENARIOS:
            raise ValueError(f"scenario must be one of {list(SCENARIOS)}")
        return v

    @field_validator("controllers")
    @classmethod
    def _ct(cls, v):
        bad = [c for c in v if c not in CONTROLLERS]
        if bad or not v:
            raise ValueError(f"controllers must be a non-empty subset of {list(CONTROLLERS)}")
        return v

    @field_validator("seeds")
    @classmethod
    def _sd(cls, v):
        if not v or len(v) > 10:
            raise ValueError("provide 1 to 10 seeds")
        return v


# ---------------------------------------------------------------- system
@app.get("/health", tags=["system"])
def health():
    out = {"api": "ok", "network_file": NET_FILE.exists()}
    try:
        out["sumo_binary"] = sumo_binary("sumo")
        out["sumo_version"] = sumo_version()
        out["sumo"] = "ok"
    except SumoNotFoundError as exc:
        out["sumo"] = "missing"
        out["sumo_error"] = str(exc)
    try:
        import traci  # noqa: F401
        out["traci"] = "ok"
    except Exception as exc:
        out["traci"] = f"missing ({exc})"
    try:
        db.list_experiments(limit=1)
        out["database"] = "ok"
    except Exception as exc:
        out["database"] = f"error ({exc})"
    out["live_status"] = live.status
    return out


@app.get("/config", tags=["system"])
def config():
    return {
        "scenarios": SCENARIOS,
        "controllers": {k: {"label": c.label, "defaults": c.default_params()} for k, c in CONTROLLERS.items()},
        "phases": PHASE_NAMES,
        "safety": {"yellow_time": YELLOW_TIME_S, "all_red_time": ALL_RED_TIME_S},
        "congestion_weights": CONGESTION_WEIGHTS,
        "starvation_threshold_s": STARVATION_THRESHOLD_S,
        "defaults": {"duration": DEFAULT_DURATION_S, "seed": DEFAULT_SEED, "fixed_time": FIXED_TIME_DEFAULTS,
                     "adaptive": ADAPTIVE_DEFAULTS, "max_pressure": MAX_PRESSURE_DEFAULTS},
    }


@app.get("/network", tags=["system"])
def network():
    try:
        m = load_network()
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc))
    lanes = [{"id": lid, "shape": shape} for lid, shape in m.lane_shapes.items()]
    tls = {}
    for tid, inter in m.intersections.items():
        tls[tid] = {"x": inter.x, "y": inter.y,
                    "links": [{"index": l.index, "in_lane": l.in_lane, "out_lane": l.out_lane,
                               "approach": l.approach, "turn": l.turn,
                               "stop": m.lane_shapes[l.in_lane][-1]} for l in inter.links],
                    "phase_links": inter.phase_links,
                    "phase_states": [inter.green_state(p) for p in range(len(PHASE_NAMES))]}
    return {"lanes": lanes, "tls": tls, "boundary": m.boundary,
            "phase_plan_problems": validate_phase_plan(m)}


# ---------------------------------------------------------------- live simulation
@app.post("/simulation/start", tags=["simulation"])
def sim_start(req: StartRequest):
    try:
        return live.start(req.scenario, req.controller, req.seed, req.duration, req.speed, req.gui, req.params)
    except (RuntimeError, ValueError, SumoNotFoundError) as exc:
        raise HTTPException(409 if "already running" in str(exc) else 400, str(exc))


@app.post("/simulation/pause", tags=["simulation"])
def sim_pause():
    try:
        return live.pause()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@app.post("/simulation/resume", tags=["simulation"])
def sim_resume():
    try:
        return live.resume()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@app.post("/simulation/reset", tags=["simulation"])
def sim_reset():
    return live.reset()


@app.post("/simulation/speed", tags=["simulation"])
def sim_speed(req: SpeedRequest):
    return live.set_speed(req.speed)


@app.get("/simulation/status", tags=["simulation"])
def sim_status():
    return live.status_dict()


def _runner():
    try:
        return live.require_runner()
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@app.get("/simulation/state", tags=["simulation"])
def sim_state():
    r = _runner()
    with live.lock:
        out = r.state_dict()
    out["status"] = live.status_dict()
    return out


@app.get("/simulation/snapshot", tags=["simulation"])
def sim_snapshot():
    r = _runner()
    with live.lock:
        out = r.snapshot()
    out["status"] = live.status
    return out


@app.get("/simulation/history", tags=["simulation"])
def sim_history():
    r = _runner()
    with live.lock:
        return {"timeseries": list(r.metrics.timeseries), "summary": r.summary()}


@app.get("/simulation/decisions", tags=["simulation"])
def sim_decisions(limit: int = Query(100, ge=1, le=400)):
    r = _runner()
    with live.lock:
        return {"decisions": list(r.decision_log)[-limit:][::-1],
                "latest": r.latest_decision,
                "transitions": r.transitions(limit)}


# ---------------------------------------------------------------- experiments
@app.post("/experiments/compare", tags=["experiments"])
def compare(req: CompareRequest):
    running = [j for j in jobs.values() if j.status in ("queued", "running")]
    if running:
        raise HTTPException(409, f"Comparison job {running[0].id} is still running.")
    job = ComparisonJob(req.scenario, req.controllers, req.seeds, req.duration, req.params).start()
    jobs[job.id] = job
    return job.to_dict()


@app.get("/experiments/jobs", tags=["experiments"])
def list_jobs():
    return [j.to_dict() for j in sorted(jobs.values(), key=lambda j: j.created_at, reverse=True)]


@app.get("/experiments/jobs/{job_id}", tags=["experiments"])
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "job not found")
    return jobs[job_id].to_dict()


@app.get("/experiments", tags=["experiments"])
def experiments(limit: int = 500, group_id: Optional[str] = None):
    return db.list_experiments(limit, group_id)


@app.get("/experiments/groups/{group_id}/aggregate", tags=["experiments"])
def group_aggregate(group_id: str):
    rows = db.list_experiments(10000, group_id)
    if not rows:
        raise HTTPException(404, "group not found")
    return aggregate(rows)


@app.get("/experiments/{exp_id}", tags=["experiments"])
def experiment(exp_id: int):
    e = db.get_experiment(exp_id)
    if not e:
        raise HTTPException(404, "experiment not found")
    return e


@app.get("/experiments/{exp_id}/timeseries", tags=["experiments"])
def experiment_ts(exp_id: int):
    if not db.get_experiment(exp_id):
        raise HTTPException(404, "experiment not found")
    return db.get_timeseries(exp_id)


@app.get("/experiments/{exp_id}/decisions", tags=["experiments"])
def experiment_decisions(exp_id: int, limit: int = 1000):
    return db.get_decisions(exp_id, limit)


@app.delete("/experiments/{exp_id}", tags=["experiments"])
def experiment_delete(exp_id: int):
    if not db.delete_experiment(exp_id):
        raise HTTPException(404, "experiment not found")
    return {"deleted": exp_id}


# ---------------------------------------------------------------- reports
def _ids(ids: Optional[str]) -> Optional[list[int]]:
    if not ids:
        return None
    try:
        return [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "ids must be a comma-separated list of integers")


@app.get("/reports/csv", tags=["reports"])
def report_csv(ids: Optional[str] = None):
    return Response(build_csv(_ids(ids)), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=vac_experiments.csv"})


@app.get("/reports/pdf", tags=["reports"])
def report_pdf(ids: Optional[str] = None):
    try:
        data = build_pdf(_ids(ids))
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=vac_report.pdf"})
