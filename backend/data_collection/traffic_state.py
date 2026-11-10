"""Standardized traffic-state data structures shared by every module."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field


class InvalidTrafficState(ValueError):
    pass


def _clean(value, default: float = 0.0, lo: float | None = 0.0, hi: float | None = None) -> float:
    """Replace missing / NaN / negative-sentinel values coming from TraCI."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    if lo is not None and v < lo:
        return default if v < -1e-6 else lo
    if hi is not None and v > hi:
        return hi
    return v


@dataclass
class LaneState:
    lane_id: str
    tls_id: str
    approach: str
    length: float
    vehicle_count: int = 0
    queue_length: int = 0            # halting vehicles (speed < 0.1 m/s)
    occupancy: float = 0.0           # percent 0..100
    mean_speed: float = 0.0          # m/s
    avg_waiting_time: float = 0.0    # s, mean over vehicles on the lane
    arrival_rate: float = 0.0        # vehicles / minute entering the lane
    vehicles_in_zone: int = 0        # vehicles within the detector zone before the stop line
    congestion_score: float = 0.0    # filled by analysis module (0..100)
    queue_pressure: float = 0.0      # filled by analysis module

    def validate(self) -> "LaneState":
        self.vehicle_count = int(_clean(self.vehicle_count))
        self.queue_length = int(min(_clean(self.queue_length), self.vehicle_count))
        self.occupancy = _clean(self.occupancy, hi=100.0)
        self.mean_speed = _clean(self.mean_speed)
        self.avg_waiting_time = _clean(self.avg_waiting_time)
        self.arrival_rate = _clean(self.arrival_rate)
        self.vehicles_in_zone = int(min(_clean(self.vehicles_in_zone), self.vehicle_count))
        if self.length <= 0:
            raise InvalidTrafficState(f"lane {self.lane_id} has non-positive length")
        return self


@dataclass
class SignalState:
    tls_id: str
    phase_index: int          # current (or last) green phase index
    phase_name: str
    mode: str                 # GREEN | YELLOW | ALL_RED
    state_string: str         # SUMO red/yellow/green string
    elapsed_green: float      # seconds the current green has been shown
    time_in_mode: float
    target_phase: int | None = None
    red_time: list[float] = field(default_factory=list)  # seconds since each phase was last green
    demand_wait: list[float] = field(default_factory=list)  # seconds each phase has had vehicles waiting on red


@dataclass
class IntersectionState:
    tls_id: str
    lanes: dict[str, LaneState]
    signal: SignalState
    phase_demand: list[float] = field(default_factory=list)    # congestion-based demand per phase
    phase_pressure: list[float] = field(default_factory=list)  # max-pressure per phase
    phase_queue: list[int] = field(default_factory=list)       # halting vehicles per phase
    phase_zone: list[int] = field(default_factory=list)        # detector-zone vehicles per phase
    approach_scores: dict[str, float] = field(default_factory=dict)
    most_congested_approach: str = ""
    priority_phase: int = 0
    congestion_level: str = "Free"


@dataclass
class NetworkState:
    sim_time: float
    intersections: dict[str, IntersectionState]
    vehicles_in_network: int
    downstream_queue: dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)
