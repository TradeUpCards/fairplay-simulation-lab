"""Seating scores — score ⑦ of the eight (kickoff §2 ⑦; docs/index.html §04–§05).

Three player×table scores the router (⑧) consumes:

* **ΔHealth(P→T)** — how Health(T) changes if P joins. Re-scores only the
  composition terms (P_pred/P_frag/P_clus); P_bleed is held fixed (it lags
  until sessions play out). Analytic, O(1) per table — no per-decision
  simulation. ``ΔHealth = Health'(T∪{P}) − Health(T)``.
* **Fit(P,T)** — 0–100, how well P's archetype matches T's style/stakes.
  Champion = an interpretable **archetype × table-style matrix** (the ML
  challenger is a session-length predictor, raced later in P4's lab).
* **Seating-risk(P,T)** — LOW · MEDIUM · HIGH, the player-protection signal:
  a composite of the table's health band, P's new-player vulnerability, the
  integrity gate, and ΔHealth, with reason codes. This is the signal that keeps
  a vulnerable player off a beginner-unfriendly table.

Key conceptual separation (and a known divergence from the index.html §04
illustration — flagged for reconciliation):

  ΔHealth is about the **table's composition**, not the joining player's danger.
  Adding a recreational/new player to a predator-heavy table can yield a *small
  positive* ΔHealth (it dilutes the aggressor ratio and fills a seat) even
  though seating that specific vulnerable player there is **HIGH risk**. The
  index.html §04 worked example shows ΔHealth ≈ −8 for P-104→T-22 by conflating
  the two; the kickoff's literal instruction is "re-score the composition terms,
  take the delta", which is what we implement. The danger to P-104 lives in
  **Seating-risk** (= HIGH for P-104@T-22), which is the actually-pinned
  acceptance — so the demo story (route P-104 to T-8, suppress T-22) holds via
  seating-risk + health band, not via the ΔHealth sign.

Guardrail: seating-risk recommends routing, never a verdict; vulnerable-player
protection and the integrity hard-gate are explicit, surfaced reason codes.
Constants mirror ``docs/scoring-thresholds.md §4``.
"""

from __future__ import annotations

from typing import Any, Mapping, NamedTuple

from .classify import classify
from .health import (
    HealthScore, p_pred, p_frag, p_clus, _archetype_of,
)

# --- Router weights (frozen policy; index.html §05 v0 defaults) ---
W_FIT = 0.30
W_HEALTH = 0.40
W_DELTA = 0.30

VULNERABLE_ARCHETYPES = ("new", "recreational")

# --- Fit champion: table-style keyword → canonical style key ---
STYLE_KEYWORDS = [  # checked in order; first keyword found in the label wins
    ("predatory", "predatory"),
    ("grinder", "grinder_heavy"),
    ("healthy anchor", "healthy_anchor"),
    ("beginner", "beginner_friendly"),
    ("promo", "promo_short"),
    ("long-session", "long_session"),
    ("long session", "long_session"),
    ("recreational", "recreational_heavy"),
    ("regular", "regular_heavy"),
    ("balanced", "balanced"),
    ("casual", "mixed"),
    ("mixed", "mixed"),
]
DEFAULT_STYLE = "mixed"

