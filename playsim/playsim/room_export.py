"""Canonical room_sim output builder (+ derived v1 room_metrics adapter in U7).

``build_canonical`` is the **source of truth**: a playsim-native dict carrying the
full causal trace (meta, run_config, arrival_intents, routing_decisions,
seat_events, sessions, hourly timeline, table_timelines) plus summary metrics.
The realized summary mirrors ``playsim/health.py``'s first-principles chip-flow
formulas — it is **evaluation-only** and is computed here, downstream of routing,
never fed back into a seating decision.
"""

from __future__ import annotations

from .room import COHORT, RoomResult

SCHEMA_VERSION = "room_sim/1.0"
FIXTURE_NOTE = "Synthetic sandbox data — not real play."


def _realized_summary(result: RoomResult) -> dict:
    arch = result.archetype_of
    cohort = [p for p in arch if arch[p] in COHORT]
    cohort_hands = sum(result.hands_played.get(p, 0) for p in cohort)
    per100 = max(cohort_hands / 100.0, 1e-9)

    cohort_net = sum(result.net_bb.get(p, 0.0) for p in cohort)
    rec_loss_velocity = round(-cohort_net / per100, 2)

    won = [v for v in result.net_bb.values() if v > 0]
    winnings_concentration = round(max(won, default=0.0) / (sum(won) or 1.0), 3)

    cohort_busts = sum(result.busts.get(p, 0) for p in cohort)
    bust_rate = round(cohort_busts / per100, 2)

    # Realized health — mirrors playsim/health.compute_health (independent of the
    # backend predicted health used for routing; this is the evaluation side).
    score = 100.0
    score -= min(50.0, max(0.0, rec_loss_velocity) * 0.05)
    score -= min(18.0, max(0.0, winnings_concentration - 0.6) * 45.0)
    score -= min(24.0, bust_rate * 0.55)
    score = round(max(0.0, score), 1)
    band = ("healthy" if score >= 65 else "fragile" if score >= 42
            else "beginner_unfriendly")

    cohort_seat_min = sum(result.seat_minutes.get(p, 0.0) for p in cohort)
    breaks = sum(1 for e in result.seat_events if e.get("event") == "break")
    departures = sum(1 for e in result.seat_events if e.get("event") == "leave")

    return {
        # ── primary (R21) ──
        "vulnerable_paid_seat_hours": round(cohort_seat_min / 60.0, 2),
        "vulnerable_paid_seat_min": round(cohort_seat_min, 1),
        # ── secondary (R22) ──
        "recreational_loss_velocity_bb_per_100": rec_loss_velocity,
        "beginner_bust_rate_per_100": bust_rate,
        "winnings_concentration": winnings_concentration,
        "realized_health_score": score,
        "realized_health_band": band,
        "table_breaks": breaks,
        "departures": departures,
        "cohort_size": len(cohort),
        "total_hands": result.hands_total,
        # ── protect-specific (0 unless FairPlay-protect ran) ──
        "balk_count": len(result.balked),
        "deferred_count": len(result.deferred),
        "prevented_bad_sessions": len(result.deferred),
    }


def build_canonical(result: RoomResult, *, data_root: str = "") -> dict:
    """Assemble the canonical playsim-native room_sim dict from a RoomResult."""
    run_config = {
        "policy": result.policy_name,
        "master_seed": result.master_seed,
        "horizon_min": result.horizon_min,
        "hands_per_hour": result.hands_per_hour,
        "min_per_hand": result.min_per_hand,
        "starting_stack_bb": result.starting_stack_bb,
        "skill_edge": result.skill_edge,
        "equity_samples": result.equity_samples,
    }
    meta = {
        "schema_version": SCHEMA_VERSION,
        "engine": "playsim",
        "format": "room_sim",
        "agent_model": result.agent_model,
        "agent_version": result.agent_version,
        "data_root": data_root,
        "fixture_note": FIXTURE_NOTE,
        **run_config,
    }
    return {
        "meta": meta,
        "run_config": run_config,
        "arrival_intents": [
            {"player_id": a.player_id, "archetype": a.archetype,
             "arrive_at_min": a.arrive_at_min}
            for a in result.arrival_intents
        ],
        "routing_decisions": result.routing_decisions,
        "seat_events": result.seat_events,
        "sessions": result.sessions,
        "hourly": result.hourly,
        "table_timelines": result.table_timelines,
        "summary": _realized_summary(result),
    }
