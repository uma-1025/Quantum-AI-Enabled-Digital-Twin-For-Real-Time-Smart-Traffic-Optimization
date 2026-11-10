"""Generate reproducible traffic demand (routes) for a scenario and random seed.

Vehicles enter at the 8 boundary roads following a Poisson arrival process and
travel to a random boundary exit (never back where they came from). SUMO
computes the shortest route for each trip at insertion time.

The same (scenario, seed, duration) ALWAYS produces the identical file, which
is what makes controller comparisons fair.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.config import NET_FILE, RUNS_DIR, SCENARIOS, STEP_LENGTH_S, VEHICLE_MIX

FRINGE = ["N1", "N2", "S1", "S2", "W1", "W2", "E1", "E2"]
ATTACH = {"N1": "C1", "N2": "C2", "W1": "C1", "E1": "C2",
          "W2": "C3", "E2": "C4", "S1": "C3", "S2": "C4"}

VTYPES = """    <vTypeDistribution id="mixed">
        <vType id="car" vClass="passenger" length="4.5" maxSpeed="13.89" accel="2.6" decel="4.5" sigma="0.5" color="0.35,0.75,1" probability="{car}"/>
        <vType id="truck" vClass="truck" length="10.0" maxSpeed="11.0" accel="1.3" decel="4.0" sigma="0.5" color="1,0.7,0.2" probability="{truck}"/>
        <vType id="bus" vClass="bus" length="12.0" maxSpeed="11.0" accel="1.2" decel="4.0" sigma="0.5" color="0.8,0.4,1" probability="{bus}"/>
    </vTypeDistribution>"""


def entry_edge(f: str) -> str:
    return f"{f}_{ATTACH[f]}"


def exit_edge(f: str) -> str:
    return f"{ATTACH[f]}_{f}"


def generate_trips(scenario: str, seed: int, duration: int,
                   density_multiplier: float = 1.0) -> list[tuple[float, str, str]]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Choose from {list(SCENARIOS)}")
    rate_vph = SCENARIOS[scenario]["veh_per_hour_per_entry"] * density_multiplier
    rng = np.random.default_rng(seed)
    trips: list[tuple[float, str, str]] = []
    mean_headway = 3600.0 / rate_vph
    for origin in FRINGE:
        t = float(rng.exponential(mean_headway))
        destinations = [d for d in FRINGE if d != origin]
        while t < duration:
            dest = destinations[int(rng.integers(len(destinations)))]
            trips.append((round(t, 1), entry_edge(origin), exit_edge(dest)))
            t += float(rng.exponential(mean_headway))
    trips.sort(key=lambda x: x[0])
    return trips


def write_run_files(scenario: str, seed: int, duration: int, run_name: str,
                    density_multiplier: float = 1.0) -> tuple[Path, int]:
    """Write <run>.rou.xml and <run>.sumocfg. Returns (sumocfg path, vehicle count)."""
    run_dir = RUNS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    trips = generate_trips(scenario, seed, duration, density_multiplier)
    lines = ["<routes>", VTYPES.format(**VEHICLE_MIX)]
    for i, (dep, frm, to) in enumerate(trips):
        lines.append(
            f'    <trip id="veh{i}" type="mixed" depart="{dep}" from="{frm}" to="{to}" '
            f'departLane="best" departSpeed="max"/>'
        )
    lines.append("</routes>")
    rou = run_dir / "demand.rou.xml"
    rou.write_text("\n".join(lines) + "\n")

    cfg = run_dir / "run.sumocfg"
    cfg.write_text(f"""<configuration>
    <input>
        <net-file value="{NET_FILE.as_posix()}"/>
        <route-files value="{rou.as_posix()}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{duration}"/>
        <step-length value="{STEP_LENGTH_S}"/>
    </time>
</configuration>
""")
    return cfg, len(trips)


if __name__ == "__main__":
    for sc in SCENARIOS:
        cfg, n = write_run_files(sc, 42, 1800, f"preview_{sc}")
        print(f"{sc}: {n} vehicles -> {cfg}")
