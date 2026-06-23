"""SQLite persistence — store runs so they can be queried and replayed.

A run is fully described by ``(table, seed, n_hands, equity_samples)``, so the
DB is a cache/record, not the source of truth: replaying the same key
regenerates byte-identical results. Stored: run metadata, per-player features,
and per-hand summaries.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .runner import SimResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT,
    seed         INTEGER NOT NULL,
    n_hands      INTEGER NOT NULL,
    big_blind    INTEGER NOT NULL,
    created_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS players (
    run_id     INTEGER, player_id INTEGER, archetype TEXT,
    cluster_id TEXT, household_id TEXT,
    PRIMARY KEY (run_id, player_id)
);
CREATE TABLE IF NOT EXISTS features (
    run_id INTEGER, player_id INTEGER, archetype TEXT,
    hands_dealt INTEGER, vpip REAL, pfr REAL, aggression_factor REAL,
    avg_pot_bb REAL, timing_regularity REAL, soft_play_delta REAL, net_bb REAL,
    PRIMARY KEY (run_id, player_id)
);
CREATE TABLE IF NOT EXISTS hands (
    run_id INTEGER, hand_id INTEGER, board TEXT, pot_bb REAL, payoffs TEXT,
    PRIMARY KEY (run_id, hand_id)
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA)
    return conn


def save_result(result: SimResult, db_path: str | Path, created_at: float | None = None) -> int:
    """Persist a SimResult; returns the new run_id."""
    conn = connect(db_path)
    arch = {p.player_id: p for p in result.roster}
    try:
        cur = conn.execute(
            "INSERT INTO runs (label, seed, n_hands, big_blind, created_at) VALUES (?,?,?,?,?)",
            (result.label, result.seed, result.n_hands, result.big_blind,
             created_at if created_at is not None else time.time()),
        )
        run_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO players VALUES (?,?,?,?,?)",
            [(run_id, p.player_id, p.archetype, p.cluster_id, p.household_id)
             for p in result.roster],
        )
        conn.executemany(
            "INSERT INTO features VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(run_id, pid, arch[pid].archetype, f["hands_dealt"], f["vpip"], f["pfr"],
              f["aggression_factor"], f["avg_pot_bb"], f["timing_regularity"],
              f["soft_play_delta"], f["net_bb"])
             for pid, f in result.features.items()],
        )
        conn.executemany(
            "INSERT INTO hands VALUES (?,?,?,?,?)",
            [(run_id, h.hand_id, " ".join(h.board), h.pot_bb, json.dumps(h.payoffs))
             for h in result.hands],
        )
        conn.commit()
        return run_id
    finally:
        conn.close()


def load_features(db_path: str | Path, run_id: int) -> list[dict]:
    conn = connect(db_path)
    try:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(features)")]
        rows = conn.execute(
            "SELECT * FROM features WHERE run_id=? ORDER BY player_id", (run_id,)
        ).fetchall()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def list_runs(db_path: str | Path) -> list[dict]:
    conn = connect(db_path)
    try:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(runs)")]
        rows = conn.execute("SELECT * FROM runs ORDER BY run_id").fetchall()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()
