"""Reusable dashboard components that render ACTUAL backend data."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from frontend import api_client as api
from frontend.theme import CARD_BORDER, SIGNAL_COLOR, TEXT, TEXT2, style_fig


@st.cache_data(ttl=600, show_spinner=False)
def network_geometry() -> dict:
    return api.get("/network")


@st.cache_data(ttl=600, show_spinner=False)
def app_config() -> dict:
    return api.get("/config")


def network_figure(net: dict, snap: dict | None, height: int = 620) -> go.Figure:
    fig = go.Figure()
    xs, ys = [], []
    for lane in net["lanes"]:
        for x, y in lane["shape"]:
            xs.append(x)
            ys.append(y)
        xs.append(None)
        ys.append(None)
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#2a3f66", width=7),
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#152a4c", width=5),
                             hoverinfo="skip", showlegend=False))

    # signal heads: one marker per incoming lane at its stop line
    if snap:
        sx, sy, sc, st_txt = [], [], [], []
        for tid, t in net["tls"].items():
            sig = snap["signals"].get(tid)
            if not sig:
                continue
            lane_chars: dict[str, list[str]] = {}
            stops: dict[str, tuple] = {}
            for link in t["links"]:
                lane_chars.setdefault(link["in_lane"], []).append(sig["state"][link["index"]])
                stops[link["in_lane"]] = link["stop"]
            for lane, chars in lane_chars.items():
                c = "G" if any(ch in "Gg" for ch in chars) else ("y" if "y" in chars else "r")
                sx.append(stops[lane][0])
                sy.append(stops[lane][1])
                sc.append(SIGNAL_COLOR[c])
                st_txt.append(f"{tid} · {lane}<br>{ {'G': 'GREEN', 'y': 'AMBER', 'r': 'RED'}[c] }")
        fig.add_trace(go.Scatter(x=sx, y=sy, mode="markers", name="Signals",
                                 marker=dict(size=9, color=sc, symbol="square", line=dict(color="#0a1628", width=1)),
                                 text=st_txt, hovertemplate="%{text}<extra></extra>", showlegend=False))
        vx = [v["x"] for v in snap["vehicles"]]
        vy = [v["y"] for v in snap["vehicles"]]
        vs = [v["speed"] for v in snap["vehicles"]]
        vt = [f"{v['id']} ({v['type']})<br>speed {v['speed']:.1f} m/s" for v in snap["vehicles"]]
        fig.add_trace(go.Scatter(
            x=vx, y=vy, mode="markers", name="Vehicles", text=vt, hovertemplate="%{text}<extra></extra>",
            marker=dict(size=8, color=vs, cmin=0, cmax=14,
                        colorscale=[[0, "#cfe1fb"], [0.5, "#5b9bf0"], [1, "#1c4f9c"]],
                        line=dict(color="#0a1628", width=1),
                        colorbar=dict(title=dict(text="speed m/s", font=dict(color=TEXT2)), thickness=10,
                                      len=0.5, tickfont=dict(color=TEXT2))),
            showlegend=False))
        for tid, t in net["tls"].items():
            sig = snap["signals"].get(tid, {})
            fig.add_annotation(x=t["x"] + 38, y=t["y"] + 38, text=f"<b>{tid}</b> {sig.get('phase', '')}"
                               f"<br>{sig.get('mode', '')} {sig.get('elapsed_green', 0):.0f}s",
                               showarrow=False, font=dict(color=TEXT, size=10), align="left",
                               bgcolor="rgba(16,33,63,0.85)", bordercolor=CARD_BORDER, xanchor="left")
    xmin, ymin, xmax, ymax = net["boundary"]
    fig.update_xaxes(visible=False, range=[xmin - 20, xmax + 20])
    fig.update_yaxes(visible=False, range=[ymin - 20, ymax + 20], scaleanchor="x", scaleratio=1)
    style_fig(fig, height=height)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    return fig


def need_live_data(path: str):
    """Fetch live data; show a friendly message and return None if unavailable."""
    data, err = api.try_get(path)
    if data is None:
        if err and "No simulation data" in err:
            st.info("No live simulation data yet. Open **Live Simulation** and press **Start**.",
                    icon=":material/info:")
        else:
            st.error(err, icon=":material/error:")
    return data
