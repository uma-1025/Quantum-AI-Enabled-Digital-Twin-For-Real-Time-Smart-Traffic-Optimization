"""FastAPI endpoints (with real SUMO underneath), database and reports."""
import time

import pytest
from fastapi.testclient import TestClient

from backend.database import db
from backend.main import app

client = TestClient(app)


def wait_for(fn, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = fn()
        if v:
            return v
        time.sleep(0.5)
    raise TimeoutError


def test_health_and_config():
    h = client.get("/health").json()
    assert h["sumo"] == "ok" and h["traci"] == "ok" and h["database"] == "ok"
    c = client.get("/config").json()
    assert set(c["controllers"]) == {"fixed_time", "adaptive", "max_pressure"}
    n = client.get("/network").json()
    assert len(n["tls"]) == 4 and n["phase_plan_problems"] == []


def test_input_validation_and_state_errors():
    client.post("/simulation/reset")
    assert client.post("/simulation/start", json={"scenario": "nope"}).status_code == 422
    assert client.post("/simulation/start", json={"controller": "nope"}).status_code == 422
    assert client.post("/simulation/start", json={"duration": 5}).status_code == 422
    assert client.post("/simulation/pause").status_code == 409
    assert client.post("/simulation/resume").status_code == 409
    assert client.get("/simulation/state").status_code == 404
    assert client.get("/experiments/999999").status_code == 404
    assert client.get("/reports/csv?ids=a,b").status_code == 400


def test_live_simulation_lifecycle():
    client.post("/simulation/reset")
    r = client.post("/simulation/start", json={"scenario": "low", "controller": "adaptive",
                                               "duration": 120, "speed": 40})
    assert r.status_code == 200 and r.json()["status"] == "running"
    assert client.post("/simulation/start", json={}).status_code == 409   # already running
    wait_for(lambda: client.get("/simulation/status").json()["sim_time"] > 5)
    assert client.post("/simulation/pause").json()["status"] == "paused"
    t1 = client.get("/simulation/status").json()["sim_time"]
    time.sleep(1.0)
    assert client.get("/simulation/status").json()["sim_time"] == t1          # really paused
    assert client.post("/simulation/resume").json()["status"] == "running"
    state = client.get("/simulation/state").json()
    assert len(state["intersections"]) == 4 and "kpis" in state
    snap = client.get("/simulation/snapshot").json()
    assert set(snap["signals"]) == {"C1", "C2", "C3", "C4"}
    assert "decisions" in client.get("/simulation/decisions").json()
    final = wait_for(lambda: (s := client.get("/simulation/status").json())["status"] == "finished" and s)
    assert final["experiment_id"] is not None
    exp = client.get(f"/experiments/{final['experiment_id']}").json()
    assert exp["mode"] == "live" and exp["throughput"] is not None
    assert len(client.get(f"/experiments/{final['experiment_id']}/timeseries").json()) > 5
    assert client.post("/simulation/reset").json()["status"] == "idle"


def test_comparison_job_and_reports():
    job = client.post("/experiments/compare", json={"scenario": "low", "seeds": [1], "duration": 120}).json()
    done = wait_for(lambda: (j := client.get(f"/experiments/jobs/{job['job_id']}").json())["status"]
                    in ("completed", "failed") and j, timeout=300)
    assert done["status"] == "completed", done["error"]
    assert {a["controller"] for a in done["aggregate"]} == {"fixed_time", "adaptive", "max_pressure"}
    fixed = next(a for a in done["aggregate"] if a["controller"] == "fixed_time")
    assert fixed["vs_fixed_time_pct"]["avg_waiting_time"] == 0.0
    agg = client.get(f"/experiments/groups/{job['job_id']}/aggregate").json()
    assert len(agg) == 3
    csv = client.get("/reports/csv")
    assert csv.status_code == 200 and b"avg_waiting_time" in csv.content
    pdf = client.get("/reports/pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_database_roundtrip(tmp_path):
    eng = db.get_engine(f"sqlite:///{tmp_path/'x.db'}")
    eid = db.save_experiment({"mode": "batch", "scenario": "low", "controller": "adaptive", "seed": 1,
                              "duration": 60, "params": {"a": 1}},
                             {"throughput": 10, "avg_waiting_time": 5.5},
                             [{"sim_time": 10, "vehicles": 3}],
                             [{"sim_time": 1, "tls_id": "C1", "action": "switch", "category": "GAP_OUT",
                               "from_phase": "A", "to_phase": "B", "reason": "r", "accepted": True}],
                             engine=eng)
    e = db.get_experiment(eid, engine=eng)
    assert e["throughput"] == 10 and e["params"] == {"a": 1}
    assert len(db.get_timeseries(eid, engine=eng)) == 1
    assert len(db.get_decisions(eid, engine=eng)) == 1
    assert db.delete_experiment(eid, engine=eng) and db.get_experiment(eid, engine=eng) is None
