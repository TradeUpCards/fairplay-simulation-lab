"""Router — score ⑧, the decision (kickoff §2 ⑧; docs/index.html §05).

    Rank(P,T) = 0.30·Fit(P,T) + 0.40·Health(T) + 0.30·ΔHealth(P→T)

A **frozen, deterministic, auditable policy** — by design there is NO model in
the routing loop. ML lives upstream (it computes Fit, Health, integrity); the
decision itself is a human-designed weighted formula any operator can inspect
and trace to specific factor values. The weights are calibrated offline on the
eval lab, not learned end-to-end.

Two hard gates wrap the rank, in order:

1. **Integrity hard-gate (first).** A table with a seated high-band cluster
   under review is **removed from the candidate set entirely** — not ranked
   down, removed. (The player may still manually select it; the badge reflects
   the recommendation only.) → badge ``hidden_gated``.
2. **Vulnerable-protection gate.** A table is only *promoted* (Recommended /
   Good fit) if the player's **seating-risk is LOW**. Medium/high-risk tables
   stay visible but un-promoted (``available``). This is what structurally
   enforces CASE-A: "T-22 not promoted to new or recreational players."

Then, among low-risk candidates, the **rank tier** sets the badge:
``rank ≥ REC_RANK_MIN → recommended`` · ``≥ GOODFIT_RANK_MIN → good_fit`` ·
else ``available``.

**Player-facing vs operator-facing (load-bearing hard rule).** The lobby badge
is the ONLY player-facing output and is neutral text ("Recommended for you",
"Good fit", "Available"). It must NOT carry the rank, health score, archetype,
seating-risk, or any integrity language. ``route`` returns both a
``player_lobby`` view (badges + neutral table facts only) and an
``operator_view`` (full breakdown) so the seam is explicit in the output.

Badge tier thresholds are calibrated to the CASE-A worked example (index.html
§05): for the new player P-104, T-8 → Recommended, T-14 → Good fit, T-22 →
Available. (Absolute rank numbers differ from the §05 illustration because the
Health champion is anchored to the only pinned value, T-22=38; the badge
*ordering* is what's pinned and holds. See ``docs/scoring-thresholds.md §4``.)
"""

from __future__ import annotations

from typing import Any, Mapping, NamedTuple

from .health import HealthScore
from .seating import (
    SeatingScore, score_seating, W_FIT, W_HEALTH, W_DELTA,
)

# --- Badge tier thresholds (calibrated offline; mirror scoring-thresholds.md §4d) ---
REC_RANK_MIN = 58.0       # >= this (and low risk) → "recommended"
GOODFIT_RANK_MIN = 40.0   # >= this (and low risk) → "good_fit"

# Badge keys → neutral player-facing display label (the ONLY lobby-visible text).
BADGE_LABELS = {
    "recommended": "Recommended for you",
    "good_fit": "Good fit",
    "available": "Available",
    "hidden_gated": None,   # not shown in the lobby at all
}
# Neutral, player-safe table fields the lobby may display (NO scores/risk/archetype).
LOBBY_SAFE_FIELDS = ("table_id", "stakes", "game_type", "max_seats",
                     "seated_count", "open_seats", "pace_label")


def rank(fit: float, health: float, delta_health: float) -> float:
    """The frozen weighted policy. O(1)."""
    return W_FIT * fit + W_HEALTH * health + W_DELTA * delta_health


class RoutedTable(NamedTuple):
    table_id: str
    rank: float
    badge: str
    seating: SeatingScore
    health: HealthScore

    @property
    def lobby_label(self) -> str | None:
        return BADGE_LABELS.get(self.badge)


def _badge(rank_val: float, seating: SeatingScore) -> str:
    if seating.integrity_gated:
        return "hidden_gated"
    # Promotion requires LOW seating-risk (vulnerable-protection gate).
    if seating.seating_risk != "low":
        return "available"
    if rank_val >= REC_RANK_MIN:
        return "recommended"
    if rank_val >= GOODFIT_RANK_MIN:
        return "good_fit"
    return "available"


def route(player_id: str, tables: list[Mapping[str, Any]],
          players_by_id: Mapping[str, Mapping],
          cluster_band_by_member: Mapping[str, tuple[str, str]],
          health_by_id: Mapping[str, HealthScore],
          classifications: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Route a seeking player across all open tables.

    Returns a dict with two views: ``operator_view`` (full rank/score breakdown,
    pit-boss console) and ``player_lobby`` (neutral badges + safe table facts
    only — the player-facing seam)."""
    routed: list[RoutedTable] = []
    for t in tables:
        if t.get("open_seats", 0) <= 0:
            continue
        tid = t["table_id"]
        h = health_by_id[tid]
        s = score_seating(player_id, t, players_by_id, cluster_band_by_member, h,
                          classifications)
        r = rank(s.fit, h.health, s.delta_health)
        routed.append(RoutedTable(tid, r, _badge(r, s), s, h))

    # Sort by rank desc; gated tables sink to the bottom of the operator view.
    routed.sort(key=lambda rt: (rt.badge != "hidden_gated", rt.rank), reverse=True)

    operator_view = []
    player_lobby = []
    table_by_id = {t["table_id"]: t for t in tables}
    for rt in routed:
        operator_view.append({
            "table_id": rt.table_id,
            "rank": round(rt.rank, 1),
            "badge": rt.badge,
            "fit": round(rt.seating.fit, 1),
            "health": round(rt.health.health, 1),
            "health_band": rt.health.band,
            "delta_health": round(rt.seating.delta_health, 1),
            "seating_risk": rt.seating.seating_risk,
            "integrity_gated": rt.seating.integrity_gated,
        })
        if rt.badge == "hidden_gated":
            continue  # gated tables are not shown in the player lobby
        src = table_by_id.get(rt.table_id, {})
        safe = {k: src[k] for k in LOBBY_SAFE_FIELDS if k in src}
        safe["badge"] = rt.badge
        safe["badge_label"] = rt.lobby_label
        player_lobby.append(safe)

    return {
        "player_id": player_id,
        "policy": {"w_fit": W_FIT, "w_health": W_HEALTH, "w_delta": W_DELTA,
                   "rec_rank_min": REC_RANK_MIN, "goodfit_rank_min": GOODFIT_RANK_MIN},
        "operator_view": operator_view,
        "player_lobby": player_lobby,
    }
