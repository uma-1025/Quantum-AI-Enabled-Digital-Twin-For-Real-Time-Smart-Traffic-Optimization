"""Signal safety layer.

Controllers only *request* a phase. The SignalExecutor decides whether the
request is allowed and drives the safe transition sequence:

    GREEN(current) --(min green served)--> YELLOW --> ALL_RED --> GREEN(target)

Before every state string is sent to SUMO it is validated:
  1. no two conflicting movements are green at the same time (conflict matrix),
  2. a green movement never jumps straight to red (it must show yellow first),
  3. a movement never becomes green while a conflicting movement is yellow,
  4. the string has the right length and only legal characters.
An invalid state raises SafetyViolation and is NEVER sent to SUMO.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.config import ALL_RED_TIME_S, SAFETY_MIN_GREEN_S, YELLOW_TIME_S
from backend.data_collection.traffic_state import SignalState
from backend.simulation.network_model import PHASE_NAMES, Intersection

GREEN, YELLOW, ALL_RED = "GREEN", "YELLOW", "ALL_RED"
LEGAL_CHARS = set("GgyrRuoO s")


class SafetyViolation(RuntimeError):
    pass


def validate_state(inter: Intersection, state: str, previous: str | None = None) -> None:
    n = inter.n_links
    if len(state) != n:
        raise SafetyViolation(f"{inter.tls_id}: state length {len(state)} != {n} links")
    bad = set(state) - LEGAL_CHARS
    if bad:
        raise SafetyViolation(f"{inter.tls_id}: illegal signal characters {bad}")
    green = [i for i, c in enumerate(state) if c in "Gg"]
    for a in green:
        for b in green:
            if a < b and inter.conflicts[a][b] and not (state[a] == "g" or state[b] == "g"):
                raise SafetyViolation(
                    f"{inter.tls_id}: conflicting movements {a} and {b} both green in '{state}'")
    if previous is not None:
        for i, (old, new) in enumerate(zip(previous, state)):
            if old in "Gg" and new in "rR":
                raise SafetyViolation(
                    f"{inter.tls_id}: link {i} switched green->red without amber")
        yellow_prev = [i for i, c in enumerate(previous) if c == "y"]
        for i in green:
            if previous[i] not in "Gg":
                for j in yellow_prev:
                    if inter.conflicts[i][j]:
                        raise SafetyViolation(
                            f"{inter.tls_id}: link {i} turned green while conflicting link {j} amber")


@dataclass
class Decision:
    action: str          # "hold" | "switch"
    target_phase: int
    reason: str
    category: str = ""   # short tag e.g. MIN_GREEN, GAP_OUT, MAX_OUT, STARVATION, PRESSURE, FIXED_PLAN


class SignalExecutor:
    """Owns the real signal of one intersection and enforces all safety rules."""

    def __init__(self, inter: Intersection, initial_phase: int = 0,
                 yellow_time: float = YELLOW_TIME_S, all_red_time: float = ALL_RED_TIME_S,
                 min_green: float = SAFETY_MIN_GREEN_S):
        self.inter = inter
        self.yellow_time = yellow_time
        self.all_red_time = all_red_time
        self.min_green = min_green
        self.n_phases = len(inter.phase_links)
        self.phase = initial_phase
        self.target: int | None = None
        self.mode = GREEN
        self.time_in_mode = 0.0
        self.elapsed_green = 0.0
        self.last_green_end = [0.0] * self.n_phases
        self.wait_since: list[float | None] = [None] * self.n_phases
        self.state = inter.green_state(initial_phase)
        validate_state(inter, self.state)
        self.phase_changes = 0
        self.rejected_requests = 0
        self.transitions: list[dict] = []   # signal transition log (mode changes)

    # ---------------------------------------------------------------- helpers
    def red_times(self, now: float) -> list[float]:
        out = []
        for p in range(self.n_phases):
            if p == self.phase and self.mode == GREEN:
                out.append(0.0)
            else:
                out.append(round(now - self.last_green_end[p], 1))
        return out

    def update_demand(self, now: float, phase_queue: list[int]) -> None:
        """Track how long each phase has had vehicles waiting while not being served."""
        for p in range(self.n_phases):
            served = self.mode == GREEN and p == self.phase
            if served or phase_queue[p] <= 0:
                self.wait_since[p] = None
            elif self.wait_since[p] is None:
                self.wait_since[p] = now

    def demand_wait(self, now: float) -> list[float]:
        return [0.0 if w is None else round(now - w, 1) for w in self.wait_since]

    def signal_state(self, now: float) -> SignalState:
        return SignalState(
            tls_id=self.inter.tls_id, phase_index=self.phase, phase_name=PHASE_NAMES[self.phase],
            mode=self.mode, state_string=self.state, elapsed_green=round(self.elapsed_green, 1),
            time_in_mode=round(self.time_in_mode, 1), target_phase=self.target,
            red_time=self.red_times(now), demand_wait=self.demand_wait(now),
        )

    def _yellow_state(self, target: int) -> str:
        # every currently-green movement shows amber (the all-red that follows is full red)
        return "".join("y" if c in "Gg" else c for c in self.state)

    def _apply(self, conn, new_state: str, now: float, note: str) -> None:
        validate_state(self.inter, new_state, self.state)  # raises -> never sent
        if conn is not None:
            conn.trafficlight.setRedYellowGreenState(self.inter.tls_id, new_state)
        self.transitions.append({"time": now, "tls_id": self.inter.tls_id, "mode": self.mode,
                                 "phase": PHASE_NAMES[self.phase], "state": new_state, "note": note})
        if len(self.transitions) > 500:
            self.transitions = self.transitions[-500:]
        self.state = new_state

    # ------------------------------------------------------------------ API
    def install(self, conn) -> None:
        """Take over the signal in SUMO (replaces SUMO's built-in program)."""
        conn.trafficlight.setRedYellowGreenState(self.inter.tls_id, self.state)

    def can_decide(self) -> bool:
        return self.mode == GREEN

    def request(self, conn, decision: Decision, now: float) -> bool:
        """Apply a controller decision. Returns True if a transition was started."""
        if decision.action != "switch" or decision.target_phase == self.phase:
            return False
        if self.mode != GREEN:
            self.rejected_requests += 1
            return False
        if not 0 <= decision.target_phase < self.n_phases:
            self.rejected_requests += 1
            raise SafetyViolation(f"invalid phase index {decision.target_phase}")
        if self.elapsed_green < self.min_green:
            self.rejected_requests += 1
            return False
        self.target = decision.target_phase
        self.mode = YELLOW
        self.time_in_mode = 0.0
        self.last_green_end[self.phase] = now
        self._apply(conn, self._yellow_state(self.target), now,
                    f"amber: ending {PHASE_NAMES[self.phase]} for {PHASE_NAMES[self.target]}")
        return True

    def tick(self, conn, dt: float, now: float) -> None:
        """Advance timers by one simulation step and progress transitions."""
        self.time_in_mode += dt
        if self.mode == GREEN:
            self.elapsed_green += dt
            return
        if self.mode == YELLOW and self.time_in_mode >= self.yellow_time - 1e-9:
            self.mode = ALL_RED
            self.time_in_mode = 0.0
            self._apply(conn, "r" * self.inter.n_links, now, "all-red clearance")
            if self.all_red_time > 0:
                return
        if self.mode == ALL_RED and self.time_in_mode >= self.all_red_time - 1e-9:
            self.phase = self.target if self.target is not None else self.phase
            self.target = None
            self.mode = GREEN
            self.time_in_mode = 0.0
            self.elapsed_green = 0.0
            self.phase_changes += 1
            self._apply(conn, self.inter.green_state(self.phase), now,
                        f"green: {PHASE_NAMES[self.phase]}")
