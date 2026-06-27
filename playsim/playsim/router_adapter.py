"""router_adapter.py — the ONLY playsim module that imports backend scoring.

It owns the cross-package seam between the playsim simulator (which keys players
by ``int``) and the frozen backend FairPlay policy (which keys players by
``"P-*"`` strings and consumes ``table_roster``-shaped dicts):

* the ``sys.path`` insert that makes ``scoring.*`` importable (mirrors
  ``backend/app/room.py`` / ``backend/scripts/build_router.py``);
* int <-> ``P-*`` id conversion (centralized — the single error-prone seam);
* live table-dict assembly carrying **every** field the scorer reads, not just
  the lobby-safe subset (``style_volatility_label`` -> Fit, ``paid_seat_time_trend``
  -> P_frag), so FairPlay ranks on real signal rather than silent defaults;
* the once-per-run integrity / cluster-band index (seating-independent);
* decision-time predicted health (``score_all_tables`` with ``sessions=None`` ->
  ``P_bleed = 0``, composition-driven only);
* the ``route()`` call and selection of the best non-gated open table.

Guardrail: backend **predicted** health is used to *choose* seats; playsim's
realized chip-flow health (``playsim/health.py``) is evaluation-only and is
never imported or consulted here. We do not reimplement the router — the point
is to test the real frozen policy.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .fixture_paths import find_data_root
from .population import (
    format_player_id,
    load_classifications,
    load_players_by_id,
    load_relationships,
)


def _ensure_backend_on_path(root: Path) -> None:
    """Make ``scoring.*`` importable. Same pattern as backend/app/room.py."""
    backend_path = root / "backend"
    if not backend_path.is_dir():
        backend_path = Path(__file__).resolve().parents[2] / "backend"
    backend = str(backend_path)
    if backend not in sys.path:
        sys.path.insert(0, backend)


@dataclass
class Placement:
    """A FairPlay routing decision for one seeker. ``table_id is None`` -> balk."""
    table_id: str | None
    badge: str | None
    rank: float | None
    health: float | None          # predicted (composition-driven) health of the chosen table
    health_band: str | None
    operator_view: list[dict] = field(default_factory=list)   # full ranked breakdown (causal trace)
    reason: dict = field(default_factory=dict)                  # chosen-entry operator metadata

    @property
    def balked(self) -> bool:
        return self.table_id is None


def make_table_dict(
    table_id: str,
    seated_int_ids: list[int],
    max_seats: int,
    *,
    style_volatility_label: str,
    paid_seat_time_trend: str,
    table_mode: str = "active",
    target_seats: int | None = None,
    stakes: str = "",
    game_type: str = "",
    pace_label: str = "",
) -> dict[str, Any]:
    """Assemble a backend-shaped live table dict from playsim int ids.

    Carries the scorer's composition inputs explicitly: ``style_volatility_label``
    (read by ``seating.style_key`` for the Fit-matrix column) and
    ``paid_seat_time_trend`` (read by ``health.p_frag``). Omitting them would let
    Fit/fragility silently collapse to ``"mixed"``/``"stable"``.
    """
    seated = [format_player_id(p) for p in seated_int_ids]
    n = len(seated)
    return {
        "table_id": table_id,
        "max_seats": max_seats,
        "seated_player_ids": seated,
        "seated_count": n,
        "open_seats": max(0, max_seats - n),
        "table_mode": table_mode,
        "target_seats": target_seats if target_seats is not None else max_seats,
        "style_volatility_label": style_volatility_label,
        "paid_seat_time_trend": paid_seat_time_trend,
        "stakes": stakes,
        "game_type": game_type,
        "pace_label": pace_label,
    }


class RouterAdapter:
    """Stateful wrapper: loads fixtures + integrity index once, routes many times."""

    def __init__(self, root: Path | None = None, *, liveness_aware: bool = False) -> None:
        self.root = find_data_root(root)
        self.liveness_aware = liveness_aware
        _ensure_backend_on_path(self.root)
        # imported lazily (after the path insert) so the module imports cleanly
        # even when backend isn't on the default path.
        from scoring.health import build_cluster_band_index
        from scoring.integrity import score_integrity

        self.players_by_id: dict[str, dict] = load_players_by_id(self.root)
        self.classifications: dict[str, str] = load_classifications(self.root)
        self._players_list = list(self.players_by_id.values())
        relationships = load_relationships(self.root)
        # seating-independent: compute once, reuse across the whole horizon.
        integrity = score_integrity(relationships, self._players_list)
        self.cbi = build_cluster_band_index(relationships, integrity)

    def predicted_health(self, live_tables: list[dict]) -> dict:
        """``{table_id: HealthScore}`` over the exact set passed to ``route``.

        ``sessions=None`` holds ``P_bleed = 0`` — composition-driven only."""
        from scoring.health import score_all_tables

        scores = score_all_tables(
            live_tables, self.players_by_id, self.cbi,
            classifications=self.classifications, sessions=None,
            liveness_aware=self.liveness_aware,
        )
        return {h.table_id: h for h in scores}

    def recommend(self, seeker_int_id: int, live_tables: list[dict]) -> Placement:
        """Route one seeker via the real backend policy.

        Scores the full ``live_tables`` set (so ``route`` never ``KeyError``s on a
        missing ``health_by_id`` entry), calls ``route``, then selects the
        highest-rank ``operator_view`` entry that is **not** integrity-gated and
        whose live table currently has an open seat. Returns a balk
        (``table_id=None``) when none qualifies.
        """
        from scoring.router import route

        seeker = format_player_id(seeker_int_id)
        health_by_id = self.predicted_health(live_tables)
        result = route(
            seeker, live_tables, self.players_by_id, self.cbi,
            health_by_id, classifications=self.classifications,
            liveness_aware=self.liveness_aware,
        )
        operator_view = result["operator_view"]
        open_by_id = {t["table_id"]: t.get("open_seats", 0) for t in live_tables}
        # operator_view is sorted rank-desc with gated tables sunk to the bottom.
        for entry in operator_view:
            if entry.get("badge") == "hidden_gated":
                continue
            if open_by_id.get(entry["table_id"], 0) > 0:
                return Placement(
                    table_id=entry["table_id"],
                    badge=entry.get("badge"),
                    rank=entry.get("rank"),
                    health=entry.get("health"),
                    health_band=entry.get("health_band"),
                    operator_view=operator_view,
                    reason=entry,
                )
        return Placement(None, None, None, None, None, operator_view, {})
