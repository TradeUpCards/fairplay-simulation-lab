"""N-way room routing comparison harness (analysis / reproducibility).

Runs the closed-loop room simulator under several seating policies over a shared,
seeded arrival stream and reports cohort paid seat-time plus churn instrumentation
(table breaks, break-displacement balks). This is the script behind
``docs/learn/playsim-room-routing-findings.md``.

Usage (from the playsim/ dir, in the venv):

    python analysis/room_policy_comparison.py --horizon 240 --seeds 42,7,99
    python analysis/room_policy_comparison.py --horizon 480 --seeds 42,7,99

Notes:
- Standard (most-full) and Random never call the backend. FairPlay-route and
  FairPlay-balanced route via the real backend scoring/router at decision time.
- The directional outcome is an empirical result of this synthetic model, not a
  universal claim — see the findings doc for caveats.
"""

from __future__ import annotations

import argparse
import statistics as st

from playsim.arrivals import build_arrival_intents
from playsim.behavior import make_behavior
from playsim.policies import (
    FairPlayBalancedPolicy,
    FairPlayLivenessPolicy,
    FairPlayRoutePolicy,
    RandomPolicy,
    StandardPolicy,
)
from playsim.room import COHORT, RoomSim
from playsim.router_adapter import RouterAdapter

METRICS = (
    "seat_hrs", "arr_surv", "breaks", "break_balks", "arr_balks",
    "wait_balks", "no_good_seat", "forming_seats", "form_activations",
)


def _run(policy, seed, horizon, equity, tables, intents, behavior, formation_mode):
    r = RoomSim(policy, master_seed=seed, horizon_min=horizon,
                equity_samples=equity, tables=tables, arrival_intents=intents,
                behavior=make_behavior(behavior, seed=seed),
                formation_mode=formation_mode).run()
    vuln = {a.player_id for a in intents if a.archetype in COHORT}
    arr_seated = {e["player_id"] for e in r.seat_events
                  if e.get("origin") == "arrival" and e["player_id"] in vuln}
    cohort = [p for p in r.archetype_of if r.archetype_of[p] in COHORT]
    return {
        "seat_hrs": sum(r.seat_minutes[p] for p in cohort) / 60.0,
        "arr_surv": st.mean([r.seat_minutes[p] for p in arr_seated]) if arr_seated else 0.0,
        "breaks": sum(1 for e in r.seat_events if e.get("event") == "break"),
        "break_balks": sum(1 for d in r.routing_decisions
                           if d.get("origin") == "break_displace" and d["table_id"] is None),
        "arr_balks": sum(1 for d in r.routing_decisions
                         if d.get("origin") == "arrival" and d["table_id"] is None
                         and d["archetype"] in COHORT),
        "wait_balks": len(r.wait_balked),
        "no_good_seat": r.instrumentation["no_good_existing_seat_count"],
        "forming_seats": r.instrumentation["forming_seat_count"],
        "form_activations": r.instrumentation["formation_activation_count"],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="N-way room routing comparison")
    ap.add_argument("--horizon", type=float, default=480.0, help="minutes (480 = 8h)")
    ap.add_argument("--seeds", default="42,7,99", help="comma-separated seed set")
    ap.add_argument("--equity", type=int, default=6, help="Monte-Carlo equity samples")
    ap.add_argument("--tables", default=None, help="comma table ids (default: all)")
    ap.add_argument("--behavior", choices=["default", "fit-aware", "reason-aware", "formation-aware"],
                    default="default")
    ap.add_argument("--arrival-mode", choices=["fixture-once", "continuous"],
                    default="fixture-once")
    ap.add_argument("--arrival-rate-per-hour", type=float,
                    help="continuous-arrival rate; defaults to fixture pool size over horizon")
    ap.add_argument("--formation-mode", choices=["none", "forming"], default="none")
    ap.add_argument("--data-root", default=None)
    args = ap.parse_args(argv)

    seeds = [int(s) for s in args.seeds.split(",")]
    tables = args.tables.split(",") if args.tables else None
    adapter = RouterAdapter(args.data_root)
    liveness_adapter = RouterAdapter(args.data_root, liveness_aware=True)

    factories = {
        "random       ": lambda s: RandomPolicy(seed=s),
        "most-full    ": lambda s: StandardPolicy(),
        "fairplay     ": lambda s: FairPlayRoutePolicy(adapter),
        "fairplay-live": lambda s: FairPlayLivenessPolicy(liveness_adapter),
        "fairplay-bal ": lambda s: FairPlayBalancedPolicy(adapter, health_floor=50.0),
    }
    agg = {k: {m: [] for m in METRICS} for k in factories}

    for seed in seeds:
        intents = build_arrival_intents(
            args.horizon, seed=seed, root=args.data_root,
            mode=args.arrival_mode,
            arrival_rate_per_hour=args.arrival_rate_per_hour,
        )
        for name, fac in factories.items():
            res = _run(fac(seed), seed, args.horizon, args.equity, tables, intents,
                       args.behavior, args.formation_mode)
            for m in METRICS:
                agg[name][m].append(res[m])
            print(f"seed={seed} {name}: seat_hrs={res['seat_hrs']:.2f} "
                  f"arr_surv={res['arr_surv']:.1f}m breaks={res['breaks']} "
                  f"break_balks={res['break_balks']} wait_balks={res['wait_balks']} "
                  f"no_good_seat={res['no_good_seat']} "
                  f"forming_seats={res['forming_seats']} "
                  f"form_activations={res['form_activations']}", flush=True)

    print(
        f"\n=== MEANS over {seeds} (horizon {args.horizon:.0f}min, "
        f"behavior={args.behavior}, arrivals={args.arrival_mode}, "
        f"formation={args.formation_mode}) ==="
    )
    print(
        f"{'policy':13} {'seat_hrs':>9} {'arr_surv':>9} {'breaks':>7} "
        f"{'brk_balks':>10} {'wait_balks':>10} {'no_good':>9} "
        f"{'forming':>8} {'active':>7}"
    )
    for name in factories:
        a = agg[name]
        print(f"{name:13} {st.mean(a['seat_hrs']):>9.2f} {st.mean(a['arr_surv']):>9.1f} "
              f"{st.mean(a['breaks']):>7.1f} {st.mean(a['break_balks']):>10.1f} "
              f"{st.mean(a['wait_balks']):>10.1f} {st.mean(a['no_good_seat']):>9.1f} "
              f"{st.mean(a['forming_seats']):>8.1f} {st.mean(a['form_activations']):>7.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
