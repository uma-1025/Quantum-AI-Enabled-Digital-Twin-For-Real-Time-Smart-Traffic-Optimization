"""Check that everything needed to run the project is installed and working.

Run from the project root:   python scripts/check_environment.py
"""
from __future__ import annotations

import importlib
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OK, BAD = "[ OK ]", "[FAIL]"
problems = 0


def check(name, fn):
    global problems
    try:
        msg = fn()
        print(f"{OK} {name}" + (f" - {msg}" if msg else ""))
    except Exception as exc:
        problems += 1
        print(f"{BAD} {name} - {exc}")


def py():
    v = sys.version_info
    if v < (3, 10):
        raise RuntimeError(f"Python {v.major}.{v.minor} found; 3.10 or newer is required")
    return f"Python {v.major}.{v.minor}.{v.micro}"


def pkgs():
    missing = []
    for m in ["traci", "sumolib", "fastapi", "uvicorn", "pydantic", "streamlit", "plotly", "pandas",
              "numpy", "sqlalchemy", "matplotlib", "requests"]:
        try:
            importlib.import_module(m)
        except Exception:
            missing.append(m)
    if missing:
        raise RuntimeError(f"missing packages: {missing}. Run: pip install -r requirements.txt")
    return "all Python packages import"


def sumo():
    from backend.simulation.sumo_utils import sumo_binary, sumo_version
    return f"{sumo_version()} at {sumo_binary('sumo')}"


def network():
    from backend.config import NET_FILE
    if not NET_FILE.exists():
        from backend.sumo_config.build_network import build
        build()
        return "network was missing - rebuilt with netconvert"
    return f"{NET_FILE.name} present"


def smoke():
    from backend.simulation.engine import SimulationRunner
    r = SimulationRunner("low", "adaptive", 1, 120, label="envcheck")
    s = r.run_to_end()
    return f"120 s headless run OK (departed {s['vehicles_departed']}, phase changes {s['phase_changes']})"


def ports():
    busy = []
    for p in (8000, 8501):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) == 0:
                busy.append(p)
    return "ports 8000 and 8501 free" if not busy else f"port(s) {busy} already in use (fine if it is this app)"


if __name__ == "__main__":
    check("Python version", py)
    check("Python packages", pkgs)
    check("SUMO installation", sumo)
    check("Road network", network)
    check("SUMO + TraCI smoke simulation", smoke)
    check("Network ports", ports)
    print("\nAll checks passed - you can start the backend and dashboard." if problems == 0
          else f"\n{problems} check(s) failed - see HOW_TO_RUN.md, section 'Fixing common errors'.")
    sys.exit(1 if problems else 0)
