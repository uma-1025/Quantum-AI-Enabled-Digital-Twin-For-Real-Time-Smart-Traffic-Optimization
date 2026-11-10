"""Locate SUMO binaries and start TraCI connections with clear error messages."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path


class SumoNotFoundError(RuntimeError):
    pass


def sumo_home() -> Path | None:
    env = os.environ.get("SUMO_HOME")
    if env and Path(env).exists():
        return Path(env)
    try:  # pip install eclipse-sumo
        import sumo  # type: ignore

        os.environ.setdefault("SUMO_HOME", str(sumo.SUMO_HOME))
        return Path(sumo.SUMO_HOME)
    except Exception:
        return None


def sumo_binary(name: str = "sumo") -> str:
    """Return the full path to a SUMO tool (sumo, sumo-gui, netconvert)."""
    exe = name + (".exe" if os.name == "nt" else "")
    home = sumo_home()
    if home is not None:
        cand = home / "bin" / exe
        if cand.exists():
            return str(cand)
    found = shutil.which(name)
    if found:
        return found
    raise SumoNotFoundError(
        f"SUMO tool '{name}' was not found. Install SUMO (pip install eclipse-sumo, "
        "or the official installer) and/or set the SUMO_HOME environment variable."
    )


def sumo_version() -> str:
    try:
        out = subprocess.run([sumo_binary("sumo"), "--version"], capture_output=True,
                             text=True, timeout=20).stdout
        return out.splitlines()[0].strip() if out else "unknown"
    except Exception as exc:  # pragma: no cover - reported via /health
        return f"unavailable ({exc})"


_start_lock = threading.Lock()


def start_traci(sumocfg: Path, label: str, gui: bool = False, seed: int = 42,
                extra_args: list[str] | None = None):
    """Start SUMO and return a TraCI connection object bound to `label`.

    Raises a RuntimeError with a readable message on failure.
    """
    import traci  # imported lazily so tests without SUMO can still import modules

    binary = sumo_binary("sumo-gui" if gui else "sumo")
    cmd = [
        binary, "-c", str(sumocfg),
        "--seed", str(seed),
        "--no-step-log", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "300",
        "--waiting-time-memory", "10000",
        "--collision.action", "warn",
    ]
    if gui:
        cmd += ["--start", "true", "--quit-on-end", "true", "--delay", "100"]
    if extra_args:
        cmd += extra_args
    with _start_lock:
        try:
            traci.start(cmd, label=label)
        except Exception as exc:
            raise RuntimeError(
                f"Could not start SUMO / connect via TraCI ({exc}). "
                f"Command: {' '.join(cmd)}"
            ) from exc
        return traci.getConnection(label)
