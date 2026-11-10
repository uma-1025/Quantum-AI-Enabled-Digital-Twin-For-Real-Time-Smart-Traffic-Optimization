# API Documentation

Base URL: `http://127.0.0.1:8000`. Interactive Swagger UI: **`/docs`**. OpenAPI JSON: `/openapi.json`.
All bodies are JSON. Errors return `{"detail": "..."}`:
**422** = invalid input, **409** = invalid state (for example already running),
**404** = no data or not found, **400** = bad request or SUMO could not start.

## System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Status of the API, SUMO, TraCI, database and the live run |
| GET | `/config` | Scenarios, controllers and their default parameters, phases, safety timings, weights |
| GET | `/network` | Lane shapes, junction positions, signal links, phase states, phase-plan check |

Example `GET /health` (real output):
```json
{"api":"ok","network_file":true,"sumo_binary":".../sumo/bin/sumo","sumo_version":"Eclipse SUMO sumo 1.28.0",
 "sumo":"ok","traci":"ok","database":"ok","live_status":"idle"}
```

## Live simulation

| Method | Path | Body | Description |
|---|---|---|---|
| POST | `/simulation/start` | `StartRequest` | Start SUMO and the selected controller in the background |
| POST | `/simulation/pause` | – | Pause stepping (409 if not running) |
| POST | `/simulation/resume` | – | Resume (409 if not paused) |
| POST | `/simulation/reset` | – | Stop and discard the live run |
| POST | `/simulation/speed` | `{"speed": 20}` | Change simulated seconds per wall second (0 = as fast as possible) |
| GET | `/simulation/status` | – | Status, simulation time, progress, config, saved experiment id |
| GET | `/simulation/state` | – | Full traffic state: 48 lanes, 4 intersections, analysis, KPIs, latest decisions |
| GET | `/simulation/snapshot` | – | Vehicle positions/speeds/types + signal strings (for the map) |
| GET | `/simulation/history` | – | Time series so far + running summary metrics |
| GET | `/simulation/decisions?limit=100` | – | Decision log, latest decision per junction, signal transitions |

`StartRequest`:
```json
{"scenario":"medium","controller":"adaptive","seed":42,"duration":1800,"speed":10,"gui":false,
 "params":{"min_green":8,"max_green":50}}
```
* `scenario`: `low` | `medium` | `high`
* `controller`: `fixed_time` | `adaptive` | `max_pressure`
* `duration`: 60–14400 s; `speed`: 0–1000; `gui: true` also opens sumo-gui on the backend machine
* `params`: optional overrides (unknown keys are rejected)

Example decision (from `/simulation/decisions`, real output):
```json
{"sim_time":298.0,"tls_id":"C4","action":"switch","category":"GAP_OUT","from_phase":"NS_THROUGH",
 "to_phase":"NS_LEFT","reason":"Gap-out: no arrivals on NS_THROUGH for 3s; NS_LEFT has highest demand 47.6 (queue 7)",
 "accepted":true}
```
When a live run reaches its duration, it is saved automatically (`mode = "live"`).

## Experiments

| Method | Path | Description |
|---|---|---|
| POST | `/experiments/compare` | Start a fair comparison job (409 if one is already running) |
| GET | `/experiments/jobs` | All jobs in this backend session |
| GET | `/experiments/jobs/{job_id}` | Status, progress, per-run results, aggregate |
| GET | `/experiments?limit=500&group_id=` | Stored experiments with their results |
| GET | `/experiments/{id}` | One experiment + results |
| GET | `/experiments/{id}/timeseries` | Time series (every 10 s) |
| GET | `/experiments/{id}/decisions` | Stored decision log |
| GET | `/experiments/groups/{group_id}/aggregate` | Mean/std per controller + % vs Fixed-Time |
| DELETE | `/experiments/{id}` | Delete an experiment |

`CompareRequest`:
```json
{"scenario":"high","controllers":["fixed_time","adaptive","max_pressure"],"seeds":[1,2,3],"duration":1800}
```
For each seed, every controller is run on the identical demand file with the same SUMO seed.

## Reports

| Method | Path | Returns |
|---|---|---|
| GET | `/reports/csv?ids=1,2,3` | `text/csv` (all experiments if `ids` is omitted) |
| GET | `/reports/pdf?ids=1,2,3` | `application/pdf`: summary table, metric bar charts, time-series page |

## curl examples
```bash
curl -X POST http://127.0.0.1:8000/simulation/start -H "Content-Type: application/json" \
     -d "{\"scenario\":\"high\",\"controller\":\"adaptive\",\"duration\":600,\"speed\":50}"
curl http://127.0.0.1:8000/simulation/state
curl -X POST http://127.0.0.1:8000/simulation/pause
curl -o report.pdf "http://127.0.0.1:8000/reports/pdf"
```
