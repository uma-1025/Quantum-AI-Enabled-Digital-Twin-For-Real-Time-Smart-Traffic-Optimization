# Testing Report

**Environments tested**
* **Development:** Linux x86-64, Python 3.13.18, SUMO 1.28.0 (eclipse-sumo pip), FastAPI 0.162.2,
  Streamlit 1.67.0, headless Chrome for UI checks, SQLite **and PostgreSQL 16.15**. Date: 10 Nov 2026.
* **Target laptop:** Windows (x64). Results in section 6 were reported by the project owner.

## 1. How to run the tests
```bash
python -m pytest -v            # all 51 tests, about 25 s
python scripts/check_environment.py
```
The tests use a temporary database, so your stored results are never touched.

## 2. Automated test results – 51 / 51 passed (23.45 s)

| File | Tests | What is verified |
|---|---|---|
| `test_network_and_safety.py` | 14 | 4 junctions × 16 links × 12 lanes; phase plan conflict-free and complete; 6 conflict-matrix cases (symmetric); validator rejects conflicting greens, green→red without amber, wrong length or characters; executor sequence (min green refusal → 3 s amber → 2 s all-red → new green); invalid phase index; waiting-on-red tracking |
| `test_analysis_and_controllers.py` | 25 | Missing/NaN/negative values cleaned; caps; invalid lane rejected; congestion formula (exact value), bounds, 6 level boundaries; phase demand and pressure incl. downstream subtraction; Fixed-Time cycling + parameter validation; Adaptive MIN_GREEN, EXTEND, GAP_OUT (selects highest demand), MAX_OUT, STARVATION (overrides higher demand), REST, bad parameters; Max-Pressure switching, min green, hysteresis; unknown controller |
| `test_simulation_integration.py` | 7 | **Real SUMO via TraCI**: demand deterministic per seed and different across seeds, no U-turn trips, high > low demand; unknown scenario rejected; for **each controller** a 400 s run where, **every second, the signal string read back from SUMO equals what the safety layer sent and passes re-validation**, amber and all-red were shown, phases changed, vehicles completed trips, 0 safety rejections; identical route files for fairness; 48-lane state consistent (queue ≤ count, occupancy and score in range) |
| `test_api_and_db.py` | 5 | `/health` (SUMO, TraCI, DB ok), `/config`, `/network`; 422 for bad scenario/controller/duration, 409 for pause/resume when idle, 404 with no data, 400 for bad ids; full **live lifecycle through the API**: start → 409 on double start → pause (time frozen for 1 s) → resume → state/snapshot/decisions → finishes → auto-saved → time series stored → reset; **comparison job** of 3 controllers completes, aggregate and % vs Fixed-Time computed, CSV contains headers, PDF starts with `%PDF`; DB round trip (save/get/series/decisions/delete) |

## 3. End-to-end and UI verification (executed)

| Check | How | Result |
|---|---|---|
| Backend + SUMO + TraCI | `uvicorn` started, `/health` called | `sumo: ok, traci: ok, database: ok` |
| Streamlit ↔ FastAPI | Headless Chrome (Playwright) opened all 7 pages during a live run | 0 exceptions on every page |
| Dashboard controls | Playwright **clicked** Start → Pause → Resume → Reset on the Live page | Status pill changed RUNNING → PAUSED → RUNNING → IDLE |
| Live map | Screenshot during a high-demand run | Vehicles and signal colours visible (`screenshots/live.png`) |
| sumo-gui mode | `gui=True` under a virtual X display | sumo-gui opened, stepped by TraCI, controller switched phases (`screenshots/sumo_gui.png`) |
| PDF report | Downloaded via API, rendered to PNG | 3 pages: table, 9 metric charts, time series |
| Environment check | `scripts/check_environment.py` | all checks passed |

## 4. Experiments executed (27 runs)

`python scripts/run_experiments.py --scenarios low medium high --seeds 1 2 3 --duration 1800`
→ [results/experiment_results.md](results/experiment_results.md). Across all 27 runs:
**0 safety rejections, 0 teleports**. Each run took 7–14 s of real time for 1800 s of simulated time.

## 5. Bugs found during testing and fixed

| Problem found | Fix |
|---|---|
| Starvation was counted from t = 0 for phases that never had traffic, which inflated counts | Starvation now uses *time vehicles have waited on red* (`demand_wait`), not time since the last green |
| Occupancy was ambiguous (TraCI returns a fraction 0–1) | Measured it, then always multiply by 100 |
| Reset could deadlock with the stepping thread (both wanted the lock) | Stop and join the thread before taking the lock; the loop checks the stop flag inside the lock |
| A phase sharing a movement could go green→red in all-red | Amber now covers all green movements before all-red |
| "Traffic condition" said *Free* while queues existed (the average included empty lanes) | Condition now uses each junction's most congested approach |
| Latency rounded to 0.00 in tables and PDF | Shown with 4 decimals |
| Live page did not show the "SUMO connection lost" message until reload (found in Windows test W13) | The live fragment triggers a full page redraw when the status changes |
| Analytics legends overlapped titles; page headers hidden under the toolbar | Legend moved below charts; top padding increased |

