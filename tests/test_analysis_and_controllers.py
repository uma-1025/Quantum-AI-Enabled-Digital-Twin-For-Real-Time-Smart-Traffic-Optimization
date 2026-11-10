"""Congestion analysis, traffic-state validation and the three controllers' decision rules."""
import math

import pytest

from backend.analysis.congestion import congestion_level, lane_congestion_score
from backend.controllers import make_controller
from backend.data_collection.traffic_state import InvalidTrafficState, LaneState

NS_THROUGH_LANE = "N1_C1_1"
EW_THROUGH_LANE = "W1_C1_1"
NS_LEFT_LANE = "N1_C1_2"


# ----------------------------------------------------------------- traffic state
def test_lane_state_cleans_missing_values():
    l = LaneState("x", "C1", "N", 100.0, vehicle_count=None, queue_length=float("nan"),
                  occupancy=-1, mean_speed=float("inf"), avg_waiting_time="bad").validate()
    assert l.vehicle_count == 0 and l.queue_length == 0
    assert l.occupancy == 0 and l.mean_speed == 0 and l.avg_waiting_time == 0


def test_lane_state_caps_values():
    l = LaneState("x", "C1", "N", 100.0, vehicle_count=3, queue_length=10, occupancy=250).validate()
    assert l.queue_length == 3 and l.occupancy == 100


def test_lane_state_rejects_bad_length():
    with pytest.raises(InvalidTrafficState):
        LaneState("x", "C1", "N", 0.0).validate()


# ----------------------------------------------------------------- congestion
def test_congestion_score_formula():
    # capacity = 75 / 7.5 = 10 vehicles
    l = LaneState("x", "C1", "N", 75.0, vehicle_count=5, queue_length=5, occupancy=50,
                  avg_waiting_time=30, arrival_rate=6)
    expected = 100 * (0.4 * 0.5 + 0.2 * 0.5 + 0.25 * 0.5 + 0.15 * 0.5)
    assert math.isclose(lane_congestion_score(l), expected, abs_tol=0.01)


def test_congestion_score_bounds():
    empty = LaneState("x", "C1", "N", 75.0)
    full = LaneState("x", "C1", "N", 75.0, vehicle_count=50, queue_length=50, occupancy=100,
                     avg_waiting_time=999, arrival_rate=99)
    assert lane_congestion_score(empty) == 0
    assert lane_congestion_score(full) == 100


@pytest.mark.parametrize("score,label", [(0, "Free"), (24.9, "Free"), (25, "Moderate"),
                                         (60, "Heavy"), (80, "Severe"), (100, "Severe")])
def test_congestion_levels(score, label):
    assert congestion_level(score) == label


def test_phase_demand_and_pressure(make_state):
    st = make_state(queues={EW_THROUGH_LANE: 6}, downstream={})
    assert st.phase_queue[2] == 6 and st.phase_queue[0] == 0
    assert st.priority_phase == 2
    assert st.phase_pressure[2] == 6.0     # lane 1 has a single movement
    assert st.most_congested_approach == "W"


def test_pressure_subtracts_downstream_queue(make_state, model):
    inter = model.intersections["C1"]
    out = next(l.out_lane for l in inter.links if l.in_lane == EW_THROUGH_LANE)
    st = make_state(queues={EW_THROUGH_LANE: 6}, downstream={out: 4})
    assert st.phase_pressure[2] == 2.0


# ----------------------------------------------------------------- fixed time
def test_fixed_time_cycles():
    c = make_controller("fixed_time")
    from backend.data_collection.traffic_state import IntersectionState, SignalState
    sig = SignalState("C1", 0, "", "GREEN", "", 29.0, 29.0)
    st = IntersectionState("C1", {}, sig, phase_queue=[0] * 4)
    assert c.decide(st, 29).action == "hold"
    sig.elapsed_green = 30.0
    d = c.decide(st, 30)
    assert d.action == "switch" and d.target_phase == 1


def test_fixed_time_param_validation():
    with pytest.raises(ValueError):
        make_controller("fixed_time", {"green_times": [10, 10]})


# ----------------------------------------------------------------- adaptive (VAC)
def test_adaptive_min_green(make_state):
    c = make_controller("adaptive")
    d = c.decide(make_state(queues={EW_THROUGH_LANE: 10}, elapsed=3), 3)
    assert d.action == "hold" and d.category == "MIN_GREEN"


def test_adaptive_extends_while_vehicles_arrive(make_state):
    c = make_controller("adaptive")
    d = c.decide(make_state(queues={EW_THROUGH_LANE: 3}, zones={NS_THROUGH_LANE: 2}, elapsed=12), 12)
    assert d.action == "hold" and d.category == "EXTEND"


def test_adaptive_gap_out_selects_highest_demand(make_state):
    c = make_controller("adaptive")
    c.decide(make_state(elapsed=1), 1)  # start of green
    st = make_state(queues={EW_THROUGH_LANE: 8, NS_LEFT_LANE: 1}, elapsed=12)
    d = c.decide(st, 12)
    assert d.action == "switch" and d.category == "GAP_OUT" and d.target_phase == 2


def test_adaptive_max_out(make_state):
    c = make_controller("adaptive")
    st = make_state(queues={EW_THROUGH_LANE: 4}, zones={NS_THROUGH_LANE: 3}, elapsed=50)
    d = c.decide(st, 50)
    assert d.action == "switch" and d.category == "MAX_OUT"


def test_adaptive_starvation_guard(make_state):
    c = make_controller("adaptive")
    # EW_THROUGH has much more demand, but NS_LEFT vehicles have waited 95 s (> max_red 90)
    st = make_state(queues={EW_THROUGH_LANE: 10, NS_LEFT_LANE: 1}, zones={NS_THROUGH_LANE: 2},
                    elapsed=15, demand_wait=[0, 95, 20, 0])
    d = c.decide(st, 100)
    assert d.action == "switch" and d.category == "STARVATION" and d.target_phase == 1


def test_adaptive_rests_without_competing_demand(make_state):
    c = make_controller("adaptive")
    c.decide(make_state(elapsed=1), 1)
    d = c.decide(make_state(elapsed=60), 60)
    assert d.action == "hold" and d.category == "REST"


def test_adaptive_rejects_bad_params():
    with pytest.raises(ValueError):
        make_controller("adaptive", {"min_green": 60, "max_green": 10})
    with pytest.raises(ValueError):
        make_controller("adaptive", {"unknown": 1})


# ----------------------------------------------------------------- max pressure
def test_max_pressure_switches_to_highest_pressure(make_state):
    c = make_controller("max_pressure")
    d = c.decide(make_state(queues={EW_THROUGH_LANE: 6}, elapsed=10), 10)
    assert d.action == "switch" and d.target_phase == 2 and d.category == "PRESSURE"


def test_max_pressure_hysteresis_and_min_green(make_state):
    c = make_controller("max_pressure")
    assert c.decide(make_state(queues={EW_THROUGH_LANE: 6}, elapsed=2), 2).category == "MIN_GREEN"
    d = c.decide(make_state(queues={EW_THROUGH_LANE: 1}, elapsed=10), 10)
    assert d.action == "hold"   # gain of 1.0 does not exceed threshold 1.0


def test_unknown_controller():
    with pytest.raises(ValueError):
        make_controller("quantum")
