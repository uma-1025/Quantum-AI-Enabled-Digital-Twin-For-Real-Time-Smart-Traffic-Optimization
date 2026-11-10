"""Continuous traffic-data collection through TraCI.

Uses TraCI *subscriptions*: SUMO pushes all requested lane variables in a single
message per simulation step, which is much faster than one query per value.

Collected per monitored lane, every step:
  vehicle count, queue length (halting vehicles), occupancy, mean speed,
  mean waiting time, arrival rate (sliding window), vehicles in detector zone.
"""
from __future__ import annotations

from collections import deque

from backend.config import ADAPTIVE_DEFAULTS, ARRIVAL_WINDOW_S
from backend.data_collection.traffic_state import LaneState
from backend.simulation.network_model import NetworkModel

try:
    import traci.constants as tc
except Exception:  # pragma: no cover
    tc = None

LANE_VARS = None
VEH_VARS = None
if tc is not None:
    LANE_VARS = [
        tc.LAST_STEP_VEHICLE_NUMBER,
        tc.LAST_STEP_VEHICLE_HALTING_NUMBER,
        tc.LAST_STEP_OCCUPANCY,
        tc.LAST_STEP_MEAN_SPEED,
        tc.VAR_WAITING_TIME,
        tc.LAST_STEP_VEHICLE_ID_LIST,
    ]
    VEH_VARS = [tc.VAR_SPEED, tc.VAR_LANE_ID, tc.VAR_LANEPOSITION, tc.VAR_POSITION,
                tc.VAR_ANGLE, tc.VAR_TYPE]


class TrafficDataCollector:
    def __init__(self, model: NetworkModel, detection_distance: float | None = None):
        self.model = model
        self.detection_distance = detection_distance or ADAPTIVE_DEFAULTS["detection_distance"]
        self.lanes = model.monitored_lanes
        self.all_lanes = sorted(set(self.lanes) | set(model.downstream_lanes))
        self.lane_tls = {}
        for tid, inter in model.intersections.items():
            for lane in inter.in_lanes:
                self.lane_tls[lane] = tid
        self._prev_ids: dict[str, set[str]] = {l: set() for l in self.lanes}
        self._arrivals: dict[str, deque] = {l: deque() for l in self.lanes}
        self.subscribed = False

    def subscribe(self, conn) -> None:
        for lane in self.all_lanes:
            conn.lane.subscribe(lane, LANE_VARS)
        self.subscribed = True

    def collect(self, conn, sim_time: float, vehicle_data: dict) -> tuple[dict[str, LaneState], dict[str, int]]:
        """Return (lane states for monitored lanes, halting count for downstream lanes)."""
        if not self.subscribed:
            self.subscribe(conn)
        results = conn.lane.getAllSubscriptionResults()

        # vehicles in the detector zone (distance to stop line <= detection_distance)
        zone_counts: dict[str, int] = {}
        for vdata in vehicle_data.values():
            lane = vdata.get(tc.VAR_LANE_ID)
            if lane in self.lane_tls:
                pos = vdata.get(tc.VAR_LANEPOSITION, 0.0)
                if self.model.lane_length[lane] - pos <= self.detection_distance:
                    zone_counts[lane] = zone_counts.get(lane, 0) + 1

        lane_states: dict[str, LaneState] = {}
        for lane in self.lanes:
            r = results.get(lane, {})
            count = r.get(tc.LAST_STEP_VEHICLE_NUMBER, 0)
            ids = set(r.get(tc.LAST_STEP_VEHICLE_ID_LIST, ()))
            new = len(ids - self._prev_ids[lane])
            self._prev_ids[lane] = ids
            dq = self._arrivals[lane]
            if new:
                dq.append((sim_time, new))
            while dq and dq[0][0] <= sim_time - ARRIVAL_WINDOW_S:
                dq.popleft()
            window = min(ARRIVAL_WINDOW_S, max(sim_time, 1.0))
            arrival_rate = sum(n for _, n in dq) * 60.0 / window
            wait_sum = r.get(tc.VAR_WAITING_TIME, 0.0)
            inter = self.model.intersections[self.lane_tls[lane]]
            lane_states[lane] = LaneState(
                lane_id=lane,
                tls_id=inter.tls_id,
                approach=inter.lane_approach[lane],
                length=self.model.lane_length[lane],
                vehicle_count=count,
                queue_length=r.get(tc.LAST_STEP_VEHICLE_HALTING_NUMBER, 0),
                # TraCI returns occupancy as a fraction (0..1) -> convert to percent
                occupancy=r.get(tc.LAST_STEP_OCCUPANCY, 0.0) * 100.0,
                mean_speed=r.get(tc.LAST_STEP_MEAN_SPEED, 0.0) if count else 0.0,
                avg_waiting_time=(wait_sum / count) if count else 0.0,
                arrival_rate=arrival_rate,
                vehicles_in_zone=zone_counts.get(lane, 0),
            ).validate()

        downstream = {l: int(results.get(l, {}).get(tc.LAST_STEP_VEHICLE_HALTING_NUMBER, 0))
                      for l in self.model.downstream_lanes}
        return lane_states, downstream
