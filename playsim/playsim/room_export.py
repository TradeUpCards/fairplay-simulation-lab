"""Canonical room_sim output builder (+ derived v1 room_metrics adapter in U7).

``build_canonical`` is the **source of truth**: a playsim-native dict carrying the
full causal trace (meta, run_config, arrival_intents, routing_decisions,
seat_events, sessions, hourly timeline, table_timelines) plus summary metrics.
The realized summary mirrors ``playsim/health.py``'s first-principles chip-flow
formulas — it is **evaluation-only** and is computed here, downstream of routing,
never fed back into a seating decision.
"""

from __future__ import annotations

from .health import realized_health_score
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

    # Realized health — shared kernel with playsim/health.compute_health (single
    # source). Independent of the backend predicted health used for routing; this
    # is the evaluation side.
    score, band = realized_health_score(rec_loss_velocity, winnings_concentration, bust_rate)

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
        "declined_count": len(result.declined),
        "prevented_bad_sessions": len(result.deferred),
        # ── cohort acceptance funnel (separates the acceptance channel from the
        #    retention channel; offered = accepted + declined + balked + deferred) ──
        "funnel": _cohort_funnel(result),
    }


def _cohort_funnel(result: RoomResult) -> dict:
    """Per-arm acceptance funnel for vulnerable-cohort *arrivals*: offered ->
    accepted / declined / balked / deferred. Lets a routing win be attributed to
    the acceptance channel vs the retention channel rather than conflated."""
    arr = [d for d in result.routing_decisions
           if d.get("origin") == "arrival" and d.get("archetype") in COHORT]
    accepted = sum(1 for d in arr if d["table_id"] is not None)
    declined = sum(1 for d in arr if d.get("reason") == "declined")
    deferred = sum(1 for d in arr if d.get("deferred"))
    balked = sum(1 for d in arr if d["table_id"] is None
                 and d.get("reason") in ("no_open_seat", "no_dealable_seat"))
    return {"offered": len(arr), "accepted": accepted, "declined": declined,
            "balked": balked, "deferred": deferred}


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


def derive_room_metrics(canonical: dict) -> dict:
    """Derive the v1 ``room_metrics_*`` shape (``{meta, hours}``) from the canonical
    room_sim dict. Pure function of ``canonical`` — no fixture/file reads. This is a
    temporary compatibility view for the existing frontend; the canonical output is
    the source of truth. ``reward_fee_ratio`` is not modeled in the MVP.
    """
    rc = canonical["run_config"]
    horizon_hours = int(round(rc["horizon_min"] / 60.0)) or 1
    path = "standard" if rc["policy"] == "standard" else "fairplay"

    hours = []
    for hr in canonical["hourly"]:
        h = hr["hour"]
        cum = int(round(hr["cumulative_paid_seat_min"]))
        projected = int(round(cum / h * horizon_hours)) if h else cum
        hours.append({
            "hour": h,
            "cumulative_paid_seat_time_minutes": cum,
            "active_players": hr["active_players"],
            "active_healthy_tables": hr["active_healthy_tables"],
            "new_player_retention_pct": hr["cohort_retention_pct"],
            "avg_casual_session_length_minutes": hr["avg_casual_session_min"],
            "early_table_breaks": hr["early_table_breaks"],
            "projected_eod_paid_seat_time_minutes": projected,
            "reward_fee_ratio": 0.0,   # not modeled in MVP
            "high_risk_seating_formations": hr["high_risk_formations"],
            "hour_note": (f"Hour {h}: {hr['active_players']} active players, "
                          f"{hr['active_healthy_tables']} healthy tables, "
                          f"{hr['cohort_retention_pct']}% cohort retention."),
        })

    meta = {
        "schema_version": "0.2.0-derived",
        "path": path,
        "generated": "playsim-room-sim",
        "derived_from": "room_sim canonical output",
        "horizon_hours": horizon_hours,
        "master_seed": rc["master_seed"],
        "policy": rc["policy"],
        "agent_model": canonical["meta"]["agent_model"],
        "fixture_note": canonical["meta"]["fixture_note"],
        "note": ("Derived compatibility view for the v1 frontend; the room_sim "
                 "canonical output is the source of truth. reward_fee_ratio is not "
                 "modeled in the MVP."),
    }
    return {"meta": meta, "hours": hours}
