"""Test configuration: use a separate temporary database so tests never touch real results."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp(prefix="vac_test_")
# Set VAC_TEST_DATABASE_URL (e.g. a PostgreSQL test database) to run the suite on another database.
os.environ["DATABASE_URL"] = os.environ.get("VAC_TEST_DATABASE_URL") or \
    f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"

import pytest  # noqa: E402

from backend.data_collection.traffic_state import IntersectionState, LaneState, SignalState  # noqa: E402
from backend.simulation.network_model import load_network  # noqa: E402


@pytest.fixture(scope="session")
def model():
    return load_network()


@pytest.fixture
def make_state(model):
    """Build an IntersectionState for C1 with chosen per-phase values (unit-test fixture)."""
    from backend.analysis.congestion import analyse_intersection

    def _make(queues=None, zones=None, phase=0, elapsed=0.0, demand_wait=None, downstream=None):
        inter = model.intersections["C1"]
        queues = queues or {}
        zones = zones or {}
        lanes = {}
        for lane in inter.in_lanes:
            q = queues.get(lane, 0)
            lanes[lane] = LaneState(lane, "C1", inter.lane_approach[lane], model.lane_length[lane],
                                    vehicle_count=max(q, zones.get(lane, 0)), queue_length=q,
                                    vehicles_in_zone=zones.get(lane, 0)).validate()
        sig = SignalState("C1", phase, "", "GREEN", inter.green_state(phase), elapsed, elapsed,
                          red_time=[0.0] * 4, demand_wait=demand_wait or [0.0] * 4)
        st = IntersectionState("C1", lanes, sig)
        analyse_intersection(inter, lanes, downstream or {}, st)
        return st
    return _make
