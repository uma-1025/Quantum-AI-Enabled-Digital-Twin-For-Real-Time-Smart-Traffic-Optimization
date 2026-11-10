# HOW TO RUN – step by step (read this first)

This file tells you **exactly what to install, which command to type, and in which window
and folder to type it**. Follow it top to bottom the first time.

---

## Part A – What you must have installed BEFORE you start

| # | Software | Why | How to check it is installed |
|---|----------|-----|------------------------------|
| 1 | **Python 3.10 or newer** (3.11 / 3.12 / 3.13 recommended) | runs the whole project | open a terminal and type `python --version` (Windows) or `python3 --version` (macOS/Linux) |
| 2 | **pip** (comes with Python) | installs the Python libraries | `python -m pip --version` |
| 3 | **Internet connection** (only for the install step) | downloads SUMO and libraries | – |
| 4 | **A web browser** (Chrome / Edge / Firefox) | shows the dashboard | – |

**You do NOT need to install SUMO separately.** `pip install -r requirements.txt` installs
`eclipse-sumo`, which contains SUMO, sumo-gui and netconvert. (If you already installed SUMO
with the official installer, that also works – the project finds it through `SUMO_HOME`.)

**Windows only – installing Python:** download it from https://www.python.org/downloads/ and
on the first installer screen **tick "Add python.exe to PATH"**. Then close and reopen any terminal.

> What is a "terminal"?
> * Windows: press the Start button, type **cmd**, press Enter ("Command Prompt").
>   (PowerShell also works; differences are noted below.)
> * macOS: open **Terminal** (Applications → Utilities).
> * Linux: open your **Terminal** app.

---

## Part B – One-time setup (do this only once)

All commands in Part B are typed in **one terminal window**.

### Step B1 – Unzip the project
Unzip `vac_traffic_epic1.zip`, for example to:
* Windows: `C:\Projects\vac_traffic_epic1`
* macOS/Linux: `~/Projects/vac_traffic_epic1`

Inside it you must see the folders `backend`, `frontend`, `docs`, `tests` and the file
`requirements.txt`. **This folder is called the "project folder" below.**

### Step B2 – Go into the project folder
Windows (Command Prompt):
```bat
cd C:\Projects\vac_traffic_epic1
```
macOS / Linux:
```bash
cd ~/Projects/vac_traffic_epic1
```

### Step B3 – Create a virtual environment (a private Python just for this project)
Windows:
```bat
python -m venv .venv
```
macOS / Linux:
```bash
python3 -m venv .venv
```

### Step B4 – Activate the virtual environment
Windows (Command Prompt):
```bat
.venv\Scripts\activate
```
Windows (PowerShell):
```powershell
.venv\Scripts\Activate.ps1
```
macOS / Linux:
```bash
source .venv/bin/activate
```
You should now see `(.venv)` at the start of the line. **Every time you open a new terminal for
this project you must do Step B2 + Step B4 again.**

### Step B5 – Install all libraries (takes a few minutes, needs internet)
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Step B6 – Check that everything works
```bash
python scripts/check_environment.py
```
Expected ending: `All checks passed - you can start the backend and dashboard.`
This also runs a 2-minute (simulated) SUMO test in about 1 second.

---

## Part C – Running the application (every time)

You need **TWO terminal windows open at the same time**. Both must be in the project folder
with the virtual environment activated (Steps B2 + B4).

### Terminal 1 – start the BACKEND (FastAPI + SUMO + TraCI)
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Wait until you see: `Uvicorn running on http://127.0.0.1:8000`.
**Leave this window open.** (Shortcut: double-click / run `run_backend.bat` on Windows or
`./run_backend.sh` on macOS/Linux from the activated terminal.)

Optional check: open http://127.0.0.1:8000/health in the browser – you should see `"sumo":"ok"`.
Interactive API documentation: http://127.0.0.1:8000/docs

### Terminal 2 – start the DASHBOARD (Streamlit)
```bash
python -m streamlit run frontend/app.py --server.port 8501
```
The browser opens automatically. If not, open **http://localhost:8501** yourself.
**Leave this window open too.** (Shortcut: `run_frontend.bat` / `./run_frontend.sh`.)

