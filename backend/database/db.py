"""Experiment storage with SQLAlchemy Core.

SQLite by default. Because only portable SQLAlchemy types are used, the same
code runs on PostgreSQL by setting DATABASE_URL, e.g.
    DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/vac_traffic
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer, MetaData,
                        String, Table, Text, create_engine, delete, insert, select)

from backend.config import DATABASE_URL

metadata = MetaData()

experiments = Table(
    "experiments", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("group_id", String(64), index=True),
    Column("mode", String(16), nullable=False),          # live | batch
    Column("scenario", String(32), nullable=False),
    Column("controller", String(32), nullable=False),
    Column("seed", Integer, nullable=False),
    Column("duration", Integer, nullable=False),
    Column("status", String(16), nullable=False),        # completed | stopped | failed
    Column("params", Text),                               # JSON
    Column("sumo_version", String(64)),
)

results = Table(
    "results", metadata,
    Column("experiment_id", Integer, ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True),
    Column("vehicles_departed", Integer),
    Column("throughput", Integer),
    Column("throughput_per_hour", Float),
    Column("vehicles_remaining", Integer),
    Column("avg_waiting_time", Float),
    Column("avg_waiting_time_all", Float),
    Column("avg_travel_time", Float),
    Column("stops_per_vehicle", Float),
    Column("mean_queue_length", Float),
    Column("mean_total_queue", Float),
    Column("max_queue_length", Integer),
    Column("max_total_queue", Integer),
    Column("avg_speed", Float),
    Column("phase_changes", Integer),
    Column("latency_mean_ms", Float),
    Column("latency_p95_ms", Float),
    Column("latency_max_ms", Float),
    Column("starvation_events", Integer),
    Column("teleports", Integer),
    Column("safety_rejections", Integer),
    Column("sim_time", Float),
    Column("wall_time_s", Float),
)

timeseries = Table(
    "timeseries", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("experiment_id", Integer, ForeignKey("experiments.id", ondelete="CASCADE"), index=True),
    Column("sim_time", Float),
    Column("vehicles", Integer),
    Column("total_queue", Integer),
    Column("avg_waiting", Float),
    Column("avg_speed", Float),
    Column("throughput", Integer),
    Column("throughput_rate", Float),
    Column("congestion_index", Float),
    Column("phase_changes", Integer),
    Column("latency_ms", Float),
)

decisions = Table(
    "decisions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("experiment_id", Integer, ForeignKey("experiments.id", ondelete="CASCADE"), index=True),
    Column("sim_time", Float),
    Column("tls_id", String(16)),
    Column("action", String(16)),
    Column("category", String(24)),
    Column("from_phase", String(24)),
    Column("to_phase", String(24)),
    Column("reason", Text),
    Column("accepted", Boolean),
)

RESULT_FIELDS = [c.name for c in results.columns if c.name != "experiment_id"]
TS_FIELDS = [c.name for c in timeseries.columns if c.name not in ("id", "experiment_id")]

_engine = None


def get_engine(url: str | None = None):
    global _engine
    if url is not None:
        eng = create_engine(url, future=True)
        metadata.create_all(eng)
        return eng
    if _engine is None:
        kwargs = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
        _engine = create_engine(DATABASE_URL, future=True, **kwargs)
        metadata.create_all(_engine)
    return _engine


def save_experiment(meta: dict, summary: dict, ts: list[dict], decs: list[dict], engine=None) -> int:
    eng = engine or get_engine()
    with eng.begin() as c:
        res = c.execute(insert(experiments).values(
            created_at=datetime.now(timezone.utc), group_id=meta.get("group_id"),
            mode=meta["mode"], scenario=meta["scenario"], controller=meta["controller"],
            seed=int(meta["seed"]), duration=int(meta["duration"]), status=meta.get("status", "completed"),
            params=json.dumps(meta.get("params") or {}), sumo_version=meta.get("sumo_version"),
        ))
        exp_id = int(res.inserted_primary_key[0])
        c.execute(insert(results).values(experiment_id=exp_id,
                                         **{k: summary.get(k) for k in RESULT_FIELDS}))
        if ts:
            c.execute(insert(timeseries), [{"experiment_id": exp_id, **{k: row.get(k) for k in TS_FIELDS}}
                                           for row in ts])
        if decs:
            c.execute(insert(decisions), [{
                "experiment_id": exp_id, "sim_time": d["sim_time"], "tls_id": d["tls_id"],
                "action": d["action"], "category": d["category"], "from_phase": d["from_phase"],
                "to_phase": d["to_phase"], "reason": d["reason"], "accepted": bool(d["accepted"]),
            } for d in decs])
    return exp_id


def _row(r) -> dict:
    d = dict(r._mapping)
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    if "params" in d and isinstance(d["params"], str):
        try:
            d["params"] = json.loads(d["params"])
        except ValueError:
            pass
    return d


def list_experiments(limit: int = 500, group_id: str | None = None, engine=None) -> list[dict]:
    eng = engine or get_engine()
    q = (select(experiments, *[results.c[k] for k in RESULT_FIELDS])
         .select_from(experiments.outerjoin(results, results.c.experiment_id == experiments.c.id))
         .order_by(experiments.c.id.desc()).limit(limit))
    if group_id:
        q = q.where(experiments.c.group_id == group_id)
    with eng.connect() as c:
        return [_row(r) for r in c.execute(q)]


def get_experiment(exp_id: int, engine=None) -> dict | None:
    eng = engine or get_engine()
    q = (select(experiments, *[results.c[k] for k in RESULT_FIELDS])
         .select_from(experiments.outerjoin(results, results.c.experiment_id == experiments.c.id))
         .where(experiments.c.id == exp_id))
    with eng.connect() as c:
        r = c.execute(q).first()
        return _row(r) if r else None


def get_timeseries(exp_id: int, engine=None) -> list[dict]:
    eng = engine or get_engine()
    with eng.connect() as c:
        rows = c.execute(select(timeseries).where(timeseries.c.experiment_id == exp_id)
                         .order_by(timeseries.c.sim_time))
        return [_row(r) for r in rows]


def get_decisions(exp_id: int, limit: int = 1000, engine=None) -> list[dict]:
    eng = engine or get_engine()
    with eng.connect() as c:
        rows = c.execute(select(decisions).where(decisions.c.experiment_id == exp_id)
                         .order_by(decisions.c.sim_time).limit(limit))
        return [_row(r) for r in rows]


def delete_experiment(exp_id: int, engine=None) -> bool:
    eng = engine or get_engine()
    with eng.begin() as c:
        for t in (timeseries, decisions, results):
            c.execute(delete(t).where(t.c.experiment_id == exp_id))
        r = c.execute(delete(experiments).where(experiments.c.id == exp_id))
        return r.rowcount > 0
