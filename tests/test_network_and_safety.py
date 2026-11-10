"""Network model, conflict matrix and signal safety layer."""
import pytest

from backend.controllers.safety import (ALL_RED, GREEN, YELLOW, Decision, SafetyViolation,
                                        SignalExecutor, validate_state)
from backend.simulation.network_model import (PHASE_NAMES, movements_conflict,
                                              validate_phase_plan)


def test_four_signalized_intersections(model):
    assert model.tls_ids == ["C1", "C2", "C3", "C4"]
    for inter in model.intersections.values():
        assert inter.n_links == 16              # 4 approaches x (right + 2 straight + left)
        assert {l.approach for l in inter.links} == {"N", "E", "S", "W"}
        assert len(inter.in_lanes) == 12        # 4 approaches x 3 lanes


def test_phase_plan_is_conflict_free_and_complete(model):
    assert validate_phase_plan(model) == []


@pytest.mark.parametrize("a,b,expected", [
    (("N", "s"), ("E", "s"), True),    # crossing through movements
    (("N", "s"), ("S", "s"), False),   # opposing through movements
    (("N", "l"), ("S", "l"), False),   # opposing left turns pass each other
    (("N", "l"), ("S", "s"), True),    # left turn vs opposing through
    (("N", "r"), ("E", "s"), True),    # merge into the same exit
    (("N", "r"), ("S", "r"), False),
])
def test_movement_conflicts(a, b, expected):
    assert movements_conflict(*a, *b) is expected
    assert movements_conflict(*b, *a) is expected  # symmetric


def test_validate_state_rejects_conflicting_greens(model):
    inter = model.intersections["C1"]
    ns, ew = inter.phase_links[0], inter.phase_links[2]
    state = ["r"] * 16
    state[ns[1]] = "G"
    state[ew[1]] = "G"
    with pytest.raises(SafetyViolation):
        validate_state(inter, "".join(state))


def test_validate_state_rejects_green_to_red_without_amber(model):
    inter = model.intersections["C1"]
    with pytest.raises(SafetyViolation):
        validate_state(inter, "r" * 16, previous=inter.green_state(0))


def test_validate_state_rejects_bad_length_and_chars(model):
    inter = model.intersections["C1"]
    with pytest.raises(SafetyViolation):
        validate_state(inter, "G" * 3)
    with pytest.raises(SafetyViolation):
        validate_state(inter, "X" * 16)


def test_executor_transition_sequence(model):
    inter = model.intersections["C1"]
    ex = SignalExecutor(inter, initial_phase=0, yellow_time=3, all_red_time=2, min_green=5)
    # min green not served -> request refused
    assert ex.request(None, Decision("switch", 2, "test"), now=1) is False
    for t in range(1, 6):
        ex.tick(None, 1.0, t)
    assert ex.request(None, Decision("switch", 2, "test"), now=5) is True
    assert ex.mode == YELLOW and set(ex.state) <= {"y", "r"}
    modes = []
    for t in range(6, 12):
        ex.tick(None, 1.0, t)
        modes.append(ex.mode)
    # 3 s amber, 2 s all-red, then the new green
    assert modes[:2] == [YELLOW, YELLOW]
    assert ALL_RED in modes
    assert ex.mode == GREEN and ex.phase == 2
    assert ex.state == inter.green_state(2)
    assert ex.phase_changes == 1


def test_executor_rejects_invalid_phase(model):
    ex = SignalExecutor(model.intersections["C1"], min_green=0)
    ex.elapsed_green = 100
    with pytest.raises(SafetyViolation):
        ex.request(None, Decision("switch", 9, "bad"), now=1)


def test_demand_wait_tracking(model):
    ex = SignalExecutor(model.intersections["C1"])
    ex.update_demand(10, [3, 0, 2, 0])
    ex.update_demand(25, [3, 0, 2, 0])
    w = ex.demand_wait(25)
    assert w[0] == 0.0          # phase 0 is being served
    assert w[2] == 15.0         # phase 2 has waited 15 s
    ex.update_demand(26, [3, 0, 0, 0])
    assert ex.demand_wait(26)[2] == 0.0
    assert len(PHASE_NAMES) == 4
