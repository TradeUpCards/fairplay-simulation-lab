"""Table-health score — scores ③–⑥ of the eight (kickoff §2; docs/index.html §03).

    Health(T) = 100 − P_pred − P_frag − P_clus − P_bleed   (clamped [0, 100])

Health is NOT average skill or average pot size — averages hide predation
(colluders' winnings and victims' losses cancel). It measures the *recreational
cohort specifically*: how long weak players survive at this table. Each term is
a bounded additive penalty off a perfect-health baseline of 100.

Term taxonomy (index.html §03):
* **Composition-driven** — recomputed whenever the seated set changes:
  * ``P_pred`` (0–45): predation pressure — skill-weighted aggressive vs
    recreational pool, on a saturating curve. One aggressor among four
    recreationals is tolerable; two on a short-handed table is exponentially
    worse. Depends on score ① (classification).
  * ``P_frag`` (0–25): fragility — rises as ``seated/max`` falls and as the
    paid-seat-time trend stalls/declines. Short-handed concentrates exposure.
  * ``P_clus`` (0–30): active-cluster severity — the integrity band (score ②)
    of any seated flagged cluster × the fraction of seats it holds.
* **Observed** — held fixed between seatings, lags composition:
  * ``P_bleed`` (0–20): actual recreational session truncations vs archetype
    baseline. Requires played-out session data; **0 in the Day-2 static
    snapshot** (roster sessions are still ``active``) and populated by the
    counterfactual sim. This is why composition leads and bleed follows.

Bands (index.html §03): 70–100 healthy · 50–69 fragile · 30–49
beginner_unfriendly · 0–29 collapsed. Plus a special **integrity_candidate**
flag: a table with a seated ``high``-band cluster is surfaced to the pit-boss
queue *regardless* of its numeric health.

Calibration: ``K_PRED = ln(9)/2`` is set so the acceptance table T-22
(2 aggressive_predatory, 3/6 seats, flat trend) lands at exactly
Health = 38 → beginner_unfriendly (kickoff §2; CASE-A evidence seed). All
constants mirror ``docs/scoring-thresholds.md §2``.

Guardrail: this is the **table-health** lens, kept distinct from integrity.
P_clus *consumes* the integrity band but health never asserts collusion; a
grinder/predatory mix is a health concern, not an integrity verdict.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, NamedTuple

from .classify import classify

# --- Calibrated constants (mirror in scoring-thresholds.md §2) ---
# P_pred: skill-weighted aggressor pressure on a saturating curve.
PRED_MAX = 45.0
PRED_K = math.log(9) / 2          # = 1.0986; calibrated so T-22 P_pred = 40 exactly
PRED_SOFT = 1.0                   # denominator softening: pressure = agg / (vulnerable + SOFT)
AGGRESSOR_WEIGHTS = {             # skill-weighted contribution to predation
    "aggressive_predatory": 1.0,
    "grinder": 0.35,
}
VULNERABLE_ARCHETYPES = ("new", "recreational")

# P_frag: occupancy + trend fragility.
FRAG_MAX = 25.0
FRAG_W_OCC = 30.0                 # weight on (1 - occupancy); pre-clamp
FRAG_TREND_PEN = {               # paid_seat_time_trend stagnation penalty
    "growing": 0.0,
    "stable": 2.0,
    "flat": 7.0,
    "declining": 12.0,
}

# P_clus: integrity-band severity × seat fraction.
CLUS_MAX = 30.0
CLUS_SEVERITY = {                 # from integrity score ② band
    "high": 1.0,
    "neutral": 0.35,
    "low": 0.15,
    "manual_review": 0.0,         # account-level bot queue — not a table cluster
}

# P_bleed: observed recreational truncation.
BLEED_MAX = 20.0
BLEED_PER_TRUNCATION = 7.0        # penalty per truncated recreational session
BLEED_TRUNCATION_RATIO = 0.5      # session < 0.5 × archetype baseline = truncated
ARCHETYPE_SESSION_BASELINE = {    # expected minutes by archetype (rough)
    "new": 30.0,
    "recreational": 60.0,
}

# Health bands.
BANDS = (  # (low_inclusive, high_inclusive, name)
    (70, 100, "healthy"),
    (50, 69, "fragile"),
    (30, 49, "beginner_unfriendly"),
    (0, 29, "collapsed"),
)


class ReasonCode(NamedTuple):
    code: str
    detail: str
    signals: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "signals": self.signals}


class HealthScore(NamedTuple):
    table_id: str
    health: float
    band: str
    integrity_candidate: bool          # seated high-band cluster → pit-boss queue
    terms: dict[str, float]            # P_pred, P_frag, P_clus, P_bleed
    reason_codes: list[ReasonCode]

    def as_dict(self) -> dict[str, Any]:
        return {
            "table_id": self.table_id,
            "health": round(self.health, 1),
            "band": self.band,
            "integrity_candidate": self.integrity_candidate,
            "terms": {k: round(v, 2) for k, v in self.terms.items()},
            "reason_codes": [rc.as_dict() for rc in self.reason_codes],
        }


def band_for(health: float) -> str:
    # Half-open from each band's lower cutoff (BANDS is ordered high→low), so
    # fractional values never fall through a gap: 69.5 → fragile, not collapsed.
    h = max(0.0, min(100.0, health))
    for lo, _hi, name in BANDS:
        if h >= lo:
            return name
    return "collapsed"


def _archetype_of(pid: str, players_by_id: Mapping[str, Mapping],
                  classifications: Mapping[str, str] | None) -> str | None:
    if classifications and pid in classifications:
        return classifications[pid]
    p = players_by_id.get(pid)
    return classify(p).archetype if p else None


def p_pred(archetypes: list[str]) -> tuple[float, dict[str, Any]]:
    """Predation pressure: skill-weighted aggressors vs the vulnerable pool, on
    a saturating curve. 0 when no aggressors are seated."""
    agg = sum(AGGRESSOR_WEIGHTS.get(a, 0.0) for a in archetypes)
    vulnerable = sum(1 for a in archetypes if a in VULNERABLE_ARCHETYPES)
    if agg == 0:
        return 0.0, {"aggressor_weight": 0.0, "vulnerable": vulnerable, "pressure": 0.0}
    pressure = agg / (vulnerable + PRED_SOFT)
    val = PRED_MAX * (1 - math.exp(-PRED_K * pressure))
    return val, {"aggressor_weight": round(agg, 2), "vulnerable": vulnerable,
                 "pressure": round(pressure, 3)}


def p_frag(seated: int, max_seats: int, trend: str) -> tuple[float, dict[str, Any]]:
    """Fragility: short-handed + stalling paid-seat-time concentrate exposure."""
    occ = min(1.0, (seated / max_seats)) if max_seats else 1.0  # cap: a full/over-full table is not fragile on occupancy
    trend_pen = FRAG_TREND_PEN.get(trend, FRAG_TREND_PEN["stable"])
    val = max(0.0, min(FRAG_MAX, FRAG_W_OCC * (1 - occ) + trend_pen))
    return val, {"occupancy": round(occ, 3), "trend": trend, "trend_penalty": trend_pen}


def p_clus(seated_ids: list[str], seated_count: int,
           cluster_band_by_member: Mapping[str, tuple[str, str]]
           ) -> tuple[float, dict[str, Any], bool]:
    """Active-cluster severity from the integrity band of seated clusters.

    ``cluster_band_by_member`` maps player_id -> (cluster_id, integrity_band).
    Returns (penalty, signals, integrity_candidate_flag)."""
    by_cluster: dict[str, tuple[str, int]] = {}  # cluster_id -> (band, seat_count)
    for pid in seated_ids:
        if pid in cluster_band_by_member:
            cid, band = cluster_band_by_member[pid]
            b, n = by_cluster.get(cid, (band, 0))
            by_cluster[cid] = (band, n + 1)
    total = 0.0
    flagged = False
    detail = {}
    for cid, (band, n) in by_cluster.items():
        sev = CLUS_SEVERITY.get(band, 0.0)
        frac = n / seated_count if seated_count else 0.0
        contrib = CLUS_MAX * sev * frac
        total += contrib
        detail[cid] = {"band": band, "seats": n, "fraction": round(frac, 3),
                       "penalty": round(contrib, 2)}
        if band == "high":
            flagged = True
    return min(CLUS_MAX, total), {"clusters": detail}, flagged


def p_bleed(seated_ids: list[str], table_id: str,
            players_by_id: Mapping[str, Mapping],
            sessions: list[Mapping[str, Any]] | None,
            classifications: Mapping[str, str] | None) -> tuple[float, dict[str, Any]]:
    """Observed recreational truncation. Counts *realized* completed
    new/recreational sessions at this table that ended far below their archetype
    baseline.

    Only realized history counts: the per-case ``standard`` / ``fairplay``
    sessions are **counterfactual projections** (what would happen if a case
    player were routed one way vs another), not observed room history, so they
    are excluded — otherwise CASE-A's hypothetical P-104 churn would leak into
    the static health of T-22, a table P-104 is not even seated at. Result: 0 in
    the Day-2 static snapshot (roster sessions are ``active``); populated by the
    counterfactual sim once sessions play out."""
    if not sessions:
        return 0.0, {"truncated": 0, "observed": False}
    truncated = 0
    considered = 0
    for s in sessions:
        if s.get("table_id") != table_id or s.get("status") != "completed":
            continue
        if s.get("scenario") in ("standard", "fairplay"):
            continue  # counterfactual projection, not realized history
        pid = s.get("player_id")
        arch = _archetype_of(pid, players_by_id, classifications) if pid else None
        if arch not in VULNERABLE_ARCHETYPES:
            continue
        considered += 1
        dur = s.get("duration_min")
        baseline = ARCHETYPE_SESSION_BASELINE.get(arch, 60.0)
        early = s.get("exit_reason") == "voluntary_short_early_exit"
        if early or (dur is not None and dur < BLEED_TRUNCATION_RATIO * baseline):
            truncated += 1
    val = min(BLEED_MAX, BLEED_PER_TRUNCATION * truncated)
    return val, {"truncated": truncated, "considered": considered,
                 "observed": considered > 0}


def score_table(table: Mapping[str, Any],
                players_by_id: Mapping[str, Mapping],
                cluster_band_by_member: Mapping[str, tuple[str, str]],
                classifications: Mapping[str, str] | None = None,
                sessions: list[Mapping[str, Any]] | None = None) -> HealthScore:
    """Compute Health(T) and its four terms for one table_roster entry."""
    tid = table.get("table_id", "?")
    seated_ids = list(table.get("seated_player_ids", []))
    seated_count = table.get("seated_count", len(seated_ids))
    max_seats = table.get("max_seats", seated_count)
    trend = table.get("paid_seat_time_trend", "stable")

    archetypes = [a for a in (_archetype_of(p, players_by_id, classifications)
                              for p in seated_ids) if a]

    pred, pred_sig = p_pred(archetypes)
    frag, frag_sig = p_frag(seated_count, max_seats, trend)
    clus, clus_sig, integrity_candidate = p_clus(seated_ids, seated_count,
                                                  cluster_band_by_member)
    bleed, bleed_sig = p_bleed(seated_ids, tid, players_by_id, sessions, classifications)

    health = max(0.0, min(100.0, 100.0 - pred - frag - clus - bleed))
    band = band_for(health)

    rcs = [
        ReasonCode("predation_pressure",
            f"Predation pressure {pred:.0f}/45 — skill-weighted aggressor load "
            f"{pred_sig['aggressor_weight']} against {pred_sig['vulnerable']} "
            f"recreational/new seat(s).", pred_sig),
        ReasonCode("fragility",
            f"Fragility {frag:.0f}/25 — {seated_count}/{max_seats} seats, "
            f"paid-seat-time trend '{trend}'. Short-handed concentrates exposure.",
            frag_sig),
        ReasonCode("active_cluster_severity",
            f"Active-cluster severity {clus:.0f}/30 from seated flagged cluster(s)."
            if clus > 0 else "No flagged cluster actively seated (P_clus 0).",
            clus_sig),
        ReasonCode("observed_bleed",
            f"Observed recreational truncation {bleed:.0f}/20."
            if bleed_sig["observed"] else
            "No observed recreational truncation yet (composition-led snapshot).",
            bleed_sig),
    ]
    if integrity_candidate:
        rcs.append(ReasonCode("integrity_candidate",
            "A high-band coordinated cluster is actively seated — surface to the "
            "pit-boss review queue regardless of numeric health. Recommend review, "
            "not a verdict.", {}))

    return HealthScore(tid, health, band, integrity_candidate,
                       {"P_pred": pred, "P_frag": frag, "P_clus": clus, "P_bleed": bleed},
                       rcs)


def build_cluster_band_index(relationships: Mapping[str, Any],
                             integrity_assessments: list[Any]) -> dict[str, tuple[str, str]]:
    """Map each cluster member player_id -> (cluster_id, integrity_band), using
    the integrity score ② output. Households/overlaps do not feed P_clus."""
    band_by_cluster = {a.group_id: a.band for a in integrity_assessments
                       if a.group_kind == "cluster"}
    out: dict[str, tuple[str, str]] = {}
    for c in relationships.get("clusters", []):
        cid = c.get("cluster_id")
        band = band_by_cluster.get(cid, "low")
        for m in c.get("member_ids", []):
            out[m] = (cid, band)
    return out


def score_all_tables(tables: list[Mapping[str, Any]],
                     players_by_id: Mapping[str, Mapping],
                     cluster_band_by_member: Mapping[str, tuple[str, str]],
                     classifications: Mapping[str, str] | None = None,
                     sessions: list[Mapping[str, Any]] | None = None) -> list[HealthScore]:
    return [score_table(t, players_by_id, cluster_band_by_member, classifications, sessions)
            for t in tables]
