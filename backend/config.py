"""Central configuration for the VAC-Inspired Adaptive Traffic Control System (Epic 1).

Every tunable number lives here so that the algorithms stay explainable and
configurable. Values can be overridden per run through the API.
"""
from __future__ import annotations

import os
from pathlib import Path

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
SUMO_CONFIG_DIR = BACKEND_DIR / "sumo_config"
NETWORK_DIR = SUMO_CONFIG_DIR / "network"
NET_FILE = NETWORK_DIR / "grid4.net.xml"
DATA_DIR = ROOT_DIR / "data"
RUNS_DIR = DATA_DIR / "runs"          # generated route files / sumocfg per run

DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# SQLite by default; any SQLAlchemy URL works (e.g. PostgreSQL):
#   DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/vac_traffic
DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'vac_traffic.db').as_posix()}"
)

# ----------------------------------------------------------------------------
# API
# ----------------------------------------------------------------------------
API_HOST = os.environ.get("VAC_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("VAC_API_PORT", "8000"))
API_BASE_URL = os.environ.get("VAC_API_URL", f"http://{API_HOST}:{API_PORT}")

# ----------------------------------------------------------------------------
# Traffic demand scenarios (vehicles per hour entering at EACH of the 8 entries)
# ----------------------------------------------------------------------------
SCENARIOS = {
    "low": {"label": "Low demand", "veh_per_hour_per_entry": 150},
    "medium": {"label": "Medium demand", "veh_per_hour_per_entry": 300},
    "high": {"label": "High demand", "veh_per_hour_per_entry": 450},
}
DEFAULT_SCENARIO = "medium"
DEFAULT_DURATION_S = 1800
DEFAULT_SEED = 42
STEP_LENGTH_S = 1.0

# Vehicle mix (probabilities must sum to 1)
VEHICLE_MIX = {"car": 0.85, "truck": 0.10, "bus": 0.05}

# ----------------------------------------------------------------------------
# Signal safety (applied to ALL controllers by the safety layer)
# ----------------------------------------------------------------------------
YELLOW_TIME_S = 3.0      # amber
ALL_RED_TIME_S = 2.0     # all-red clearance
SAFETY_MIN_GREEN_S = 5.0  # absolute minimum green the safety layer will ever allow

# ----------------------------------------------------------------------------
# Controller defaults
# ----------------------------------------------------------------------------
FIXED_TIME_DEFAULTS = {
    # green seconds for the 4 phases: NS_THROUGH, NS_LEFT, EW_THROUGH, EW_LEFT
    "green_times": [30.0, 12.0, 30.0, 12.0],
}

ADAPTIVE_DEFAULTS = {
    "min_green": 8.0,          # never terminate a green before this
    "max_green": 50.0,         # always terminate a green after this (if others wait)
    "passage_time": 3.0,       # gap-out: end green when no vehicle detected for this long
    "detection_distance": 40.0,  # metres before the stop line treated as the detector zone
    "max_red": 90.0,           # starvation guard: a waiting phase is forced after this red time
}

MAX_PRESSURE_DEFAULTS = {
    "min_green": 8.0,
    "max_green": 50.0,
    "switch_threshold": 1.0,   # hysteresis: switch only if pressure gain exceeds this
}

# ----------------------------------------------------------------------------
# Congestion analysis (weights must sum to 1; score is 0-100)
# ----------------------------------------------------------------------------
CONGESTION_WEIGHTS = {
    "queue": 0.40,       # queue / lane storage capacity
    "occupancy": 0.20,   # lane occupancy %
    "waiting": 0.25,     # mean waiting time / WAITING_NORM_S
    "arrival": 0.15,     # arrival rate / ARRIVAL_NORM_VPM
}
WAITING_NORM_S = 60.0         # waiting time that counts as "fully congested"
ARRIVAL_NORM_VPM = 12.0       # arrivals per minute per lane that count as "fully loaded"
VEHICLE_SPACE_M = 7.5         # vehicle length + gap used for lane storage capacity
CONGESTION_LEVELS = [(25, "Free"), (50, "Moderate"), (75, "Heavy"), (101, "Severe")]

# ----------------------------------------------------------------------------
# Evaluation
# ----------------------------------------------------------------------------
STARVATION_THRESHOLD_S = 120.0   # a phase with demand unserved longer than this = 1 event
TIMESERIES_INTERVAL_S = 10       # sample interval for stored time series
ARRIVAL_WINDOW_S = 60.0          # sliding window for arrival-rate estimation
