"""Conventional fixed-time controller (baseline).

Cycles NS_THROUGH -> NS_LEFT -> EW_THROUGH -> EW_LEFT with pre-set green times,
regardless of traffic. Amber and all-red are inserted by the safety layer.
"""
from __future__ import annotations

from backend.config import FIXED_TIME_DEFAULTS
from backend.controllers.base import BaseController
from backend.controllers.safety import Decision
from backend.data_collection.traffic_state import IntersectionState


class FixedTimeController(BaseController):
    name = "fixed_time"
    label = "Fixed-Time"

    @classmethod
    def default_params(cls) -> dict:
        return {"green_times": list(FIXED_TIME_DEFAULTS["green_times"])}

    def validate_params(self) -> None:
        g = self.params["green_times"]
        if len(g) != 4 or any(float(x) <= 0 for x in g):
            raise ValueError("green_times must be 4 positive numbers")

    def decide(self, state: IntersectionState, now: float) -> Decision:
        sig = state.signal
        p = sig.phase_index
        green = float(self.params["green_times"][p])
        nxt = (p + 1) % len(self.params["green_times"])
        if sig.elapsed_green >= green:
            return Decision("switch", nxt,
                            f"Fixed plan: {self.pname(p)} green of {green:.0f}s completed -> {self.pname(nxt)}",
                            "FIXED_PLAN")
        return Decision("hold", p,
                        f"Fixed plan: {self.pname(p)} {sig.elapsed_green:.0f}/{green:.0f}s", "FIXED_PLAN")
