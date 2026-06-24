"""The integration surface for a UI / API layer.

One function, ``simulate(...)``, returns a JSON-serializable dict — everything a
frontend or HTTP endpoint needs, with no PokerKit/dataclass objects leaking out.
This is the seam: a UI calls this (directly in-process, or behind a thin
FastAPI/Flask route), or a batch job calls it and commits the JSON as a *frozen*
fixture the UI reads statically (the determinism-friendly default).

    from playsim.service import simulate
    simulate("case_c", hands=500, seed=42)            # integrity-loop view
    simulate("routing_standard", hands=600, persist=True)   # + health
    simulate_routing(hands=600, seed=42)              # Standard-vs-FairPlay ΔHealth
"""

from __future__ import annotations

from .health import compare_routing, compute_health
from .phh import session_to_phh
from .rosters import TABLES, get_roster
from .runner import run_session


def _features_view(result) -> list[dict]:
    rows = []
    for r in result.realized_vs_target():
        rows.append({
            "player_id": r["player_id"],
            "archetype": r["archetype"],
            "vpip": r["vpip"][0], "vpip_target": r["vpip"][1],
            "pfr": r["pfr"][0], "pfr_target": r["pfr"][1],
            "aggression_factor": r["aggression_factor"][0],
            "aggression_factor_target": r["aggression_factor"][1],
            "avg_pot_bb": r["avg_pot_bb"][0],
            "timing_regularity": r["timing_regularity"],
            "soft_play_delta": r["soft_play_delta"],
            "net_bb": r["net_bb"],
        })
    return rows


def simulate(
    table: str,
    hands: int = 500,
    seed: int = 42,
    samples: int = 24,
    persist: bool = False,
    include_phh: bool = False,
) -> dict:
    """Run one table and return a JSON-serializable result for a UI/API."""
    roster = get_roster(table)
    result = run_session(
        roster, hands, seed=seed, equity_samples=samples,
        label=table, persist_stacks=persist,
    )
    out: dict = {
        "meta": {
            "table": table, "hands": hands, "seed": seed, "samples": samples,
            "persist_stacks": persist, "n_players": len(roster),
            "deterministic": True,
        },
        "players": [
            {"player_id": p.player_id, "archetype": p.archetype,
             "cluster_id": p.cluster_id, "household_id": p.household_id}
            for p in roster
        ],
        # Contract-1 features the scoring engine consumes:
        "features": result.features,
        # realized-vs-target view for a calibration/health panel:
        "calibration": _features_view(result),
    }
    if persist:
        out["health"] = compute_health(result)
        out["final_stacks_bb"] = result.final_stacks_bb
        out["busts"] = result.busts
    if include_phh:
        out["phh"] = session_to_phh(result.hands)
    return out


def simulate_routing(
    hands: int = 350, seed: int = 42, samples: int = 12,
    seeds: int = 12, stack_bb: int = 40, skill_edge: float = 1.6,
) -> dict:
    """Standard-vs-FairPlay counterfactual, **averaged over ``seeds`` runs**.

    Headline = retained **paid seat-time** (the north star); ΔHealth is the
    driver; rec-loss/concentration are the "why". A poker sim is noisy per-seed
    (individual fish run hot/cold), so we Monte-Carlo over seeds for a stable
    population-level number — exactly the *average* effect FairPlay claims.

    ``skill_edge`` applies the per-hand skill-EV transfer (see ``runner``); it's
    what makes the predation→decay signal reliable with heuristic agents. Set 0
    for pure-emergent play (then the signal is buried in variance).
    """
    runs = []
    for s in range(seed, seed + seeds):
        std = run_session(get_roster("routing_standard"), hands, seed=s,
                          equity_samples=samples, label="standard", retention=True,
                          starting_stack_bb=stack_bb, skill_edge=skill_edge)
        fp = run_session(get_roster("routing_fairplay"), hands, seed=s,
                         equity_samples=samples, label="fairplay", retention=True,
                         starting_stack_bb=stack_bb, skill_edge=skill_edge)
        runs.append(compare_routing(std, fp))

    def avg(path):
        vals = []
        for r in runs:
            v = r
            for key in path:
                v = v[key]
            vals.append(v)
        return round(sum(vals) / len(vals), 2)

    std_h, fp_h = avg(["standard", "health_score"]), avg(["fairplay", "health_score"])
    std_ps = avg(["paid_seat_time", "standard_hours"])
    fp_ps = avg(["paid_seat_time", "fairplay_hours"])
    return {
        "meta": {"horizon_hands": hands, "seeds": list(range(seed, seed + seeds)),
                 "samples": samples, "stack_bb": stack_bb},
        "paid_seat_time": {
            "standard_hours": std_ps, "fairplay_hours": fp_ps,
            "delta_hours": round(fp_ps - std_ps, 2),
            "delta_pct": round((fp_ps - std_ps) / std_ps * 100, 1) if std_ps else 0.0,
        },
        "avg_casual_session_min": {
            "standard": avg(["avg_casual_session_min", "standard"]),
            "fairplay": avg(["avg_casual_session_min", "fairplay"]),
        },
        "retention_rate": {
            "standard": avg(["retention_rate", "standard"]),
            "fairplay": avg(["retention_rate", "fairplay"]),
        },
        "early_exits": {
            "standard": avg(["early_exits", "standard"]),
            "fairplay": avg(["early_exits", "fairplay"]),
        },
        "health": {
            "standard": std_h, "fairplay": fp_h,
            "delta": round(fp_h - std_h, 1),
        },
        "rec_loss_velocity": {
            "standard": avg(["standard", "recreational_loss_velocity_bb_per_100"]),
            "fairplay": avg(["fairplay", "recreational_loss_velocity_bb_per_100"]),
        },
    }


