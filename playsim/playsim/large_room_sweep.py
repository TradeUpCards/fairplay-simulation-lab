"""Large-room room-economics sweep.

This is the first-class harness for the generated 50-table / 1000-player room.
It keeps the old small fixture useful for replay, while making the large-room
shape the default place to evaluate table formation, liveness-aware routing, and
seat-time economics.
"""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path
from typing import Iterable

from .arrivals import build_arrival_intents
from .behavior import make_behavior
from .large_room_fixture import write_large_room_fixture
from .policies import FairPlayLivenessPolicy, FairPlayRoutePolicy, StandardPolicy
from .room import COHORT, RoomSim
from .router_adapter import RouterAdapter

DEFAULT_POLICIES = ("standard", "fairplay", "fairplay_liveness")
RESEEK_EXIT_REASONS = frozenset({
    "table_thinning",
    "table_break",
    "break",
    "bad_fit_decline",
    "boredom_low_action",
})

# Terminal site-departure buckets, keyed off ``session.exit_reason``. These are
# players who *left the room*, not mid-session table relocations (table_break /
# thinning re-seeks stay in the reseek funnel, not here). "Couldn't seat" is the
# acceptance-channel failure (balked / wait-balked) and is counted from the balk
# lists since those players were never seated and so have no session row.
DEPART_SATISFIED = {"profit_taking", "time_budget_complete"}
DEPART_DAMAGED = {"tilt_bleed", "tilt"}


def _has_fixture(root: Path) -> bool:
    return all(
        (root / rel).is_file()
        for rel in (
            "players.json",
            "table_roster.json",
            "relationships.json",
            "devices.json",
            "derived/classifications.json",
        )
    )


def ensure_large_room_fixture(
    root: Path,
    *,
    seed: int,
    players: int,
    tables: int,
    active_tables: int,
    max_seats: int,
    start_fill_min: int,
    start_fill_max: int,
    regenerate: bool = False,
) -> None:
    """Create the generated data root if needed."""
    if regenerate or not _has_fixture(root):
        write_large_room_fixture(
            root,
            seed=seed,
            player_count=players,
            table_count=tables,
            active_table_count=active_tables,
            max_seats=max_seats,
            start_fill_min=start_fill_min,
            start_fill_max=start_fill_max,
        )


def _policy_factory(name: str, adapter: RouterAdapter, live_adapter: RouterAdapter):
    if name == "standard":
        return StandardPolicy()
    if name == "fairplay":
        return FairPlayRoutePolicy(adapter)
    if name in {"fairplay_liveness", "fairplay-live"}:
        return FairPlayLivenessPolicy(live_adapter)
    raise ValueError(f"unknown policy {name!r}")


def _departures(result) -> dict:
    """3-bucket terminal site-departure counts, with a vulnerable-cohort split.

    Satisfied / damaged come from seated players' ``session.exit_reason``;
    couldn't-seat comes from the balk lists (never-seated players have no
    session row). Cohort membership reuses the ``archetype in COHORT`` test that
    every other cohort metric in this file uses, so the split is free.
    """
    arch = result.archetype_of
    satisfied = damaged = c_satisfied = c_damaged = 0
    for s in result.sessions:
        reason = s.get("exit_reason", "")
        in_cohort = s.get("archetype") in COHORT
        if reason in DEPART_SATISFIED:
            satisfied += 1
            c_satisfied += in_cohort
        elif reason in DEPART_DAMAGED:
            damaged += 1
            c_damaged += in_cohort
    never_seated = list(result.balked) + list(result.wait_balked)
    couldnt_seat = len(never_seated)
    c_couldnt = sum(1 for pid in never_seated if arch.get(pid) in COHORT)
    return {
        "left_satisfied_count": satisfied,
        "left_damaged_count": damaged,
        "couldnt_seat_count": couldnt_seat,
        "cohort_left_satisfied_count": c_satisfied,
        "cohort_left_damaged_count": c_damaged,
        "cohort_couldnt_seat_count": c_couldnt,
    }


