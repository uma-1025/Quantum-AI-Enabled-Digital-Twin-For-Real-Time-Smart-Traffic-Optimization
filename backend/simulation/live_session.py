"""Live (interactive) simulation running in a background thread.

Supports start, pause, resume and reset. The dashboard polls the latest state.
When the run reaches its duration, results are stored in the database.
"""
from __future__ import annotations

import threading
import time
import traceback

from backend.database import db
from backend.simulation.engine import FatalTraCIError, SimulationRunner
from backend.simulation.sumo_utils import sumo_version

IDLE, RUNNING, PAUSED, FINISHED, ERROR = "idle", "running", "paused", "finished", "error"


class LiveSession:
    def __init__(self):
        self.lock = threading.RLock()
        self.runner: SimulationRunner | None = None
        self.status = IDLE
        self.error: str | None = None
        self.experiment_id: int | None = None
        self.config: dict = {}
        self._pause = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.speed = 10.0

    # ------------------------------------------------------------------
    def start(self, scenario: str, controller: str, seed: int, duration: int,
              speed: float = 10.0, gui: bool = False, params: dict | None = None) -> dict:
        if self.status in (RUNNING, PAUSED):
            raise RuntimeError("A simulation is already running. Reset it first.")
        self._shutdown()
        with self.lock:
            runner = SimulationRunner(scenario, controller, seed, duration, gui=gui,
                                      controller_params=params, label=f"live_{int(time.time())}")
            runner.start()  # raises a readable error if SUMO cannot start
            self.runner = runner
            self.config = {"scenario": scenario, "controller": controller, "seed": seed,
                           "duration": duration, "speed": speed, "gui": gui,
                           "params": runner.controller.params}
            self.speed = speed
            self.error = None
            self.experiment_id = None
            self._pause.clear()
            self._stop.clear()
            self.status = RUNNING
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            return self.status_dict()

    def _loop(self):
        runner = self.runner
        try:
            while not self._stop.is_set() and not runner.finished:
                if self._pause.is_set():
                    time.sleep(0.05)
                    continue
                t0 = time.perf_counter()
                with self.lock:
                    if self._stop.is_set():
                        break
                    runner.step()
                if self.speed > 0:
                    delay = 1.0 / self.speed - (time.perf_counter() - t0)
                    if delay > 0:
                        time.sleep(delay)
            if runner.finished and not self._stop.is_set():
                runner.close()
                self.experiment_id = db.save_experiment(
                    {"mode": "live", "scenario": self.config["scenario"],
                     "controller": self.config["controller"], "seed": self.config["seed"],
                     "duration": self.config["duration"], "params": self.config["params"],
                     "sumo_version": sumo_version()},
                    runner.summary(), runner.metrics.timeseries, runner.stored_decisions)
                self.status = FINISHED
        except FatalTraCIError as exc:
            if self._stop.is_set():
                return
            self.status = ERROR
            self.error = (f"SUMO connection lost ({exc}). The SUMO process ended unexpectedly "
                          "(e.g. the sumo-gui window was closed). Press Reset and start again.")
        except Exception as exc:
            if self._stop.is_set():
                return
            self.status = ERROR
            self.error = f"{exc}\n{traceback.format_exc(limit=4)}"
        finally:
            if runner is not None and self.status != FINISHED:
                runner.close()

    def pause(self):
        if self.status != RUNNING:
            raise RuntimeError(f"Cannot pause: simulation is {self.status}")
        self._pause.set()
        self.status = PAUSED
        return self.status_dict()

    def resume(self):
        if self.status != PAUSED:
            raise RuntimeError(f"Cannot resume: simulation is {self.status}")
        self._pause.clear()
        self.status = RUNNING
        return self.status_dict()

    def set_speed(self, speed: float):
        self.speed = max(0.0, float(speed))
        self.config["speed"] = self.speed
        return self.status_dict()

    def _shutdown(self):
        """Stop the stepping thread (must be called WITHOUT holding self.lock)."""
        self._stop.set()
        self._pause.clear()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=15)
        if self.runner is not None:
            self.runner.close()

    def reset(self):
        self._shutdown()
        with self.lock:
            self.runner = None
            self.status = IDLE
            self.error = None
            self.config = {}
            self.experiment_id = None
            return self.status_dict()

    # ------------------------------------------------------------------
    def status_dict(self) -> dict:
        r = self.runner
        return {
            "status": self.status,
            "error": self.error,
            "config": self.config,
            "sim_time": r.now if r else 0.0,
            "duration": r.duration if r else 0,
            "progress": round(r.now / r.duration, 4) if r and r.duration else 0.0,
            "experiment_id": self.experiment_id,
            "loaded_vehicles": r.loaded_vehicles if r else 0,
        }

    def require_runner(self) -> SimulationRunner:
        if self.runner is None or self.runner.latest_state is None:
            raise LookupError("No simulation data yet. Start a simulation first.")
        return self.runner