# Fit(archetype, style) 0–100. The `new` row is calibrated to the index.html §05
# worked example (T-8 balanced = 74, T-14 regular_heavy = 58, T-22 predatory =
# 22). Other rows are directional. Higher = longer/more enjoyable predicted
# session.
FIT_MATRIX: dict[str, dict[str, int]] = {
    "new": {
        "beginner_friendly": 90, "healthy_anchor": 85, "recreational_heavy": 80,
        "balanced": 74, "mixed": 65, "regular_heavy": 58, "long_session": 45,
        "promo_short": 40, "grinder_heavy": 30, "predatory": 22,
    },
    "recreational": {
        "beginner_friendly": 85, "healthy_anchor": 82, "recreational_heavy": 88,
        "balanced": 78, "mixed": 72, "regular_heavy": 60, "long_session": 48,
        "promo_short": 50, "grinder_heavy": 32, "predatory": 25,
    },
    "regular": {
        "beginner_friendly": 55, "healthy_anchor": 68, "recreational_heavy": 70,
        "balanced": 75, "mixed": 70, "regular_heavy": 85, "long_session": 80,
        "promo_short": 55, "grinder_heavy": 65, "predatory": 50,
    },
    "grinder": {
        "beginner_friendly": 30, "healthy_anchor": 45, "recreational_heavy": 60,
        "balanced": 62, "mixed": 58, "regular_heavy": 72, "long_session": 88,
        "promo_short": 40, "grinder_heavy": 90, "predatory": 70,
    },
    "aggressive_predatory": {
        "beginner_friendly": 40, "healthy_anchor": 35, "recreational_heavy": 75,
        "balanced": 60, "mixed": 62, "regular_heavy": 55, "long_session": 60,
        "promo_short": 45, "grinder_heavy": 72, "predatory": 80,
    },
    "promo_hunter": {
        "beginner_friendly": 55, "healthy_anchor": 45, "recreational_heavy": 58,
        "balanced": 52, "mixed": 55, "regular_heavy": 48, "long_session": 35,
        "promo_short": 90, "grinder_heavy": 35, "predatory": 40,
    },
    "healthy_anchor": {
        "beginner_friendly": 70, "healthy_anchor": 88, "recreational_heavy": 82,
        "balanced": 80, "mixed": 72, "regular_heavy": 78, "long_session": 75,
        "promo_short": 50, "grinder_heavy": 55, "predatory": 45,
    },
}
# Tiers that have no calibrated row reuse a nearby one.
FIT_ROW_ALIASES = {
    "cluster_member": "regular",
    "shared_device_household": "recreational",
    "bot_like": "grinder",
}
FIT_DEFAULT = 50  # unknown archetype/style fallback


# --- Seating-risk thresholds (mirror in scoring-thresholds.md §4) ---
DELTA_STRONG_NEGATIVE = -6.0   # ΔHealth this negative bumps risk up a level


class ReasonCode(NamedTuple):
    code: str
    detail: str
    signals: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "signals": self.signals}


class SeatingScore(NamedTuple):
    player_id: str
    table_id: str
    fit: float
    delta_health: float
    seating_risk: str               # low | medium | high
    integrity_gated: bool           # table removed from candidates by hard-gate
    reason_codes: list[ReasonCode]

    def as_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "table_id": self.table_id,
            "fit": round(self.fit, 1),
            "delta_health": round(self.delta_health, 1),
            "seating_risk": self.seating_risk,
            "integrity_gated": self.integrity_gated,
            "reason_codes": [rc.as_dict() for rc in self.reason_codes],
        }


def style_key(table: Mapping[str, Any]) -> str:
    label = str(table.get("style_volatility_label", "")).lower()
    for kw, key in STYLE_KEYWORDS:
        if kw in label:
            return key
    return DEFAULT_STYLE


def fit(player_archetype: str, table: Mapping[str, Any]) -> tuple[float, dict[str, Any]]:
    """Champion Fit(P,T): archetype × table-style matrix lookup."""
    row_key = player_archetype if player_archetype in FIT_MATRIX \
        else FIT_ROW_ALIASES.get(player_archetype, None)
    sk = style_key(table)
    if row_key and row_key in FIT_MATRIX:
        val = FIT_MATRIX[row_key].get(sk, FIT_DEFAULT)
    else:
        val = FIT_DEFAULT
    return float(val), {"archetype": player_archetype, "style": sk,
                        "matrix_row": row_key or "default"}


def delta_health(player_id: str, table: Mapping[str, Any],
                 players_by_id: Mapping[str, Mapping],
                 cluster_band_by_member: Mapping[str, tuple[str, str]],
                 base: HealthScore,
                 classifications: Mapping[str, str] | None = None) -> float:
    """ΔHealth(P→T) = Health'(T∪{P}) − Health(T), re-scoring only the
    composition terms (P_bleed held fixed at the base value)."""
    seated_ids = list(table.get("seated_player_ids", []))
    seated_count = table.get("seated_count", len(seated_ids))
    max_seats = table.get("max_seats", seated_count)
    trend = table.get("paid_seat_time_trend", "stable")

    aug_ids = seated_ids + [player_id]
    aug_n = seated_count + 1
    archetypes = [a for a in (_archetype_of(p, players_by_id, classifications)
                              for p in aug_ids) if a]

    pred, _ = p_pred(archetypes)
    frag, _ = p_frag(aug_n, max_seats, trend)
    clus, _, _ = p_clus(aug_ids, aug_n, cluster_band_by_member)
    bleed = base.terms["P_bleed"]  # held fixed
    health_prime = max(0.0, min(100.0, 100.0 - pred - frag - clus - bleed))
    return health_prime - base.health


