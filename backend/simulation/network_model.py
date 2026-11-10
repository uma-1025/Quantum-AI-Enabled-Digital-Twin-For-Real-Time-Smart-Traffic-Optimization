"""Static description of the signalized network, read from the SUMO .net.xml file.

For every traffic light (TLS) we know, for each controlled link index:
  * the incoming lane and outgoing lane,
  * the approach it comes from (N, E, S, W),
  * its turning movement (r = right, s = straight, l = left).

From that we derive
  * the 4 signal PHASES (movement groups) used by all controllers,
  * the CONFLICT MATRIX used by the safety layer.

Conflict rule (right-hand traffic, explainable geometry):
  each movement is drawn as a straight chord from its entry point to its exit
  point inside a unit intersection box. Two movements from different approaches
  conflict if their chords cross or if they leave on the same exit road (merge).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from backend.config import NET_FILE

# Signal phases (movement groups). Every controller selects one of these.
PHASES: list[tuple[str, frozenset[str], frozenset[str]]] = [
    ("NS_THROUGH", frozenset({"N", "S"}), frozenset({"s", "r"})),
    ("NS_LEFT", frozenset({"N", "S"}), frozenset({"l"})),
    ("EW_THROUGH", frozenset({"E", "W"}), frozenset({"s", "r"})),
    ("EW_LEFT", frozenset({"E", "W"}), frozenset({"l"})),
]
PHASE_NAMES = [p[0] for p in PHASES]

_ENTRY = {"N": (-0.3, 1.0), "S": (0.3, -1.0), "E": (1.0, 0.3), "W": (-1.0, -0.3)}
_EXIT = {"N": (0.3, 1.0), "S": (-0.3, -1.0), "E": (1.0, -0.3), "W": (-1.0, 0.3)}
_OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
_RIGHT_OF = {"S": "W", "W": "N", "N": "E", "E": "S"}
_LEFT_OF = {v: k for k, v in _RIGHT_OF.items()}


def exit_arm(approach: str, turn: str) -> str:
    heading = _OPPOSITE[approach]
    if turn == "s":
        return heading
    if turn == "r":
        return _RIGHT_OF[heading]
    return _LEFT_OF[heading]


def _segments_intersect(p1, p2, p3, p4) -> bool:
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)

    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    return o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4)


def movements_conflict(a1: str, t1: str, a2: str, t2: str) -> bool:
    """True if movement (a1,t1) conflicts with (a2,t2)."""
    if a1 == a2:
        return False  # same approach, parallel lanes
    e1, e2 = exit_arm(a1, t1), exit_arm(a2, t2)
    if e1 == e2:
        return True  # merge conflict
    return _segments_intersect(_ENTRY[a1], _EXIT[e1], _ENTRY[a2], _EXIT[e2])


@dataclass
class Link:
    index: int
    in_lane: str
    out_lane: str
    approach: str
    turn: str


@dataclass
class Intersection:
    tls_id: str
    x: float
    y: float
    links: list[Link]
    conflicts: list[list[bool]] = field(default_factory=list)
    phase_links: list[list[int]] = field(default_factory=list)   # link indices green per phase
    phase_lanes: list[list[str]] = field(default_factory=list)   # incoming lanes per phase
    in_lanes: list[str] = field(default_factory=list)
    lane_approach: dict[str, str] = field(default_factory=dict)
    lane_phases: dict[str, list[int]] = field(default_factory=dict)

    @property
    def n_links(self) -> int:
        return len(self.links)

    def green_state(self, phase: int) -> str:
        green = set(self.phase_links[phase])
        return "".join("G" if i in green else "r" for i in range(self.n_links))


@dataclass
class NetworkModel:
    intersections: dict[str, Intersection]
    lane_length: dict[str, float]
    lane_shapes: dict[str, list[tuple[float, float]]]
    downstream_lanes: list[str]       # outgoing lanes of TLS links (for max-pressure)
    boundary: tuple[float, float, float, float]

    @property
    def tls_ids(self) -> list[str]:
        return sorted(self.intersections)

    @property
    def monitored_lanes(self) -> list[str]:
        lanes = []
        for t in self.tls_ids:
            lanes.extend(self.intersections[t].in_lanes)
        return lanes


def _approach(from_xy, junction_xy) -> str:
    dx, dy = from_xy[0] - junction_xy[0], from_xy[1] - junction_xy[1]
    if abs(dy) >= abs(dx):
        return "N" if dy > 0 else "S"
    return "E" if dx > 0 else "W"


def _turn(direction: str) -> str:
    d = direction.lower()
    if d in ("s", "r", "l"):
        return d
    if d == "t":
        return "l"
    return "s"


@lru_cache(maxsize=4)
def load_network(net_file: str | Path = NET_FILE) -> NetworkModel:
    import sumolib  # lazy import

    net_file = Path(net_file)
    if not net_file.exists():
        raise FileNotFoundError(
            f"Network file {net_file} not found. Run: python -m backend.sumo_config.build_network"
        )
    net = sumolib.net.readNet(str(net_file), withInternal=False)
    intersections: dict[str, Intersection] = {}
    downstream: set[str] = set()

    for tls in net.getTrafficLights():
        tid = tls.getID()
        node = net.getNode(tid)
        jx, jy = node.getCoord()
        links: list[Link] = []
        for in_lane, out_lane, idx in tls.getConnections():
            from_node = in_lane.getEdge().getFromNode()
            appr = _approach(from_node.getCoord(), (jx, jy))
            conn = in_lane.getEdge().getConnections(out_lane.getEdge())
            direction = "s"
            for c in conn:
                if c.getFromLane() == in_lane and c.getToLane() == out_lane:
                    direction = c.getDirection()
                    break
            links.append(Link(idx, in_lane.getID(), out_lane.getID(), appr, _turn(direction)))
            downstream.add(out_lane.getID())
        links.sort(key=lambda l: l.index)
        inter = Intersection(tid, jx, jy, links)
        n = len(links)
        inter.conflicts = [[False] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    a, b = links[i], links[j]
                    inter.conflicts[i][j] = movements_conflict(a.approach, a.turn, b.approach, b.turn)
        for name, apprs, turns in PHASES:
            idxs = [l.index for l in links if l.approach in apprs and l.turn in turns]
            inter.phase_links.append(idxs)
            lanes = sorted({links[i].in_lane for i in idxs})
            inter.phase_lanes.append(lanes)
        inter.in_lanes = sorted({l.in_lane for l in links})
        inter.lane_approach = {l.in_lane: l.approach for l in links}
        for lane in inter.in_lanes:
            inter.lane_phases[lane] = [p for p, lanes in enumerate(inter.phase_lanes) if lane in lanes]
        intersections[tid] = inter

    lane_length, lane_shapes = {}, {}
    for edge in net.getEdges():
        for lane in edge.getLanes():
            lane_length[lane.getID()] = lane.getLength()
            lane_shapes[lane.getID()] = [tuple(p) for p in lane.getShape()]
    (xmin, ymin), (xmax, ymax) = net.getBBoxXY()
    return NetworkModel(intersections, lane_length, lane_shapes, sorted(downstream),
                        (xmin, ymin, xmax, ymax))


def validate_phase_plan(model: NetworkModel) -> list[str]:
    """Return a list of problems; empty list means every phase is conflict-free."""
    problems = []
    for tid, inter in model.intersections.items():
        for p, idxs in enumerate(inter.phase_links):
            if not idxs:
                problems.append(f"{tid}: phase {PHASE_NAMES[p]} has no links")
            for i in idxs:
                for j in idxs:
                    if i < j and inter.conflicts[i][j]:
                        problems.append(f"{tid}: phase {PHASE_NAMES[p]} links {i},{j} conflict")
        covered = set().union(*map(set, inter.phase_links))
        missing = set(range(inter.n_links)) - covered
        if missing:
            problems.append(f"{tid}: links {sorted(missing)} never receive green")
    return problems
