"""Realized table health — measured bottom-up from played-out chips.

This is the **health/routing loop**: instead of asserting ``Health(T)``, we play
the table out (persistent stacks) and compute the outcome terms from what
actually happened — how fast the recreational cohort bleeds, how concentrated the
winnings are, how often beginners bust. Comparing two compositions under the same
seed is the Standard-vs-FairPlay counterfactual ("does risk-aware routing produce
healthier tables?").

⚠ **Circularity guardrail** (see ``docs/learn/ai-hand-generation-decision.md`` §4):
these metrics come from first-principles chip flow — who won/lost/busted — **not**
from re-running the scoring engine's ``Health(T)`` formula. That independence is
what makes the comparison a real test rather than a tautology.
"""

from __future__ import annotations

from .runner import SimResult

_REC = frozenset({"new", "recreational", "promo_hunter"})
_PREDATOR = frozenset({"aggressive_predatory", "grinder", "cluster_member", "solver_like"})


def realized_health_score(
    rec_loss_velocity: float, winnings_concentration: float, bust_rate: float,
) -> tuple[float, str]:
    """Transparent realized health (score, band) from first-principles chip-flow
    terms — the **single source** for both the single-table session health
    (``compute_health``) and the room-scale realized summary
    (``room_export._realized_summary``). The recreational bleed rate dominates;
    over-concentration and beginner busts add secondary penalties.
    """
    score = 100.0
    score -= min(50.0, max(0.0, rec_loss_velocity) * 0.05)            # bleed (primary)
    score -= min(18.0, max(0.0, winnings_concentration - 0.6) * 45.0)  # concentration
    score -= min(24.0, bust_rate * 0.55)                             # beginner busts
    score = round(max(0.0, score), 1)
    band = (
        "healthy" if score >= 65
        else "fragile" if score >= 42
        else "beginner_unfriendly"
    )
    return score, band


def compute_health(result: SimResult) -> dict:
    if not result.persist_stacks:
        raise ValueError("health needs a persist_stacks=True session (bust dynamics)")

    arch = {p.player_id: p.archetype for p in result.roster}
    net = {pid: result.features[pid]["net_bb"] for pid in arch}
    rec_ids = [pid for pid, a in arch.items() if a in _REC]
    pred_ids = [pid for pid, a in arch.items() if a in _PREDATOR]

    # Normalize the rec bleed/bust by the cohort's *hands actually played* (in
    # retention mode players leave at different times, so dividing by session
    # hands would wrongly favor the table where the cohort quits fast).
    if result.retention and result.hands_played:
        cohort_hands = sum(result.hands_played.get(pid, 0) for pid in rec_ids)
        rec_per100 = max(cohort_hands / 100.0, 1e-9)
    else:
        rec_per100 = max(result.n_hands / 100.0, 1e-9) * max(len(rec_ids), 1)
    per100 = max(result.n_hands / 100.0, 1e-9)

    # 1) recreational loss velocity — bb bled per 100 cohort hands played
    rec_net = sum(net[pid] for pid in rec_ids)
    rec_loss_velocity = round(-rec_net / rec_per100, 2)

    # 2) winnings concentration — share of all winnings held by the top winner
    won = [v for v in net.values() if v > 0]
    total_won = sum(won) or 1.0
    winnings_concentration = round(max(won, default=0.0) / total_won, 3)

    # 3) beginner bust rate — rec/new rebuys per 100 cohort hands
    rec_busts = sum(result.busts.get(pid, 0) for pid in rec_ids)
    bust_rate = round(rec_busts / rec_per100, 2)

    # 4) predation — net bb the predator cohort extracted (per 100 session hands)
    predation_bb = round(sum(max(net[pid], 0) for pid in pred_ids) / per100, 2)

    # Transparent health score (higher = healthier) — single source in
    # realized_health_score so the room-scale realized summary cannot drift.
    score, band = realized_health_score(rec_loss_velocity, winnings_concentration, bust_rate)

    return {
        "health_score": score,
        "band": band,
        "recreational_loss_velocity_bb_per_100": rec_loss_velocity,
        "winnings_concentration": winnings_concentration,
        "beginner_bust_rate_per_100": bust_rate,
        "predation_bb_per_100": predation_bb,
        "n_recreational": len(rec_ids),
        "n_predator": len(pred_ids),
    }


