"""Traffic demand and congestion analysis (explainable, configurable).

Lane congestion score (0-100):
    score = 100 * ( w_q * min(queue / capacity, 1)
                  + w_o * occupancy / 100
                  + w_w * min(avg_wait / WAITING_NORM_S, 1)
                  + w_a * min(arrival_rate / ARRIVAL_NORM_VPM, 1) )
    capacity = lane_length / VEHICLE_SPACE_M  (how many vehicles fit on the lane)

Queue pressure of a lane = its queue minus the average queue on the lanes it
feeds (downstream). Positive = vehicles are piling up here faster than ahead.

Phase demand   = sum of congestion scores of the lanes served by the phase.
Phase pressure = Max-Pressure weight: sum over the phase's movements of
                 (incoming queue shared by the lane's movements - outgoing queue).
"""
from __future__ import annotations

from backend.config import (ARRIVAL_NORM_VPM, CONGESTION_LEVELS, CONGESTION_WEIGHTS,
                            VEHICLE_SPACE_M, WAITING_NORM_S)
from backend.data_collection.traffic_state import IntersectionState, LaneState
from backend.simulation.network_model import Intersection


def congestion_level(score: float) -> str:
    for limit, label in CONGESTION_LEVELS:
        if score < limit:
            return label
    return CONGESTION_LEVELS[-1][1]


def lane_congestion_score(lane: LaneState, weights: dict | None = None) -> float:
    w = weights or CONGESTION_WEIGHTS
    capacity = max(lane.length / VEHICLE_SPACE_M, 1.0)
    q = min(lane.queue_length / capacity, 1.0)
    o = min(lane.occupancy / 100.0, 1.0)
    wt = min(lane.avg_waiting_time / WAITING_NORM_S, 1.0)
    a = min(lane.arrival_rate / ARRIVAL_NORM_VPM, 1.0)
    score = 100.0 * (w["queue"] * q + w["occupancy"] * o + w["waiting"] * wt + w["arrival"] * a)
    return round(max(0.0, min(score, 100.0)), 2)


def analyse_intersection(inter: Intersection, lanes: dict[str, LaneState],
                         downstream_queue: dict[str, int], state: IntersectionState,
                         weights: dict | None = None) -> IntersectionState:
    """Fill the analysis fields of `state` in place and return it."""
    # lane scores + queue pressure
    out_by_lane: dict[str, list[str]] = {}
    links_from_lane: dict[str, int] = {}
    for link in inter.links:
        out_by_lane.setdefault(link.in_lane, []).append(link.out_lane)
        links_from_lane[link.in_lane] = links_from_lane.get(link.in_lane, 0) + 1
    for lane_id, lane in lanes.items():
        lane.congestion_score = lane_congestion_score(lane, weights)
        outs = out_by_lane.get(lane_id, [])
        down = sum(downstream_queue.get(o, 0) for o in outs) / len(outs) if outs else 0.0
        lane.queue_pressure = round(lane.queue_length - down, 2)

    n_phases = len(inter.phase_links)
    demand, pressure, pqueue, pzone = [], [], [], []
    for p in range(n_phases):
        p_lanes = inter.phase_lanes[p]
        demand.append(round(sum(lanes[l].congestion_score for l in p_lanes if l in lanes), 2))
        pqueue.append(int(sum(lanes[l].queue_length for l in p_lanes if l in lanes)))
        pzone.append(int(sum(lanes[l].vehicles_in_zone for l in p_lanes if l in lanes)))
        pr = 0.0
        for idx in inter.phase_links[p]:
            link = inter.links[idx]
            ln = lanes.get(link.in_lane)
            if ln is None:
                continue
            q_in = ln.queue_length / links_from_lane[link.in_lane]
            pr += q_in - downstream_queue.get(link.out_lane, 0)
        pressure.append(round(pr, 2))

    approach_scores: dict[str, float] = {}
    for lane in lanes.values():
        approach_scores[lane.approach] = approach_scores.get(lane.approach, 0.0) + lane.congestion_score
    # report the mean lane score per approach so it stays on the 0-100 scale
    counts: dict[str, int] = {}
    for lane in lanes.values():
        counts[lane.approach] = counts.get(lane.approach, 0) + 1
    approach_scores = {a: round(s / counts[a], 2) for a, s in approach_scores.items()}

    state.phase_demand = demand
    state.phase_pressure = pressure
    state.phase_queue = pqueue
    state.phase_zone = pzone
    state.approach_scores = approach_scores
    state.most_congested_approach = max(approach_scores, key=approach_scores.get) if approach_scores else ""
    state.priority_phase = max(range(n_phases), key=lambda p: demand[p]) if n_phases else 0
    avg = sum(l.congestion_score for l in lanes.values()) / len(lanes) if lanes else 0.0
    state.congestion_level = congestion_level(max(approach_scores.values(), default=avg))
    return state


def network_congestion_index(states: dict[str, IntersectionState]) -> float:
    scores = [l.congestion_score for s in states.values() for l in s.lanes.values()]
    return round(sum(scores) / len(scores), 2) if scores else 0.0


def busiest_lane(states: dict[str, IntersectionState]) -> LaneState | None:
    lanes = [l for s in states.values() for l in s.lanes.values()]
    if not lanes:
        return None
    return max(lanes, key=lambda l: (l.congestion_score, l.queue_length))
