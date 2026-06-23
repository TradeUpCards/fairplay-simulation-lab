"""In-memory `Room` — the live, mutable counterpart to the frozen `data/*.json`.

It mirrors the exact assembly used by `scripts/build_health.py` /
`scripts/build_router.py` so a fresh Room reproduces the frozen scores
byte-for-byte. The only thing that changes at runtime is the seating: `stand()`
and `sit()` mutate a table's roster, and we re-run `score_table()` for *only* the
affected table (the cluster-band index depends on relationships, not seating, so
it's computed once and reused). Everything else stays the scoring engine, untouched.

State is process-memory only — it resets on restart. That's intentional for the
demo; persistence is a later concern if it's ever earned.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # make the top-level `scoring` package importable

from scoring.health import (  # noqa: E402
    HealthScore,
    build_cluster_band_index,
    score_all_tables,
    score_table,
)
from scoring.integrity import score_integrity  # noqa: E402

DATA = ROOT / "data"


def _load(name: str) -> Any:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class RoomError(ValueError):
    """A rejected seating mutation (player not seated, table full, etc.)."""


class Room:
    """Live room state + the two seating mutations, each re-scoring its table."""

    def __init__(self) -> None:
        rel = _load("relationships.json")
        praw = _load("players.json")
        players = praw["players"] if isinstance(praw, dict) else praw
        self.players_by_id: dict[str, Any] = {p["player_id"]: p for p in players}

        # The roster is the mutable surface — seated_player_ids change on stand/sit.
        self.tables: list[dict[str, Any]] = _load("table_roster.json")["tables"]
        self.tables_by_id: dict[str, dict[str, Any]] = {t["table_id"]: t for t in self.tables}

        # Realized sessions feed P_bleed; counterfactual rows are excluded upstream.
        self.sessions = [s for s in _load("sessions.json")["sessions"] if "session_id" in s]

        # Integrity (and thus the cluster-band index) is seating-independent —
        # it's about who is *in* a cluster, so we compute it once and reuse it.
        integ = score_integrity(rel, players)
        self.cbi = build_cluster_band_index(rel, integ)

        # Initial full scoring — identical call to build_health.py.
        self.health: dict[str, HealthScore] = {
            h.table_id: h
            for h in score_all_tables(self.tables, self.players_by_id, self.cbi, sessions=self.sessions)
        }

    # ── queries ──────────────────────────────────────────────────────────────
    def table_of(self, player_id: str) -> dict[str, Any] | None:
        for t in self.tables:
            if player_id in t.get("seated_player_ids", []):
                return t
        return None

    def _rescore(self, table_id: str) -> HealthScore:
        h = score_table(self.tables_by_id[table_id], self.players_by_id, self.cbi, sessions=self.sessions)
        self.health[table_id] = h
        return h

    # ── mutations ────────────────────────────────────────────────────────────
    def stand(self, player_id: str) -> HealthScore:
        """Remove a player from whatever table they're seated at; rescore it."""
        t = self.table_of(player_id)
        if t is None:
            raise RoomError(f"{player_id} is not seated at any table")
        t["seated_player_ids"].remove(player_id)
        self._sync_counts(t)
        return self._rescore(t["table_id"])

    def sit(self, player_id: str, table_id: str) -> HealthScore:
        """Seat a player at a table; rescore it. Rejects full tables / double-seating."""
        if player_id not in self.players_by_id:
            raise RoomError(f"unknown player {player_id}")
        t = self.tables_by_id.get(table_id)
        if t is None:
            raise RoomError(f"unknown table {table_id}")
        if player_id in t["seated_player_ids"]:
            raise RoomError(f"{player_id} is already seated at {table_id}")
        current = self.table_of(player_id)
        if current is not None:
            raise RoomError(f"{player_id} is already seated at {current['table_id']} — stand them up first")
        if t["max_seats"] - len(t["seated_player_ids"]) <= 0:
            raise RoomError(f"{table_id} is full")
        t["seated_player_ids"].append(player_id)
        self._sync_counts(t)
        return self._rescore(table_id)

    @staticmethod
    def _sync_counts(t: dict[str, Any]) -> None:
        t["seated_count"] = len(t["seated_player_ids"])
        t["open_seats"] = t["max_seats"] - t["seated_count"]

    # ── snapshots (the wire shapes the frontend binds to) ─────────────────────
    def table_update(self, table_id: str) -> dict[str, Any]:
        """One table's current roster + recomputed health — the SSE event payload."""
        return {
            "table_id": table_id,
            "table": self.tables_by_id[table_id],
            "health": self.health[table_id].as_dict(),
        }

    def pit_snapshot(self) -> dict[str, Any]:
        """Full operator snapshot: every table's roster + health, healthiest-first."""
        scores = sorted(
            (h.as_dict() for h in self.health.values()),
            key=lambda s: s["health"],
            reverse=True,
        )
        return {"tables": self.tables, "health_scores": scores}
