"""Common controller interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from backend.controllers.safety import Decision
from backend.data_collection.traffic_state import IntersectionState
from backend.simulation.network_model import PHASE_NAMES


class BaseController(ABC):
    name = "base"
    label = "Base"

    def __init__(self, params: dict | None = None):
        self.params = dict(self.default_params())
        if params:
            unknown = set(params) - set(self.params)
            if unknown:
                raise ValueError(f"Unknown parameters for {self.name}: {sorted(unknown)}")
            self.params.update(params)
        self.validate_params()

    @classmethod
    def default_params(cls) -> dict:
        return {}

    def validate_params(self) -> None:
        p = self.params
        if "min_green" in p and "max_green" in p and p["min_green"] > p["max_green"]:
            raise ValueError("min_green must not exceed max_green")
        for k, v in p.items():
            if isinstance(v, (int, float)) and v < 0:
                raise ValueError(f"parameter {k} must be non-negative")

    @abstractmethod
    def decide(self, state: IntersectionState, now: float) -> Decision:
        """Return a Decision for one intersection (called only while in GREEN)."""

    @staticmethod
    def pname(p: int) -> str:
        return PHASE_NAMES[p]
