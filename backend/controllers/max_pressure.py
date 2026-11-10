"""Max-Pressure controller (Varaiya, 2013).

Pressure of a phase = sum over its movements of
    (queue on the incoming lane, shared among that lane's movements)
  - (queue on the outgoing lane the movement feeds).

After the minimum green, the phase with the highest pressure is selected.
A small hysteresis (`switch_threshold`) avoids switching for negligible gains,
and `max_green` caps any green when another phase has vehicles waiting.
Amber / all-red and conflict checks come from the shared safety layer.
"""
from __future__ import annotations

from backend.config import MAX_PRESSURE_DEFAULTS
from backend.controllers.base import BaseController
from backend.controllers.safety import Decision
from backend.data_collection.traffic_state import IntersectionState


class MaxPressureController(BaseController):
    name = "max_pressure"
    label = "Max-Pressure"

    @classmethod
    def default_params(cls) -> dict:
        return dict(MAX_PRESSURE_DEFAULTS)

    def decide(self, state: IntersectionState, now: float) -> Decision:
        P = self.params
        sig = state.signal
        p, e = sig.phase_index, sig.elapsed_green
        pr = state.phase_pressure
        n = len(pr)

        if e < P["min_green"]:
            return Decision("hold", p, f"Minimum green: {self.pname(p)} {e:.0f}/{P['min_green']:.0f}s",
                            "MIN_GREEN")

        if e >= P["max_green"]:
            waiting = [q for q in range(n) if q != p and state.phase_queue[q] > 0]
            if waiting:
                q = max(waiting, key=lambda x: pr[x])
                return Decision("switch", q,
                                f"Max green {P['max_green']:.0f}s on {self.pname(p)}; highest remaining "
                                f"pressure {self.pname(q)} = {pr[q]:.1f}", "MAX_OUT")

        best = max(range(n), key=lambda q: pr[q])
        if best != p and pr[best] - pr[p] > P["switch_threshold"]:
            return Decision("switch", best,
                            f"Pressure {self.pname(best)} = {pr[best]:.1f} exceeds current "
                            f"{self.pname(p)} = {pr[p]:.1f} by more than {P['switch_threshold']:.1f}",
                            "PRESSURE")
        return Decision("hold", p, f"Keep {self.pname(p)}: pressure {pr[p]:.1f} is the highest "
                                   f"(max other {max([pr[q] for q in range(n) if q != p], default=0):.1f})",
                        "PRESSURE")