def _metrics(result, intents) -> dict:
    cohort_players = [p for p, arch in result.archetype_of.items() if arch in COHORT]
    arrival_seated = {
        e["player_id"]
        for e in result.seat_events
        if e.get("origin") == "arrival"
    }
    final_states: dict[str, int] = {}
    for table in result.table_timelines.values():
        state = table["final_state"]
        final_states[state] = final_states.get(state, 0) + 1

    horizon_hours = result.horizon_min / 60.0 if result.horizon_min else 0.0
    non_horizon_sessions = [
        s for s in result.sessions
        if s.get("exit_reason") != "horizon"
    ]
    reseek_departures = [
        s for s in non_horizon_sessions
        if s.get("exit_reason") in RESEEK_EXIT_REASONS
    ]
    terminal_churn = [
        s for s in non_horizon_sessions
        if s.get("exit_reason") not in RESEEK_EXIT_REASONS
    ]
    arrival_count = len(intents)
    arrival_balk_count = sum(
        1 for d in result.routing_decisions
        if d.get("origin") == "arrival" and d.get("table_id") is None
    )
    wait_balk_count = len(result.wait_balked)

    instr = result.instrumentation
    return {
        "total_paid_seat_hours": round(sum(result.seat_minutes.values()) / 60.0, 3),
        "vulnerable_paid_seat_hours": round(
            sum(result.seat_minutes[p] for p in cohort_players) / 60.0, 3
        ),
        "arrival_count": arrival_count,
        "arrival_seated_count": len(arrival_seated),
        "arrival_balk_count": arrival_balk_count,
        "arrival_balk_rate": round(arrival_balk_count / arrival_count, 4) if arrival_count else 0.0,
        "demand_drop_rate": round(
            (arrival_balk_count + wait_balk_count) / arrival_count, 4
        ) if arrival_count else 0.0,
        "seated_departure_count": len(non_horizon_sessions),
        "terminal_churn_count": len(terminal_churn),
        "reseek_departure_count": len(reseek_departures),
        "departure_rate_per_hour": round(
            len(non_horizon_sessions) / horizon_hours, 4
        ) if horizon_hours else 0.0,
        "terminal_churn_rate_per_hour": round(
            len(terminal_churn) / horizon_hours, 4
        ) if horizon_hours else 0.0,
        "reseek_departure_rate_per_hour": round(
            len(reseek_departures) / horizon_hours, 4
        ) if horizon_hours else 0.0,
        "break_count": sum(1 for e in result.seat_events if e.get("event") == "break"),
        "break_balk_count": sum(
            1 for d in result.routing_decisions
            if d.get("origin") == "break_displace" and d.get("table_id") is None
        ),
        "wait_balk_count": wait_balk_count,
        "no_good_existing_seat_count": instr["no_good_existing_seat_count"],
        "empty_table_available_count": instr["empty_table_available_count"],
        "sub_quorum_table_available_count": instr["sub_quorum_table_available_count"],
        "forming_seat_count": instr["forming_seat_count"],
        "formation_activation_count": instr["formation_activation_count"],
        "table_reactivation_count": instr["table_reactivation_count"],
        "final_active_tables": final_states.get("active", 0),
        "final_forming_tables": final_states.get("forming", 0),
        "final_empty_tables": final_states.get("empty", 0) + final_states.get("broken_empty", 0),
        "hands_total": result.hands_total,
        **_departures(result),
    }


def _mean(rows: Iterable[dict], key: str) -> float:
    vals = [float(r[key]) for r in rows]
    return round(st.mean(vals), 3) if vals else 0.0


def summarize_runs(runs: list[dict]) -> list[dict]:
    groups: dict[tuple[float, str], list[dict]] = {}
    for row in runs:
        groups.setdefault((row["arrival_rate_per_hour"], row["policy"]), []).append(row)

    out = []
    metric_keys = [
        "total_paid_seat_hours",
        "vulnerable_paid_seat_hours",
        "arrival_count",
        "arrival_seated_count",
        "arrival_balk_count",
        "arrival_balk_rate",
        "demand_drop_rate",
        "seated_departure_count",
        "terminal_churn_count",
        "reseek_departure_count",
        "departure_rate_per_hour",
        "terminal_churn_rate_per_hour",
        "reseek_departure_rate_per_hour",
        "break_count",
        "break_balk_count",
        "wait_balk_count",
        "no_good_existing_seat_count",
        "forming_seat_count",
        "formation_activation_count",
        "table_reactivation_count",
        "final_active_tables",
        "final_forming_tables",
        "final_empty_tables",
        "left_satisfied_count",
        "left_damaged_count",
        "couldnt_seat_count",
        "cohort_left_satisfied_count",
        "cohort_left_damaged_count",
        "cohort_couldnt_seat_count",
    ]
    for (rate, policy), rows in sorted(groups.items()):
        item = {
            "arrival_rate_per_hour": rate,
            "policy": policy,
            "seeds": [r["seed"] for r in rows],
        }
        item.update({f"{key}_mean": _mean(rows, key) for key in metric_keys})
        out.append(item)
    return out