### Use it
1. Sidebar must show **Backend online** and **SUMO ready** (green).
2. Go to **Live Simulation** → choose scenario + controller → press **Start**.
   Vehicles move on the map, signal squares change colour. Try **Pause**, **Resume**, **Reset**.
   Tick **Open sumo-gui** before Start if you also want SUMO's own window.
3. Open **Traffic Monitoring** and **Adaptive Control** while it runs.
4. Go to **Controller Comparison** → **Run comparison** (default: 3 seeds × 3 controllers × 1800 s
   ≈ 1.5–3 minutes). Results and charts appear when finished.
5. **Analytics** shows time-series graphs; **Reports** exports CSV and PDF.

### Stopping
Press **Ctrl + C** in each terminal window.

---

## Part D – Other useful commands (Terminal 1 or a third terminal, venv activated)

| What | Command |
|------|---------|
| Run all automated tests (≈ 25 s) | `python -m pytest -v` |
| Run the full experiment set used in the docs (≈ 5 min) | `python scripts/run_experiments.py --scenarios low medium high --seeds 1 2 3 --duration 1800` |
| Rebuild the road network | `python -m backend.sumo_config.build_network` |
| Preview generated traffic demand | `python -m backend.sumo_config.generate_routes` |
| Open the network in SUMO's GUI without the app | `python -c "from backend.simulation.sumo_utils import sumo_binary; import subprocess; subprocess.run([sumo_binary('sumo-gui'), '-n', 'backend/sumo_config/network/grid4.net.xml'])"` |
| Use PostgreSQL instead of SQLite | `pip install psycopg2-binary` then set `DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/vac_traffic` before starting the backend (Windows: `set DATABASE_URL=...`, macOS/Linux: `export DATABASE_URL=...`) |
| Start fresh (delete all stored results) | stop the backend, delete `data/vac_traffic.db`, start the backend again |

---

## Part E – Fixing common errors

| Message / symptom | Cause | Fix |
|---|---|---|
| `'python' is not recognized` (Windows) | Python not on PATH | Reinstall Python with **"Add python.exe to PATH"** ticked, or use `py` instead of `python` |
| `running scripts is disabled on this system` (PowerShell) | PowerShell blocks Activate.ps1 | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use Command Prompt (`cmd`) |
| `ModuleNotFoundError: No module named 'backend'` | Command not run from the project folder | `cd` into the project folder (the one containing `backend`) and run again |
| `ModuleNotFoundError: fastapi / streamlit / traci ...` | venv not activated or install skipped | Do Step B4, then Step B5 |
| `SUMO tool 'sumo' was not found` | eclipse-sumo not installed | `python -m pip install eclipse-sumo`, or install SUMO and set `SUMO_HOME` to its folder |
| Sidebar says **Backend offline** | Terminal 1 not running / crashed | Start Terminal 1 again and read its error |
| `[Errno 10048]` / `address already in use` | Port 8000 or 8501 busy (an old copy is running) | Close the old terminal, or use another port: `--port 8001` and start the dashboard with `set VAC_API_URL=http://127.0.0.1:8001` (Windows) / `export VAC_API_URL=...` |
| "A simulation is already running. Reset it first." | Live run still active | Press **Reset** on the Live Simulation page |
| "SUMO connection lost" | sumo-gui window was closed during a run | Press **Reset**, then **Start** again |
| sumo-gui does not open | No display (e.g. remote server) | Leave **Open sumo-gui** unticked – the dashboard map works without it |
| Comparison is slow | Long duration / many seeds | Use fewer seeds or a shorter duration (e.g. 600 s) while testing |
| macOS: sumo-gui fails with XQuartz error | sumo-gui on macOS needs XQuartz | Install XQuartz (https://www.xquartz.org) or leave sumo-gui unticked |

If an error is not listed: copy the **full text from Terminal 1** and the message shown in the
dashboard – they say exactly which step failed.