def compute_retention(
    result: SimResult,
    early_exit_min: float = 30.0,
    checkpoints_min: tuple[float, ...] = (30.0, 60.0, 120.0),
    cohort_ids: list[int] | None = None,
) -> dict:
    """Paid-seat-time / retention — the **north-star** metrics.

    The hypothesis: better routing → healthier composition → lower play-decay →
    **more retained paid seat-time**. Raw hands are a throughput proxy (a table
    can churn many hands by busting players fast); the headline is **seat-time**.

    ``cohort_ids`` pins which players to measure (the routed cohort); defaults to
    all recreational/new at the table. ``seat_minutes`` is how long each actually
    played before logging off — so it captures decay directly.
    """
    if not result.retention:
        raise ValueError("retention metrics need a retention=True session")

    arch = {p.player_id: p.archetype for p in result.roster}
    cohort = cohort_ids if cohort_ids is not None else [
        pid for pid, a in arch.items() if a in _REC
    ]
    k = max(len(cohort), 1)
    sm = result.seat_minutes
    left = result.left_at_minute
    horizon_min = round(result.n_hands * result.minutes_per_hand, 1)

    cohort_min = [sm[pid] for pid in cohort]
    total_min = sum(cohort_min)
    still_active = sum(1 for pid in cohort if left[pid] is None)
    early_exits = sum(1 for pid in cohort if (left[pid] is not None and sm[pid] < early_exit_min))
    # "active at T minutes" = played at least T minutes before leaving
    retention_at = {
        f"{int(t)}min": round(sum(1 for pid in cohort if sm[pid] >= t) / k, 3)
        for t in checkpoints_min
    }

    return {
        "cohort_size": len(cohort),
        # ── north star ──
        "paid_seat_hours_table": round(result.paid_seat_minutes / 60.0, 2),
        "paid_seat_hours_cohort": round(total_min / 60.0, 2),
        "avg_casual_session_min": round(total_min / k, 1),
        # ── retention / decay ──
        "retention_rate": round(still_active / k, 3),
        "retention_at": retention_at,
        "early_exit_rate": round(early_exits / k, 3),
        "early_exits": early_exits,
        # ── supporting (throughput) ──
        "dealt_player_hands": result.dealt_player_hands,
        "mean_hands_played": round(sum(result.hands_played[pid] for pid in cohort) / k, 1),
        "horizon_min": horizon_min,
    }


def _pct_delta(a: float, b: float) -> float:
    return round((b - a) / a * 100.0, 1) if a > 0 else float("inf")


def compare_routing(standard: SimResult, fairplay: SimResult) -> dict:
    """Standard-vs-FairPlay. Headline = Δ play-time (the north star); ΔHealth is
    the driver. Both sessions should be ``retention=True`` over the same horizon."""
    ha, hb = compute_health(standard), compute_health(fairplay)
    out = {
        "standard": ha,
        "fairplay": hb,
        "delta_health": round(hb["health_score"] - ha["health_score"], 1),
        "routing_helped": hb["health_score"] > ha["health_score"],
    }
    if standard.retention and fairplay.retention:
        # the routed cohort = players present in BOTH rosters (fair comparison)
        ids_a = {p.player_id for p in standard.roster}
        ids_b = {p.player_id for p in fairplay.roster}
        cohort_ids = sorted(ids_a & ids_b)
        ra = compute_retention(standard, cohort_ids=cohort_ids)
        rb = compute_retention(fairplay, cohort_ids=cohort_ids)
        out["standard_retention"] = ra
        out["fairplay_retention"] = rb
        # the headline: retained paid seat-time (the north star)
        out["paid_seat_time"] = {
            "standard_hours": ra["paid_seat_hours_cohort"],
            "fairplay_hours": rb["paid_seat_hours_cohort"],
            "delta_hours": round(rb["paid_seat_hours_cohort"] - ra["paid_seat_hours_cohort"], 2),
            "delta_pct": _pct_delta(ra["paid_seat_hours_cohort"], rb["paid_seat_hours_cohort"]),
        }
        out["avg_casual_session_min"] = {
            "standard": ra["avg_casual_session_min"],
            "fairplay": rb["avg_casual_session_min"],
        }
        out["retention_rate"] = {
            "standard": ra["retention_rate"], "fairplay": rb["retention_rate"],
        }
        out["early_exits"] = {
            "standard": ra["early_exits"], "fairplay": rb["early_exits"],
        }
    return out
