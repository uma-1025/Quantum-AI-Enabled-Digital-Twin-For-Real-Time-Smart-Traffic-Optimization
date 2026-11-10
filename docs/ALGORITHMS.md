# Algorithms

All parameters below are defaults from `backend/config.py`. They can be overridden per run
through the API's `params` field.

## 1. Signal phases

Each junction has 16 controlled movements (4 approaches × right, straight on lane 0, straight on
lane 1, left on lane 2), grouped into 4 phases:

| Index | Phase | Green movements |
|---|---|---|
| 0 | NS_THROUGH | N and S approaches: straight + right |
| 1 | NS_LEFT | N and S approaches: left (opposing lefts do not cross) |
| 2 | EW_THROUGH | E and W approaches: straight + right |
| 3 | EW_LEFT | E and W approaches: left |

Example state strings for C1: NS_THROUGH `GGGrrrrrGGGrrrrr`, EW_LEFT `rrrrrrrGrrrrrrrG`.

## 2. Conflict matrix (safety)

```
entry points (unit box, right-hand traffic):  N(-0.3, 1)  S(0.3,-1)  E(1, 0.3)  W(-1,-0.3)
exit points:                                  N(0.3, 1)   S(-0.3,-1) E(1,-0.3)  W(-1, 0.3)
exit arm = heading after the turn (right = clockwise, left = counter-clockwise)

conflict(m1, m2) =
    false                       if same approach
    true                        if same exit arm (merge)
    segments_cross(entry1→exit1, entry2→exit2)   otherwise
```
`validate_phase_plan()` checks that no phase contains a conflicting pair and that every movement
appears in at least one phase. Both checks pass.

## 3. Lane congestion score

```
capacity   = lane_length / 7.5
score      = 100 × [ 0.40·min(queue/capacity,1) + 0.20·occupancy/100
                   + 0.25·min(avg_wait/60,1)    + 0.15·min(arrivals_per_min/12,1) ]
level      = Free <25 ≤ Moderate <50 ≤ Heavy <75 ≤ Severe
queue_pressure(lane) = queue(lane) − mean(queue of the lanes it feeds)
phase_demand(p)      = Σ score(lane) for lanes served by p
priority_phase       = argmax phase_demand
```

## 4. Adaptive controller (VAC-inspired) – pseudocode

```
params: min_green=8, max_green=50, passage_time=3, detection_distance=40, max_red=90

every second, for each junction showing GREEN on phase p with elapsed green e:
    if a vehicle is within 40 m of the stop line on p's lanes: last_detect = now
    gap    = now - last_detect
    others = phases ≠ p with queue > 0 or a vehicle in the detector zone
    wait[q]= seconds phase q's vehicles have waited on red

    if e < min_green:                         HOLD   "MIN_GREEN"
    elif any q in others with wait[q] ≥ max_red:
                                              SWITCH to the longest-waiting q   "STARVATION"
    elif e ≥ max_green and others:            SWITCH to argmax demand(others)   "MAX_OUT"
    elif e ≥ max_green:                       HOLD   "REST"
    elif gap < passage_time:                  HOLD   "EXTEND"
    elif others:                              SWITCH to argmax demand(others)   "GAP_OUT"
    else:                                     HOLD   "REST"
```
Ties on demand are broken by the longest waiting time.

## 5. Max-Pressure controller

```
params: min_green=8, max_green=50, switch_threshold=1.0

pressure(p) = Σ_{movement (in→out) in p} [ queue(in)/n_movements_from(in) − queue(out) ]

if e < min_green:                                            HOLD
if e ≥ max_green and some other phase has queue > 0:         SWITCH to max pressure among them
best = argmax pressure
if best ≠ p and pressure(best) − pressure(p) > threshold:    SWITCH to best
else:                                                        HOLD
```
Queues are halting vehicles (speed < 0.1 m/s) from TraCI.

## 6. Fixed-Time controller

```
green_times = [30, 12, 30, 12]
if elapsed_green ≥ green_times[p]: SWITCH to (p+1) mod 4   else HOLD
cycle = 30+12+30+12 + 4×(3 amber + 2 all-red) = 104 s
```

## 7. Safety executor (state machine)

```
GREEN(p) --request(q), elapsed ≥ 5 s--> YELLOW (all green → 'y', 3 s)
YELLOW   --3 s-->                          ALL_RED ('r' everywhere, 2 s)
ALL_RED  --2 s-->                          GREEN(q)   (phase_changes += 1)

before sending any state S (previous P):
  len(S) == links,  chars ⊂ {G,g,y,r,…}
  no i,j green with conflict[i][j]
  no link with P[i]∈{G,g} and S[i]='r'          (amber required)
  no link newly green while a conflicting link is 'y'
→ otherwise raise SafetyViolation (the state is NOT sent)
```

## 8. Metrics

| Metric | Formula |
|---|---|
| Waiting time | Σ seconds with speed < 0.1 m/s, per vehicle; averaged over completed trips |
| Stops | count of moving → halted transitions per vehicle |
| Travel time | arrival time − departure time |
| Throughput | number of completed trips (also per hour) |
| Mean queue | mean over time of the mean halting count across the 48 approach lanes |
| Max queue | largest halting count seen on any single lane |
| Phase changes | completed transitions to a new green (all junctions) |
| Latency | `perf_counter` around `decide()`: mean, 95th percentile, max (ms) |
| Starvation event | a phase with vehicles waiting on red ≥ 120 s; counted once until served |
| % vs Fixed-Time | (value − fixed) / fixed × 100, from measured means only |

## 9. Demand generation

For each of the 8 entries: Poisson arrivals with rate λ (low 150, medium 300, high 450 veh/h).
Each trip goes to a random exit other than its own entry. The vehicle type is drawn from
car 85 %, truck 10 %, bus 5 %. NumPy's `default_rng(seed)` makes it reproducible: the same seed
gives the identical file.
