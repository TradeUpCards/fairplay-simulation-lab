"""Phase 3 — fit-aware sensitivity sweep (the anti-circularity check).

Sweeps the FitAwareBehaviorPolicy weight (w_pressure = w_fit) across Standard vs
FairPlay-route and reports cohort retained seat-hours, the acceptance funnel, and
table breaks per arm. The point: see *whether and how* fit-aware leaving changes
the routing conclusion. Because table-pressure overlaps the router's predicted
health, a FairPlay edge that only appears at HIGH weight is a mechanism artifact
(predicted-vs-predicted circularity), not evidence — calibration (with real data)
is what would make any edge meaningful. At weight 0 the model is exactly the
default, so that row is the baseline.

Usage (from playsim/, in the venv):
    python analysis/fit_sensitivity_sweep.py --horizon 480 --seeds 42,7,99
    python analysis/fit_sensitivity_sweep.py --horizon 240 --weights 0,0.15,0.3,0.5 --decline
"""

from __future__ import annotations

import argparse
import statistics as st

from playsim.arrivals import build_arrival_intents
from playsim.behavior import FitAwareBehaviorPolicy
from playsim.policies import FairPlayRoutePolicy, StandardPolicy
from playsim.room import run_room
from playsim.room_export import build_canonical
from playsim.router_adapter import RouterAdapter


def _arm(policy, behavior, seed, horizon, equity, tables, intents):
    r = run_room(policy, master_seed=seed, horizon_min=horizon, equity_samples=equity,
                 tables=tables, arrival_intents=intents, behavior=behavior)
    s = build_canonical(r)["summary"]
    return s["vulnerable_paid_seat_hours"], s["funnel"], s["table_breaks"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fit-aware sensitivity sweep")
    ap.add_argument("--horizon", type=float, default=480.0)
    ap.add_argument("--seeds", default="42,7,99")
    ap.add_argument("--equity", type=int, default=6)
    ap.add_argument("--tables", default=None)
    ap.add_argument("--weights", default="0,0.15,0.3,0.5",
                    help="comma w values; w_pressure = w_fit = w")
    ap.add_argument("--decline", action="store_true", help="enable fit-aware decline")
    ap.add_argument("--data-root", default=None)
    args = ap.parse_args(argv)

    seeds = [int(s) for s in args.seeds.split(",")]
    tables = args.tables.split(",") if args.tables else None
    weights = [float(w) for w in args.weights.split(",")]
    adapter = RouterAdapter(args.data_root)

    print(f"horizon={args.horizon:.0f}min  seeds={seeds}  decline={args.decline}\n")
    print(f"{'w(p=f)':>7} {'std_hrs':>8} {'fp_hrs':>8} {'delta':>7} "
          f"{'std_acc':>8} {'fp_acc':>7} {'std_brk':>8} {'fp_brk':>7}")
    for w in weights:
        std_h, fp_h, std_acc, fp_acc, std_brk, fp_brk = ([] for _ in range(6))
        for s in seeds:
            intents = build_arrival_intents(args.horizon, seed=s, root=args.data_root)
            # fresh behavior per arm/seed so the decline RNG is independent
            def beh():
                return FitAwareBehaviorPolicy(w_pressure=w, w_fit=w,
                                              decline_enabled=args.decline, seed=s)
            h, fn, b = _arm(StandardPolicy(), beh(), s, args.horizon, args.equity, tables, intents)
            std_h.append(h); std_acc.append(fn["accepted"]); std_brk.append(b)
            h2, fn2, b2 = _arm(FairPlayRoutePolicy(adapter), beh(), s, args.horizon,
                               args.equity, tables, intents)
            fp_h.append(h2); fp_acc.append(fn2["accepted"]); fp_brk.append(b2)
        m = st.mean
        print(f"{w:>7.2f} {m(std_h):>8.2f} {m(fp_h):>8.2f} {m(fp_h) - m(std_h):>+7.2f} "
              f"{m(std_acc):>8.1f} {m(fp_acc):>7.1f} {m(std_brk):>8.1f} {m(fp_brk):>7.1f}")
    print("\nRead: an FP edge (delta>0) that appears ONLY as w rises is a mechanism "
          "artifact (pressure overlaps router health), not evidence — calibrate before claiming.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
