# Database Schema

Defined with SQLAlchemy Core in `backend/database/db.py`. The tables are created automatically on
first start. The default URL is `sqlite:///data/vac_traffic.db`; override it with the
`DATABASE_URL` environment variable.

```mermaid
erDiagram
  experiments ||--|| results : "1 summary"
  experiments ||--o{ timeseries : "every 10 s"
  experiments ||--o{ decisions : "signal decisions"
```

## experiments
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | auto-increment |
| created_at | DATETIME (tz) | UTC |
| group_id | VARCHAR(64), indexed | comparison batch id (NULL for live runs) |
| mode | VARCHAR(16) | `live` or `batch` |
| scenario | VARCHAR(32) | low / medium / high |
| controller | VARCHAR(32) | fixed_time / adaptive / max_pressure |
| seed | INTEGER | random seed for demand and SUMO |
| duration | INTEGER | simulated seconds |
| status | VARCHAR(16) | completed |
| params | TEXT (JSON) | controller parameters actually used |
| sumo_version | VARCHAR(64) | e.g. "Eclipse SUMO sumo 1.28.0" |

## results (1 row per experiment)
| Column | Type | Meaning |
|---|---|---|
| experiment_id | INTEGER PK, FK → experiments.id | |
| vehicles_departed | INTEGER | vehicles that entered the network |
| throughput | INTEGER | completed trips |
| throughput_per_hour | FLOAT | completed trips × 3600 / duration |
| vehicles_remaining | INTEGER | still in the network at the end |
| avg_waiting_time | FLOAT | s, completed trips |
| avg_waiting_time_all | FLOAT | s, including unfinished vehicles |
| avg_travel_time | FLOAT | s |
| stops_per_vehicle | FLOAT | |
| mean_queue_length | FLOAT | mean halted vehicles per approach lane |
| mean_total_queue | FLOAT | mean halted vehicles over all 48 lanes |
| max_queue_length | INTEGER | largest single-lane queue |
| max_total_queue | INTEGER | largest network-wide queue |
| avg_speed | FLOAT | m/s, mean of per-step vehicle means |
| phase_changes | INTEGER | |
| latency_mean_ms / latency_p95_ms / latency_max_ms | FLOAT | controller decision time |
| starvation_events | INTEGER | |
| teleports | INTEGER | SUMO gridlock removals |
| safety_rejections | INTEGER | decisions rejected by the safety layer |
| sim_time | FLOAT | final simulated time |
| wall_time_s | FLOAT | real time the run took |

## timeseries
`id` PK, `experiment_id` FK (indexed), `sim_time`, `vehicles`, `total_queue`, `avg_waiting`
(mean accumulated waiting time of vehicles currently in the network), `avg_speed`, `throughput`
(cumulative), `throughput_rate` (veh/h in the last interval), `congestion_index`, `phase_changes`
(cumulative), `latency_ms` (mean in the interval).

## decisions
`id` PK, `experiment_id` FK (indexed), `sim_time`, `tls_id`, `action` (hold/switch), `category`
(MIN_GREEN, EXTEND, GAP_OUT, MAX_OUT, STARVATION, REST, PRESSURE, FIXED_PLAN), `from_phase`,
`to_phase`, `reason`, `accepted`. Every switch is stored, plus each change of decision category,
so the table stays compact.

## Operations (functions in db.py)
`save_experiment` (one transaction: experiment + result + series + decisions), `list_experiments`
(join with results, optional group filter), `get_experiment`, `get_timeseries`, `get_decisions`,
`delete_experiment`.

## Switching to PostgreSQL
```bash
pip install psycopg2-binary
# Windows:  set DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/vac_traffic
# macOS/Linux: export DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/vac_traffic
python -m uvicorn backend.main:app --port 8000
```
Only portable types are used (Integer, Float, String, Text, Boolean, DateTime), so no code changes
are needed. *Status: verified on PostgreSQL 16.15. All 51 tests pass, and a full comparison
run gives results identical to SQLite (see TESTING_REPORT.md section 7). To run the tests on
PostgreSQL, set `VAC_TEST_DATABASE_URL` to the database URL before `python -m pytest`.*
