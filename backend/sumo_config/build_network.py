"""Build the SUMO road network: a 2 x 2 grid of four signalized intersections.

Layout (metres)::

            N1            N2
            |             |
    W1 ---- C1 ---------- C2 ---- E1
            |             |
            |             |
    W2 ---- C3 ---------- C4 ---- E2
            |             |
            S1            S2

* C1..C4 are traffic-light junctions.
* Every road is two-way with 3 lanes per direction:
  lane 0 = right turn + straight, lane 1 = straight, lane 2 = dedicated left turn.
* Lane connections are written explicitly so each lane's movements are known
  and no U-turns exist.

Run:  python -m backend.sumo_config.build_network
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from backend.config import NETWORK_DIR, NET_FILE
from backend.simulation.sumo_utils import sumo_binary

SPEED_MS = 13.89  # 50 km/h
LANES = 3

NODES = {
    "C1": (0.0, 300.0), "C2": (300.0, 300.0), "C3": (0.0, 0.0), "C4": (300.0, 0.0),
    "N1": (0.0, 550.0), "N2": (300.0, 550.0), "S1": (0.0, -250.0), "S2": (300.0, -250.0),
    "W1": (-250.0, 300.0), "W2": (-250.0, 0.0), "E1": (550.0, 300.0), "E2": (550.0, 0.0),
}
TLS_NODES = ["C1", "C2", "C3", "C4"]
ROADS = [  # undirected; each becomes two directed edges
    ("N1", "C1"), ("N2", "C2"), ("W1", "C1"), ("W2", "C3"),
    ("E1", "C2"), ("E2", "C4"), ("S1", "C3"), ("S2", "C4"),
    ("C1", "C2"), ("C3", "C4"), ("C1", "C3"), ("C2", "C4"),
]


def directed_edges():
    for a, b in ROADS:
        yield a, b
        yield b, a


def edge_id(a: str, b: str) -> str:
    return f"{a}_{b}"


def turn_type(frm: str, via: str, to: str) -> str:
    """Return 'r', 's' or 'l' for the movement frm -> via -> to (right-hand traffic)."""
    (x0, y0), (x1, y1), (x2, y2) = NODES[frm], NODES[via], NODES[to]
    v1 = (x1 - x0, y1 - y0)
    v2 = (x2 - x1, y2 - y1)
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    angle = math.degrees(math.atan2(cross, dot))
    if abs(angle) < 30:
        return "s"
    return "l" if angle > 0 else "r"


def write_inputs(out_dir: Path) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    nod = out_dir / "grid4.nod.xml"
    edg = out_dir / "grid4.edg.xml"
    con = out_dir / "grid4.con.xml"

    lines = ['<nodes>']
    for nid, (x, y) in NODES.items():
        ntype = "traffic_light" if nid in TLS_NODES else "priority"
        lines.append(f'  <node id="{nid}" x="{x}" y="{y}" type="{ntype}"/>')
    lines.append('</nodes>')
    nod.write_text("\n".join(lines) + "\n")

    lines = ['<edges>']
    for a, b in directed_edges():
        lines.append(
            f'  <edge id="{edge_id(a, b)}" from="{a}" to="{b}" numLanes="{LANES}" '
            f'speed="{SPEED_MS}" priority="2"/>'
        )
    lines.append('</edges>')
    edg.write_text("\n".join(lines) + "\n")

    lines = ['<connections>']
    for junction in TLS_NODES:
        incoming = [a for a, b in directed_edges() if b == junction]
        outgoing = [b for a, b in directed_edges() if a == junction]
        for frm in incoming:
            for to in outgoing:
                if to == frm:
                    continue  # no U-turns
                t = turn_type(frm, junction, to)
                e_in, e_out = edge_id(frm, junction), edge_id(junction, to)
                if t == "r":
                    pairs = [(0, 0)]
                elif t == "s":
                    pairs = [(0, 0), (1, 1)]
                else:
                    pairs = [(2, 2)]
                for fl, tl in pairs:
                    lines.append(
                        f'  <connection from="{e_in}" to="{e_out}" fromLane="{fl}" toLane="{tl}"/>'
                    )
    lines.append('</connections>')
    con.write_text("\n".join(lines) + "\n")
    return nod, edg, con


def build(out_dir: Path = NETWORK_DIR, net_file: Path = NET_FILE) -> Path:
    nod, edg, con = write_inputs(out_dir)
    cmd = [
        sumo_binary("netconvert"),
        "--node-files", str(nod),
        "--edge-files", str(edg),
        "--connection-files", str(con),
        "--output-file", str(net_file),
        "--no-turnarounds", "true",
        "--tls.default-type", "static",
        "--junctions.corner-detail", "5",
        "--no-warnings", "true",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"netconvert failed:\n{res.stdout}\n{res.stderr}")
    return net_file


if __name__ == "__main__":
    path = build()
    print(f"Network written to {path}")
