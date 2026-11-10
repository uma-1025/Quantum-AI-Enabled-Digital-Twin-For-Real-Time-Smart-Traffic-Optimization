"""Integration tests that run the REAL SUMO simulation through TraCI."""
import pytest

from backend.controllers.safety import validate_state
from backend.simulation.engine import SimulationRunner
from backend.sumo_config.generate_routes import FRINGE, generate_trips, write_run_files


def test_route_generation_is_deterministic():
    a = generate_trips("medium", 7, 600)
    b = generate_trips("medium", 7, 600)
    c = generate_trips("medium", 8, 600)
    assert a == b and a != c
    assert len(generate_trips("high", 7, 600)) > len(generate_trips("low", 7, 600))
    for _, frm, to in a:            # never return to the entry point (no U-turn trips)
        assert frm.split("_")[0] != to.split("_")[1]
        assert frm.split("_")[0] in FRINGE


def test_unknown_scenario():
    with pytest.raises(ValueError):
        generate_trips("extreme", 1, 100)


@pytest.mark.parametrize("controller", ["fixed_time", "adaptive", "max_pressure"])
def test_controller_runs_in_sumo_safely(controller):
    r = SimulationRunner("medium", controller, seed=3, duration=400, label=f"it_{controller}")
    r.start()
    try:
        prev = {t: ex.state for t, ex in r.executors.items()}
        seen_states = {t: set() for t in r.executors}
        for _ in range(400):
            r.step()
            for tid, ex in r.executors.items():
                sumo_state = r.conn.trafficlight.getRedYellowGreenState(tid)
                assert sumo_state == ex.state                  # SUMO shows exactly what we sent
                validate_state(ex.inter, sumo_state, prev[tid])  # every applied state is safe
                prev[tid] = sumo_state
                seen_states[tid].add(sumo_state)
        s = r.summary()
    finally:
        r.close()
    assert s["safety_rejections"] == 0
    assert s["phase_changes"] > 0                    # signals change automatically
    assert s["throughput"] > 0 and s["vehicles_departed"] > 0
    assert s["avg_waiting_time"] is not None
    assert all(any("y" in x for x in v) for v in seen_states.values())  # amber was shown
    assert all("r" * 16 in v for v in seen_states.values())             # all-red was shown
    assert len(r.metrics.timeseries) >= 30


def test_same_seed_same_demand_for_all_controllers():
    _, n1 = write_run_files("medium", 11, 300, "fair_a")
    _, n2 = write_run_files("medium", 11, 300, "fair_b")
    assert n1 == n2
    a = (write_run_files("medium", 11, 300, "fair_a")[0].parent / "demand.rou.xml").read_text()
    b = (write_run_files("medium", 11, 300, "fair_b")[0].parent / "demand.rou.xml").read_text()
    assert a == b


def test_collected_state_is_consistent():
    r = SimulationRunner("high", "adaptive", seed=5, duration=200, label="it_state")
    r.start()
    try:
        for _ in range(200):
            st = r.step()
        d = r.state_dict()
    finally:
        r.close()
    assert len(d["intersections"]) == 4
    lanes = [l for i in d["intersections"].values() for l in i["lanes"]]
    assert len(lanes) == 48
    for l in lanes:
        assert 0 <= l["queue_length"] <= l["vehicle_count"]
        assert 0 <= l["occupancy"] <= 100
        assert 0 <= l["congestion_score"] <= 100
    assert sum(l["vehicle_count"] for l in lanes) > 0
    assert d["kpis"]["vehicles_departed"] > 0
