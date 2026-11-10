"""Performance evaluation: every number here is measured from the running SUMO simulation.

Definitions
-----------
* waiting time    : seconds a vehicle spends with speed < 0.1 m/s (SUMO's definition)
* stop            : a transition from moving (>= 0.1 m/s) to halted (< 0.1 m/s)
* travel time     : arrival time - departure time (completed trips only)
* throughput      : number of vehicles that completed their trip
* queue length    : halting vehicles on the 48 signal-approach lanes
* starvation event: a phase with waiting vehicles that stays red for longer than
                    STARVATION_THRESHOLD_S (counted once per episode)
* latency         : wall-clock time of the controller's decide() calls
"""
from __future__ import annotations

import numpy as np

from backend.config import STARVATION_THRESHOLD_S, TIMESERIES_INTERVAL_S

try:
    import traci.constants as tc
except Exception:  # pragma: no cover
    tc = None


class MetricsTracker:
    def __init__(self, tls_ids: list[str], n_phases: int = 4,
                 starvation_threshold: float = STARVATION_THRESHOLD_S,
                 interval: int = TIMESERIES_INTERVAL_S):
        self.vehicles: dict[str, dict] = {}
        self.completed: list[tuple[float, float, int]] = []  # (travel, wait, stops)
        self.departed = 0
        self.queue_samples: list[int] = []
        self.lane_queue_max = 0
        self.lane_queue_mean_samples: list[float] = []
        self.speed_samples: list[float] = []
        self.latencies_ms: list[float] = []
        self._interval_lat: list[float] = []
        self.starvation_events = 0
        self.starvation_log: list[dict] = []
        self._starving = {(t, p): False for t in tls_ids for p in range(n_phases)}
        self.teleports = 0
        self.interval = interval
        self.timeseries: list[dict] = []
        self._last_arrived_count = 0
        self.phase_changes = 0

    # ------------------------------------------------------------------
    def record_latency(self, ms: float) -> None:
        self.latencies_ms.append(ms)
        self._interval_lat.append(ms)

    def on_step(self, now: float, dt: float, vehicle_data: dict, departed: list[str],
                arrived: list[str], net_states: dict, phase_changes: int,
                congestion_index: float, teleports: int = 0) -> None:
        for vid in departed:
            self.vehicles[vid] = {"depart": now, "wait": 0.0, "stops": 0, "stopped": False}
            self.departed += 1
        for vid, data in vehicle_data.items():
            v = self.vehicles.get(vid)
            if v is None:
                continue
            speed = data.get(tc.VAR_SPEED, 0.0)
            if speed < 0.1:
                v["wait"] += dt
                if not v["stopped"]:
                    v["stops"] += 1
                    v["stopped"] = True
            else:
                v["stopped"] = False
        for vid in arrived:
            v = self.vehicles.pop(vid, None)
            if v is not None:
                self.completed.append((now - v["depart"], v["wait"], v["stops"]))
        self.teleports += teleports
        self.phase_changes = phase_changes

        lane_queues = [l.queue_length for s in net_states.values() for l in s.lanes.values()]
        total_q = int(sum(lane_queues))
        self.queue_samples.append(total_q)
        if lane_queues:
            self.lane_queue_max = max(self.lane_queue_max, max(lane_queues))
            self.lane_queue_mean_samples.append(float(np.mean(lane_queues)))
        speeds = [d.get(tc.VAR_SPEED, 0.0) for d in vehicle_data.values()]
        if speeds:
            self.speed_samples.append(float(np.mean(speeds)))

        # starvation monitor (independent of the controller)
        for tid, s in net_states.items():
            for p, wait in enumerate(s.signal.demand_wait):
                key = (tid, p)
                if wait >= STARVATION_THRESHOLD_S:
                    if not self._starving[key]:
                        self._starving[key] = True
                        self.starvation_events += 1
                        self.starvation_log.append({"time": now, "tls_id": tid, "phase": p,
                                                    "waited_s": wait, "queue": s.phase_queue[p]})
                elif wait == 0.0:
                    self._starving[key] = False

        if int(now) % self.interval == 0:
            waits = [v["wait"] for v in self.vehicles.values()]
            arrived_total = len(self.completed)
            self.timeseries.append({
                "sim_time": now,
                "vehicles": len(vehicle_data),
                "total_queue": total_q,
                "avg_waiting": round(float(np.mean(waits)), 3) if waits else 0.0,
                "avg_speed": round(float(np.mean(speeds)), 3) if speeds else 0.0,
                "throughput": arrived_total,
                "throughput_rate": round((arrived_total - self._last_arrived_count) * 3600.0 / self.interval, 1),
                "congestion_index": congestion_index,
                "phase_changes": phase_changes,
                "latency_ms": round(float(np.mean(self._interval_lat)), 4) if self._interval_lat else 0.0,
            })
            self._last_arrived_count = arrived_total
            self._interval_lat = []

    # ------------------------------------------------------------------
    def live_kpis(self) -> dict:
        waits = [c[1] for c in self.completed]
        return {
            "vehicles_departed": self.departed,
            "vehicles_completed": len(self.completed),
            "vehicles_in_network": len(self.vehicles),
            "avg_waiting_time": round(float(np.mean(waits)), 2) if waits else None,
            "current_total_queue": self.queue_samples[-1] if self.queue_samples else 0,
            "avg_queue_per_lane": round(float(np.mean(self.lane_queue_mean_samples)), 3)
            if self.lane_queue_mean_samples else None,
            "phase_changes": self.phase_changes,
            "starvation_events": self.starvation_events,
        }

    def summary(self, duration: float) -> dict:
        travel = [c[0] for c in self.completed]
        waits = [c[1] for c in self.completed]
        stops = [c[2] for c in self.completed]
        unfinished_wait = [v["wait"] for v in self.vehicles.values()]
        lat = np.array(self.latencies_ms) if self.latencies_ms else np.array([0.0])
        n = len(self.completed)
        return {
            "vehicles_departed": self.departed,
            "throughput": n,
            "throughput_per_hour": round(n * 3600.0 / duration, 1) if duration else 0.0,
            "vehicles_remaining": len(self.vehicles),
            "avg_waiting_time": round(float(np.mean(waits)), 3) if waits else None,
            "avg_waiting_time_all": round(float(np.mean(waits + unfinished_wait)), 3)
            if (waits or unfinished_wait) else None,
            "avg_travel_time": round(float(np.mean(travel)), 3) if travel else None,
            "stops_per_vehicle": round(float(np.mean(stops)), 3) if stops else None,
            "mean_queue_length": round(float(np.mean(self.lane_queue_mean_samples)), 4)
            if self.lane_queue_mean_samples else None,
            "mean_total_queue": round(float(np.mean(self.queue_samples)), 3) if self.queue_samples else None,
            "max_queue_length": int(self.lane_queue_max),
            "max_total_queue": int(max(self.queue_samples)) if self.queue_samples else 0,
            "avg_speed": round(float(np.mean(self.speed_samples)), 3) if self.speed_samples else None,
            "phase_changes": self.phase_changes,
            "latency_mean_ms": round(float(lat.mean()), 4),
            "latency_p95_ms": round(float(np.percentile(lat, 95)), 4),
            "latency_max_ms": round(float(lat.max()), 4),
            "starvation_events": self.starvation_events,
            "teleports": self.teleports,
        }
