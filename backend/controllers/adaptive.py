"""VAC-inspired adaptive (vehicle-actuated) signal controller.

VAC = Vehicle-Actuated Control. Classic actuated logic, plus congestion-aware
phase selection and a starvation guard. Rules are checked in this order every
simulation second while the signal is green:

 1. MIN GREEN  - if the green has run < min_green, keep it (safety + driver expectation).
 2. STARVATION - if any other phase has vehicles waiting and has been red for
                 >= max_red, switch to the longest-waiting one.
 3. MAX OUT    - if the green has run >= max_green and someone else is waiting,
                 terminate and serve the phase with the highest congestion demand.
 4. EXTENSION  - if a vehicle was detected in the detector zone of the green
                 lanes within the last `passage_time` seconds, extend the green.
 5. GAP OUT    - otherwise (no vehicles arriving), terminate the green and serve
                 the phase with the highest congestion demand.
 6. REST       - if nobody else is waiting, stay green (rest in green).

Every decision carries a human-readable reason.
"""
from __future__ import annotations

from backend.config import ADAPTIVE_DEFAULTS
from backend.controllers.base import BaseController
from backend.controllers.safety import Decision
from backend.data_collection.traffic_state import IntersectionState


class AdaptiveVACController(BaseController):
    name = "adaptive"
    label = "Adaptive (VAC)"

    def __init__(self, params: dict | None = None):
        super().__init__(params)
        self._last_detect: dict[str, float] = {}
        self._last_elapsed: dict[str, float] = {}

    @classmethod
    def default_params(cls) -> dict:
        return dict(ADAPTIVE_DEFAULTS)

    @staticmethod
    def _has_demand(state: IntersectionState, q: int) -> bool:
        return state.phase_queue[q] > 0 or state.phase_zone[q] > 0

    def _best(self, state: IntersectionState, candidates: list[int]) -> int:
        wait = state.signal.demand_wait
        return max(candidates, key=lambda q: (state.phase_demand[q], wait[q] if wait else 0))

    def decide(self, state: IntersectionState, now: float) -> Decision:
        P = self.params
        sig = state.signal
        tid = state.tls_id
        p, e = sig.phase_index, sig.elapsed_green

        # new green started -> reset gap timer
        if e < self._last_elapsed.get(tid, -1.0) or tid not in self._last_detect:
            self._last_detect[tid] = now
        self._last_elapsed[tid] = e
        if state.phase_zone[p] > 0:
            self._last_detect[tid] = now
        gap = now - self._last_detect[tid]

        others = [q for q in range(len(state.phase_queue)) if q != p and self._has_demand(state, q)]

        if e < P["min_green"]:
            return Decision("hold", p, f"Minimum green: {self.pname(p)} has run {e:.0f}s of "
                                       f"{P['min_green']:.0f}s minimum", "MIN_GREEN")

        wait = sig.demand_wait or [0.0] * len(state.phase_queue)
        starving = [q for q in others if wait[q] >= P["max_red"]]
        if starving:
            q = max(starving, key=lambda x: wait[x])
            return Decision("switch", q,
                            f"Starvation guard: {self.pname(q)} vehicles waited {wait[q]:.0f}s on red "
                            f"(limit {P['max_red']:.0f}s) with {state.phase_queue[q]} queued", "STARVATION")

        if e >= P["max_green"]:
            if others:
                q = self._best(state, others)
                return Decision("switch", q,
                                f"Max green {P['max_green']:.0f}s reached on {self.pname(p)}; "
                                f"serving {self.pname(q)} (demand {state.phase_demand[q]:.1f}, "
                                f"queue {state.phase_queue[q]})", "MAX_OUT")
            return Decision("hold", p, f"Max green reached but no competing demand; resting in "
                                       f"{self.pname(p)}", "REST")

        if gap < P["passage_time"]:
            return Decision("hold", p,
                            f"Extend {self.pname(p)}: {state.phase_zone[p]} vehicle(s) in detector zone, "
                            f"gap {gap:.0f}s < passage time {P['passage_time']:.0f}s "
                            f"(green {e:.0f}/{P['max_green']:.0f}s)", "EXTEND")

        if others:
            q = self._best(state, others)
            return Decision("switch", q,
                            f"Gap-out: no arrivals on {self.pname(p)} for {gap:.0f}s; "
                            f"{self.pname(q)} has highest demand {state.phase_demand[q]:.1f} "
                            f"(queue {state.phase_queue[q]})", "GAP_OUT")
        return Decision("hold", p, f"No competing demand; resting in {self.pname(p)}", "REST")