def list_tables() -> list[str]:
    return sorted(TABLES)


def simulate_room(
    *,
    root=None,
    seed: int = 42,
    seeds: list[int] | None = None,
    horizon_min: float = 480.0,
    equity_samples: int = 20,
    tables: list[str] | None = None,
    protect: bool = False,
    protect_threshold: float = 50.0,
    debug_trace: bool = False,
    data_root_str: str = "",
) -> dict:
    """Run the closed-loop room A/B and return JSON-serializable results.

    Standard (most-full) vs FairPlay-route (backend router) over an identical,
    seeded, policy-independent arrival stream. The headline directional metric
    (vulnerable paid seat-time) is **averaged over a seed set** — single-seed
    variance is expected. Canonical ``room_sim_*`` outputs use the first seed.

    Returns ``{standard, fairplay, room_metrics_standard, room_metrics_fairplay,
    comparison[, fairplay_protect]}``. Realized health stays evaluation-only;
    routing uses backend predicted health via the adapter.
    """
    from .arrivals import build_arrival_intents
    from .policies import FairPlayProtectPolicy, FairPlayRoutePolicy, StandardPolicy
    from .room import run_room
    from .room_export import build_canonical, derive_room_metrics
    from .router_adapter import RouterAdapter

    adapter = RouterAdapter(root)
    seed_list = list(seeds) if seeds else [seed]

    std_hours: list[float] = []
    fp_hours: list[float] = []
    canon_std = canon_fp = canon_protect = None

    for i, s in enumerate(seed_list):
        intents = build_arrival_intents(horizon_min, seed=s, root=root)
        common = dict(root=root, master_seed=s, horizon_min=horizon_min,
                      equity_samples=equity_samples, tables=tables,
                      arrival_intents=intents, debug_trace=debug_trace)
        std = run_room(StandardPolicy(), **common)
        fp = run_room(FairPlayRoutePolicy(adapter), **common)
        cstd = build_canonical(std, data_root=data_root_str)
        cfp = build_canonical(fp, data_root=data_root_str)
        std_hours.append(cstd["summary"]["vulnerable_paid_seat_hours"])
        fp_hours.append(cfp["summary"]["vulnerable_paid_seat_hours"])
        if i == 0:
            canon_std, canon_fp = cstd, cfp
            if protect:
                pr = run_room(
                    FairPlayProtectPolicy(adapter, enabled=True,
                                          safety_threshold=protect_threshold),
                    **common)
                canon_protect = build_canonical(pr, data_root=data_root_str)

    n = len(seed_list)
    std_mean = sum(std_hours) / n
    fp_mean = sum(fp_hours) / n
    comparison = {
        "metric": "vulnerable_paid_seat_hours",
        "seeds": seed_list,
        "standard_mean": round(std_mean, 3),
        "fairplay_route_mean": round(fp_mean, 3),
        "delta_hours": round(fp_mean - std_mean, 3),
        "delta_pct": round((fp_mean - std_mean) / std_mean * 100, 1) if std_mean > 0 else 0.0,
        "routing_helped": fp_mean >= std_mean,
        "per_seed": {"standard": std_hours, "fairplay_route": fp_hours},
    }

    out = {
        "standard": canon_std,
        "fairplay": canon_fp,
        "room_metrics_standard": derive_room_metrics(canon_std),
        "room_metrics_fairplay": derive_room_metrics(canon_fp),
        "comparison": comparison,
    }
    if protect:
        out["fairplay_protect"] = canon_protect
    return out
