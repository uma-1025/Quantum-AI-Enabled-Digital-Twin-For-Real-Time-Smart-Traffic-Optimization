"""Simulation engine: one SUMO run driven step-by-step through TraCI.

Per simulation step (1 s):
  1. SUMO advances one step                         (traci simulationStep)
  2. safety executors advance amber/all-red timers
  3. traffic data is collected                      (data_collection)
  4. congestion / pressure is analysed              (analysis)
  5. the controller decides for every green signal  (controllers) - timed for latency
  6. the safety layer validates and applies changes (controllers.safety -> TraCI)
  7. performance metrics are updated                (evaluation)
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import asdict

from backend.analysis.congestion import (analyse_intersection, busiest_lane, congestion_level,
                                         network_congestion_index)
from backend.config import STEP_LENGTH_S
from backend.controllers import make_controller
from backend.controllers.safety import SafetyViolation, SignalExecutor
from backend.data_collection.collector import VEH_VARS, TrafficDataCollector
from backend.data_collection.traffic_state import IntersectionState, NetworkState
from backend.evaluation.metrics import MetricsTracker
from backend.simulation.network_model import PHASE_NAMES, load_network
from backend.simulation.sumo_utils import start_traci
from backend.sumo_config.generate_routes import write_run_files

try:
    import traci.constants as tc
    from traci.exceptions import FatalTraCIError, TraCIException
except Exception:  # pragma: no cover
    tc = None
    FatalTraCIError = TraCIException = RuntimeError


class SimulationRunner:
    def __init__(self, scenario: str, controller: str, seed: int, duration: int,
                 gui: bool = False, controller_params: dict | None = None,
                 density_multiplier: float = 1.0, label: str | None = None):
        if duration <= 0:
            raise ValueError("duration must be positive")
        self.scenario = scenario
        self.controller_name = controller
        self.seed = int(seed)
        self.duration = int(duration)
        self.gui = gui
        self.density_multiplier = density_multiplier
        self.label = label or f"run_{uuid.uuid4().hex[:8]}"
        self.controller = make_controller(controller, controller_params)
        self.model = load_network()
        self.conn = None
        self.now = 0.0
        self.finished = False
        self.loaded_vehicles = 0
        self.decision_log: deque = deque(maxlen=400)
        self.stored_decisions: list[dict] = []
        self.latest_decision: dict[str, dict] = {}
        self._last_category: dict[str, str] = {}
        self.safety_rejections = 0
        self.latest_state: NetworkState | None = None
        self.latest_vehicles: dict = {}
        self.wall_start = None

    # ------------------------------------------------------------------
    def start(self) -> None:
        cfg, n = write_run_files(self.scenario, self.seed, self.duration, self.label,
                                 self.density_multiplier)
        self.loaded_vehicles = n
        self.conn = start_traci(cfg, self.label, gui=self.gui, seed=self.seed)
        det = self.controller.params.get("detection_distance")
        self.collector = TrafficDataCollector(self.model, det)
        self.collector.subscribe(self.conn)
        self.executors = {tid: SignalExecutor(inter) for tid, inter in self.model.intersections.items()}
        for ex in self.executors.values():
            ex.install(self.conn)
        self.metrics = MetricsTracker(self.model.tls_ids, len(PHASE_NAMES))
        self.wall_start = time.perf_counter()

    def _record_decision(self, tid: str, decision, accepted: bool, from_phase: int) -> None:
        entry = {
            "sim_time": self.now, "tls_id": tid, "action": decision.action,
            "category": decision.category, "from_phase": PHASE_NAMES[from_phase],
            "to_phase": PHASE_NAMES[decision.target_phase], "reason": decision.reason,
            "accepted": accepted,
        }
        self.latest_decision[tid] = entry
        if decision.action == "switch" or self._last_category.get(tid) != decision.category:
            self.decision_log.append(entry)
            self.stored_decisions.append(entry)
        self._last_category[tid] = decision.category

    def step(self) -> NetworkState:
        if self.conn is None:
            raise RuntimeError("Simulation not started")
        conn = self.conn
        conn.simulationStep()
        self.now = conn.simulation.getTime()
        dt = STEP_LENGTH_S

        departed = list(conn.simulation.getDepartedIDList())
        for vid in departed:
            conn.vehicle.subscribe(vid, VEH_VARS)
        arrived = list(conn.simulation.getArrivedIDList())
        teleports = conn.simulation.getStartingTeleportNumber()

        for ex in self.executors.values():
            ex.tick(conn, dt, self.now)

        vehicle_data = conn.vehicle.getAllSubscriptionResults()
        lane_states, downstream = self.collector.collect(conn, self.now, vehicle_data)

        states: dict[str, IntersectionState] = {}
        for tid, inter in self.model.intersections.items():
            st = IntersectionState(tid, {l: lane_states[l] for l in inter.in_lanes},
                                   self.executors[tid].signal_state(self.now))
            analyse_intersection(inter, st.lanes, downstream, st)
            self.executors[tid].update_demand(self.now, st.phase_queue)
            st.signal = self.executors[tid].signal_state(self.now)
            states[tid] = st

        for tid, st in states.items():
            ex = self.executors[tid]
            if not ex.can_decide():
                continue
            t0 = time.perf_counter()
            decision = self.controller.decide(st, self.now)
            self.metrics.record_latency((time.perf_counter() - t0) * 1000.0)
            from_phase = ex.phase
            try:
                accepted = ex.request(conn, decision, self.now)
            except SafetyViolation as exc:
                self.safety_rejections += 1
                accepted = False
                decision.reason += f" [REJECTED by safety layer: {exc}]"
            self._record_decision(tid, decision, accepted, from_phase)
            st.signal = ex.signal_state(self.now)

        ci = network_congestion_index(states)
        phase_changes = sum(ex.phase_changes for ex in self.executors.values())
        self.metrics.on_step(self.now, dt, vehicle_data, departed, arrived, states,
                             phase_changes, ci, teleports)
        self.latest_vehicles = vehicle_data
        self.latest_state = NetworkState(self.now, states, len(vehicle_data), downstream)
        if self.now >= self.duration:
            self.finished = True
        return self.latest_state

    def run_to_end(self, progress_cb=None) -> dict:
        if self.conn is None:
            self.start()
        try:
            while not self.finished:
                self.step()
                if progress_cb and int(self.now) % 60 == 0:
                    progress_cb(self.now / self.duration)
        finally:
            self.close()
        return self.summary()

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    # ------------------------------------------------------------------ views
    def summary(self) -> dict:
        s = self.metrics.summary(self.now or self.duration)
        s["safety_rejections"] = self.safety_rejections
        s["sim_time"] = self.now
        s["wall_time_s"] = round(time.perf_counter() - self.wall_start, 2) if self.wall_start else None
        return s

    def state_dict(self) -> dict:
        st = self.latest_state
        if st is None:
            return {}
        inters = {}
        for tid, s in st.intersections.items():
            d = asdict(s)
            d["lanes"] = list(d["lanes"].values())
            d["latest_decision"] = self.latest_decision.get(tid)
            d["phase_names"] = PHASE_NAMES
            inters[tid] = d
        bl = busiest_lane(st.intersections)
        return {
            "sim_time": st.sim_time,
            "duration": self.duration,
            "vehicles_in_network": st.vehicles_in_network,
            "congestion_index": network_congestion_index(st.intersections),
            # condition = level of the mean of each intersection's most congested approach
            "condition_score": round(sum(max(i.approach_scores.values(), default=0.0)
                                         for i in st.intersections.values()) / max(len(st.intersections), 1), 2),
            "congestion_level": congestion_level(sum(max(i.approach_scores.values(), default=0.0)
                                                     for i in st.intersections.values())
                                                 / max(len(st.intersections), 1)),
            "controller": self.controller_name,
            "scenario": self.scenario,
            "active_intersections": len(st.intersections),
            "busiest_lane": asdict(bl) if bl else None,
            "intersections": inters,
            "kpis": self.metrics.live_kpis(),
            "safety_rejections": self.safety_rejections,
        }

    def snapshot(self) -> dict:
        vehicles = []
        for vid, d in self.latest_vehicles.items():
            pos = d.get(tc.VAR_POSITION)
            if not pos:
                continue
            vehicles.append({"id": vid, "x": round(pos[0], 2), "y": round(pos[1], 2),
                             "angle": round(d.get(tc.VAR_ANGLE, 0.0), 1),
                             "speed": round(d.get(tc.VAR_SPEED, 0.0), 2),
                             "type": d.get(tc.VAR_TYPE, "car")})
        signals = {tid: {"state": ex.state, "mode": ex.mode, "phase": PHASE_NAMES[ex.phase],
                         "elapsed_green": round(ex.elapsed_green, 1)}
                   for tid, ex in getattr(self, "executors", {}).items()}
        return {"sim_time": self.now, "vehicles": vehicles, "signals": signals}

    def transitions(self, limit: int = 100) -> list[dict]:
        out = []
        for ex in getattr(self, "executors", {}).values():
            out.extend(ex.transitions)
        out.sort(key=lambda x: x["time"], reverse=True)
        return out[:limit]