def seating_risk(player_archetype: str, base: HealthScore, dh: float
                 ) -> tuple[str, bool, list[ReasonCode]]:
    """Composite player-protection signal: health band + new-player
    vulnerability + integrity hard-gate + ΔHealth. Returns
    (risk_level, integrity_gated, reason_codes)."""
    rcs: list[ReasonCode] = []
    vulnerable = player_archetype in VULNERABLE_ARCHETYPES
    band = base.band

    # Integrity hard-gate: a seated high-band cluster removes the table from the
    # candidate set entirely (index.html §05). Highest-priority signal.
    if base.integrity_candidate:
        rcs.append(ReasonCode("integrity_hard_gate",
            "Table has a high-band coordinated cluster under review — gated out "
            "of seating recommendations entirely (player may still self-select).",
            {"band": band}))
        return "high", True, rcs

    # Map health band → a base risk for a vulnerable (new/recreational) player.
    band_risk = {"healthy": "low", "fragile": "medium",
                 "beginner_unfriendly": "high", "collapsed": "high"}
    if vulnerable:
        level = band_risk.get(band, "medium")
        rcs.append(ReasonCode("vulnerable_on_band",
            f"{player_archetype} player at a '{band}' table (Health "
            f"{base.health:.0f}). New/recreational players are the cohort this "
            f"protects — risk {level}.",
            {"archetype": player_archetype, "band": band, "health": round(base.health, 1)}))
    else:
        # Non-vulnerable players carry low seating risk; the table's own band is
        # a health concern, not a per-seat protection issue.
        level = "low" if band in ("healthy", "fragile") else "medium"
        rcs.append(ReasonCode("non_vulnerable_seating",
            f"{player_archetype} is not in the protected new/recreational cohort; "
            f"seating risk driven only by table band '{band}'.",
            {"archetype": player_archetype, "band": band}))

    # ΔHealth bump: seating that materially degrades the table raises risk.
    if dh <= DELTA_STRONG_NEGATIVE:
        order = ["low", "medium", "high"]
        level = order[min(len(order) - 1, order.index(level) + 1)]
        rcs.append(ReasonCode("delta_health_degradation",
            f"Seating degrades table health by {dh:.1f} — risk bumped to {level}.",
            {"delta_health": round(dh, 1)}))

    return level, False, rcs


def score_seating(player_id: str, table: Mapping[str, Any],
                  players_by_id: Mapping[str, Mapping],
                  cluster_band_by_member: Mapping[str, tuple[str, str]],
                  base_health: HealthScore,
                  classifications: Mapping[str, str] | None = None) -> SeatingScore:
    """Full seating score for one player×table pair."""
    arch = _archetype_of(player_id, players_by_id, classifications) or "unknown"
    unknown_rc = []
    if arch == "unknown":
        # Surface the lookup miss rather than emitting a plausible-looking default
        # silently — this is a contract seam, and a missing player_id is a data
        # bug upstream, not a routable player.
        unknown_rc.append(ReasonCode("unresolved_player",
            f"Player '{player_id}' could not be classified (missing from "
            f"players.json / classifications) — scores are placeholder defaults, "
            f"not a real recommendation.", {"player_id": player_id}))
    fit_val, fit_sig = fit(arch, table)
    dh = delta_health(player_id, table, players_by_id, cluster_band_by_member,
                      base_health, classifications)
    risk, gated, risk_rcs = seating_risk(arch, base_health, dh)

    rcs = [
        *unknown_rc,
        ReasonCode("fit", f"Fit {fit_val:.0f}/100 — {arch} at a "
                   f"'{fit_sig['style']}' table.", fit_sig),
        ReasonCode("delta_health",
                   f"ΔHealth {dh:+.1f} — marginal change to table composition "
                   f"health if seated (P_bleed held fixed).",
                   {"delta_health": round(dh, 1)}),
        *risk_rcs,
    ]
    return SeatingScore(player_id, table.get("table_id", "?"), fit_val, dh,
                        risk, gated, rcs)