## 6. Windows laptop tests

| # | Test | How | Expected | Result |
|---|---|---|---|---|
| W1 | Environment check | `python scripts/check_environment.py` | "All checks passed" | **Passed** (10 Nov 2026) |
| W2 | Backend starts | `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` | "Uvicorn running…" | **Passed** |
| W3 | Dashboard opens | `python -m streamlit run frontend/app.py --server.port 8501` | Dashboard in browser | **Passed** |
| W4 | SUMO ready and connected | Sidebar status | "Backend online", "SUMO ready" | **Passed** |
| W5 | Live simulation, Adaptive (VAC) | Live Simulation → Start | Vehicles move, signals change | **Passed** |
| W6 | Map and dashboard data | Live, Home, Monitoring pages | Live values shown | **Passed** |
| W7 | Automated tests on Windows | `python -m pytest -v` | 51 passed | **Passed**: 51 passed in 20.70 s (1 harmless Starlette deprecation notice, now silenced in `pytest.ini`) |
| W8 | Pause / Resume / Reset | Buttons on Live Simulation | Status pill PAUSED → RUNNING → IDLE, time freezes while paused | **Passed** |
| W9 | Live run finishes and is saved | Duration 120, speed 50, Start, wait | "Run finished and saved as experiment #N" | **Passed** |
| W10 | Fair comparison + reproducibility | Comparison: High, seeds `1`, duration 1800 | Fixed-Time 93.44 s, Adaptive 55.60 s, Max-Pressure 76.87 s avg waiting (Linux values; equal or very close) | **Passed: exact match** (Windows: 93.437 / 55.601 / 76.872 s waiting, 177.879 / 137.197 / 165.45 s travel, throughput +7.26 % for Adaptive. Identical to Linux, so results are reproducible across operating systems) |
| W11 | Reports | Reports → Download CSV, Generate PDF → Download PDF | Both files open | **Passed** |
| W12 | sumo-gui on a real desktop | Tick "Open sumo-gui", Start | SUMO window opens; signals follow the dashboard | **Passed**: sumo-gui opened on the Windows desktop and showed vehicles on the 4-junction network |
| W13 | Error handling: SUMO closed | Close the sumo-gui window during a W12 run | Dashboard shows "SUMO connection lost…"; Reset works | **Passed**: status became ERROR at t = 253 s and Reset returned to IDLE. Found: the red message only appeared after a page reload and Pause stayed clickable. Fixed in `frontend/views/live.py` (the page redraws when the status changes) and re-verified by a browser test |
| W14 | Error handling: backend down | Ctrl+C in the backend terminal, refresh dashboard | Sidebar "Backend offline" with start command; recovers after restart | **Passed** |

**Windows summary:** all 14 checks passed (W1–W14). The fair comparison reproduced the Linux results exactly.

## 7. PostgreSQL compatibility test (executed)

| Step | Result |
|---|---|
| Server | PostgreSQL 16.15, driver psycopg2-binary 2.9.13 |
| Full test suite with `VAC_TEST_DATABASE_URL=postgresql+psycopg2://…/vac_traffic` | **51 / 51 passed** (31.8 s) |
| Tables created automatically | `experiments`, `results`, `timeseries`, `decisions` |
| Real backend with `DATABASE_URL` set to PostgreSQL | `/health` → `database: ok` |
| Comparison job (high, seed 1, 1800 s) stored in PostgreSQL | Completed. Avg waiting Fixed-Time 93.437 s, Adaptive 55.601 s, Max-Pressure 76.872 s, **identical to the SQLite run** |
| CSV and PDF reports read from PostgreSQL | CSV OK, PDF 3 pages |

**Conclusion:** the "SQLite initially, PostgreSQL-compatible" requirement is verified, and no code
change is needed. Using PostgreSQL day to day is optional; SQLite remains the default.

## 8. Necessary vs optional remaining tests

| Item | Necessary? | Why |
|---|---|---|
| W7–W11, W14 | **Completed – all passed on Windows** | Every acceptance criterion you will demonstrate (controls, saving, fair comparison, reports, error handling) is confirmed on the target laptop |
| W12–W13 sumo-gui | **Completed – passed** | sumo-gui works on the Windows desktop, and closing it is handled safely |
| PostgreSQL on the laptop | Optional | Compatibility was verified in section 7 (51/51 tests). Only needed if your evaluator asks for a live PostgreSQL demo |