def run_large_room_sweep(
    *,
    data_root: Path,
    fixture_seed: int = 42,
    seeds: list[int] | None = None,
    arrival_rates_per_hour: list[float] | None = None,
    horizon_min: float = 480.0,
    equity_samples: int = 1,
    sample_interval_min: float = 20.0,
    policies: tuple[str, ...] = DEFAULT_POLICIES,
    behavior: str = "formation-aware",
    arrival_mode: str = "continuous",
    formation_mode: str = "forming",
    players: int = 1000,
    tables: int = 50,
    active_tables: int = 35,
    max_seats: int = 6,
    start_fill_min: int = 4,
    start_fill_max: int = 6,
    regenerate_fixture: bool = False,
) -> dict:
    """Run a deterministic large-room comparison over seeds/rates/policies."""
    if arrival_mode != "continuous":
        raise ValueError("large-room economics sweep expects arrival_mode='continuous'")
    seeds = seeds or [42, 7, 99]
    arrival_rates_per_hour = arrival_rates_per_hour or [40.0]

    ensure_large_room_fixture(
        data_root,
        seed=fixture_seed,
        players=players,
        tables=tables,
        active_tables=active_tables,
        max_seats=max_seats,
        start_fill_min=start_fill_min,
        start_fill_max=start_fill_max,
        regenerate=regenerate_fixture,
    )

    adapter = RouterAdapter(data_root)
    live_adapter = RouterAdapter(data_root, liveness_aware=True)
    runs: list[dict] = []

    for rate in arrival_rates_per_hour:
        for seed in seeds:
            intents = build_arrival_intents(
                horizon_min,
                seed=seed,
                root=data_root,
                mode=arrival_mode,
                arrival_rate_per_hour=rate,
            )
            for policy_name in policies:
                policy = _policy_factory(policy_name, adapter, live_adapter)
                result = RoomSim(
                    policy,
                    root=data_root,
                    master_seed=seed,
                    horizon_min=horizon_min,
                    equity_samples=equity_samples,
                    arrival_intents=intents,
                    arrival_mode=arrival_mode,
                    arrival_rate_per_hour=rate,
                    formation_mode=formation_mode,
                    sample_interval_min=sample_interval_min,
                    behavior=make_behavior(behavior, seed=seed),
                ).run()
                runs.append({
                    "seed": seed,
                    "arrival_rate_per_hour": float(rate),
                    "policy": policy_name,
                    "tables": tables,
                    **_metrics(result, intents),
                    # per-interval cumulative trace for the animated dashboard hero.
                    # Ignored by the sweep-explorer (it slims runs to summary keys).
                    "series": result.samples,
                })

    return {
        "meta": {
            "fixture": "playsim-large-room",
            "data_root": str(data_root),
            "fixture_seed": fixture_seed,
            "players": players,
            "tables": tables,
            "active_tables": active_tables,
            "horizon_min": horizon_min,
            "equity_samples": equity_samples,
            "sample_interval_min": sample_interval_min,
            "arrival_mode": arrival_mode,
            "arrival_rates_per_hour": arrival_rates_per_hour,
            "formation_mode": formation_mode,
            "behavior": behavior,
            "policies": list(policies),
            "deterministic": True,
            "note": (
                "Large-room economics outputs are illustrative until calibrated "
                "against real room traffic and behavior."
            ),
        },
        "runs": runs,
        "summary": summarize_runs(runs),
    }


def render_markdown_report(payload: dict) -> str:
    """Render a compact teammate-facing report from a sweep payload."""
    meta = payload["meta"]
    lines = [
        "# Playsim large-room economics sweep",
        "",
        f"Fixture: {meta['tables']} tables, {meta['active_tables']} active at hour 0, "
        f"{meta['players']} players.",
        f"Run: {meta['horizon_min']:.0f} min, arrivals={meta['arrival_mode']}, "
        f"formation={meta['formation_mode']}, behavior={meta['behavior']}.",
        "",
        "North star: total paid seat-hours across all users and tables. "
        "Vulnerable paid seat-hours remains the FairPlay cohort check.",
        "",
        "| arrival/hr | policy | total seat-hrs | vulnerable seat-hrs | arrivals seated | demand drop | departures/hr | non-reseat exits/hr | breaks | wait balks | forming seats | activations | final active |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]:
        lines.append(
            f"| {row['arrival_rate_per_hour']:.1f} | {row['policy']} | "
            f"{row['total_paid_seat_hours_mean']:.2f} | "
            f"{row['vulnerable_paid_seat_hours_mean']:.2f} | "
            f"{row['arrival_seated_count_mean']:.1f} | "
            f"{row['demand_drop_rate_mean']:.1%} | "
            f"{row['departure_rate_per_hour_mean']:.2f} | "
            f"{row['terminal_churn_rate_per_hour_mean']:.2f} | "
            f"{row['break_count_mean']:.1f} | "
            f"{row['wait_balk_count_mean']:.1f} | "
            f"{row['forming_seat_count_mean']:.1f} | "
            f"{row['formation_activation_count_mean']:.1f} | "
            f"{row['final_active_tables_mean']:.1f} |"
        )
    lines.extend([
        "",
        "Interpretation rule: prefer mechanism-first reads. A FairPlay-liveness win "
        "should come with fewer no-good-seat moments, healthier formation activation, "
        "or fewer break/wait failures, not only more aggregate seat-time.",
        "",
    ])
    return "\n".join(lines)


def write_sweep_outputs(payload: dict, *, json_path: Path | None, markdown_path: Path | None) -> None:
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if markdown_path:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown_report(payload), encoding="utf-8")
