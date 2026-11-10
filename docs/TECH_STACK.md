# Technology Stack

Every technology below has a concrete job in the code. Versions are the ones the project was
tested with (Python 3.13.18, 10 Nov 2026).

| Layer | Technology | Version tested | Where it is used | Why it is needed |
|---|---|---|---|---|
| Language | **Python** | 3.13 (3.10+ supported) | everything | One language for simulation control, API, UI and tests |
| Simulation | **SUMO** (`eclipse-sumo` pip package) | 1.28.0 | `sumo` / `sumo-gui` processes | Microscopic simulation of every vehicle and signal |
| Simulation | **netconvert** (in SUMO) | 1.28.0 | `build_network.py` | Builds `grid4.net.xml` from our node, edge and connection files |
| Simulation interface | **TraCI** | 1.28.0 | `sumo_utils.py`, `collector.py`, `engine.py`, `safety.py` | Step the simulation, read lane and vehicle data, set signal states |
| Simulation interface | **sumolib** | 1.28.0 | `network_model.py` | Read lanes, shapes, lengths and TLS links from the network file |
| Backend API | **FastAPI** | 0.162.2 | `backend/main.py` | REST endpoints; the only component that talks to SUMO |
| Backend API | **Uvicorn** | 0.54.0 | run command | ASGI server for FastAPI |
| Backend API | **Pydantic** | 2.13.5 | request models in `main.py` | Validates scenario, controller, duration, seeds and speed (HTTP 422 on bad input) |
| Frontend | **Streamlit** | 1.67.0 | `frontend/` | Multi-page dashboard, auto-refreshing fragments, forms, downloads |
| Frontend | **Requests** | 2.34.2 | `frontend/api_client.py` | Dashboard → API calls |
| Visualization | **Plotly** | 7.1.0 | all dashboard charts + live map | Interactive charts with hover, zoom and legends |
| Data | **Pandas** | 3.0.5 | dashboard tables, report frames, CSV export | Tabular processing |
| Data | **NumPy** | 2.5.3 | demand generator (seeded RNG), metrics (mean, std, percentiles) | Reproducible randomness, statistics |
| Database | **SQLAlchemy Core** | 2.1.8 | `backend/database/db.py` | Portable SQL: SQLite now, PostgreSQL by changing `DATABASE_URL` |
| Database | **SQLite** | built into Python | `data/vac_traffic.db` | Zero-setup experiment storage |
| Reports | **Matplotlib** | 3.11.2 | `report_generator.py` | Tables and charts inside the PDF report (PdfPages) |
| Testing | **pytest** | 9.1.1 | `tests/` | 51 automated tests |
| Testing | **httpx** | 0.28.1 | FastAPI `TestClient` | API tests without starting a server |

## Deliberately NOT used

| Technology | Reason |
|---|---|
| Scikit-learn / PyTorch | No prediction model is needed in Epic 1. Controllers are reactive and explainable. |
| PyQUBO / Qiskit | Quantum optimisation belongs to Epic 2. |
| Docker, Redis, Celery | Not required to meet the requirements. Background threads are enough for one user. |
| ReportLab | Matplotlib already produces the PDF, so one library is enough. |
| psycopg2 | Only needed if you switch to PostgreSQL. It is listed as an optional comment in `requirements.txt`. |

## How the pieces connect

```
Browser ⇄ Streamlit (Requests) ⇄ FastAPI/Uvicorn ⇄ engine ⇄ TraCI (TCP) ⇄ SUMO
                                        │
                                  SQLAlchemy ⇄ SQLite/PostgreSQL
                                        │
                              Pandas + Matplotlib → CSV / PDF
```
