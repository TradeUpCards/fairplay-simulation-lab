"""playsim command line — stand up a table, replay it, inspect calibration.

    python -m playsim.cli tables
    python -m playsim.cli run --table case_c --hands 500 --seed 42 --db out/sim.db
    python -m playsim.cli run --table healthy_mix --hands 800 --phh out/hands.json
    python -m playsim.cli replay --table case_c --hands 500 --seed 42   # verify determinism
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

from .knobs import knobs_for
from .rosters import TABLES, get_roster
from .runner import run_session


def _write_json(path: str, payload, *, compact: bool = False) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(payload, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(payload, indent=2) + "\n"
    if out.suffix == ".gz":
        with gzip.open(out, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        out.write_text(text, encoding="utf-8")


def _print_report(result) -> None:
    print(f"\n  table: {result.label}   seed: {result.seed}   hands: {result.n_hands}\n")
    head = f"  {'player':>7}  {'archetype':22} {'vpip(r/t)':13} {'pfr(r/t)':13} {'AF(r/t)':13} {'timing':6} {'soft':6} {'net_bb':>8}"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for row in result.realized_vs_target():
        v, p, a = row["vpip"], row["pfr"], row["aggression_factor"]
        print(
            f"  {row['player_id']:>7}  {row['archetype']:22} "
            f"{v[0]:.2f}/{v[1]:.2f}   {p[0]:.2f}/{p[1]:.2f}   {a[0]:.2f}/{a[1]:.2f}   "
            f"{row['timing_regularity']:.2f}   {row['soft_play_delta']:+.2f}  {row['net_bb']:>+8.1f}"
        )
    print("\n  (r/t = realized / archetype target. vpip·pfr·timing·soft-play")
    print("   are emergent; AF is the active calibration knob — see README.)\n")


def _run(args) -> int:
    roster = get_roster(args.table)
    result = run_session(
        roster, args.hands, seed=args.seed,
        equity_samples=args.samples, label=args.table,
    )
    _print_report(result)

    if args.db:
        from .store import save_result
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
        run_id = save_result(result, args.db, created_at=0.0)
        print(f"  stored run_id={run_id} in {args.db}")
    if args.phh:
        from .phh import session_to_phh
        Path(args.phh).parent.mkdir(parents=True, exist_ok=True)
        Path(args.phh).write_text(json.dumps(session_to_phh(result.hands), indent=2))
        print(f"  wrote {len(result.hands)} PHH-shaped hands to {args.phh}")
    if args.features:
        Path(args.features).parent.mkdir(parents=True, exist_ok=True)
        Path(args.features).write_text(json.dumps(result.features, indent=2))
        print(f"  wrote player features to {args.features}")
    return 0


def _replay(args) -> int:
    roster = get_roster(args.table)
    a = run_session(roster, args.hands, seed=args.seed, equity_samples=args.samples)
    b = run_session(roster, args.hands, seed=args.seed, equity_samples=args.samples)
    identical = (
        a.features == b.features
        and [h.payoffs for h in a.hands] == [h.payoffs for h in b.hands]
    )
    print(f"  replay {args.table} seed={args.seed} hands={args.hands}: "
          f"{'IDENTICAL ✓ (deterministic)' if identical else 'MISMATCH ✗'}")
    return 0 if identical else 1


def _calibrate(args) -> int:
    from .calibrate import calibration_report, run_calibration
    run_calibration(rounds=args.rounds, hands=args.hands, seed=args.seed,
                    samples=args.samples)
    print(f"\n  {'archetype':24} {'realized':>9} {'target':>7} {'knob':>6}")
    print("  " + "-" * 50)
    for r in calibration_report():
        print(f"  {r['archetype']:24} {r['realized_af']:>9.2f} {r['target_af']:>7.2f}"
              f" {r['postflop_aggression']:>6.3f}")
    print("\n  (written to playsim/calibration.json; overlaid on knob defaults)\n")
    return 0


def _health(args) -> int:
    from .health import compute_health
    roster = get_roster(args.table)
    result = run_session(roster, args.hands, seed=args.seed,
                         equity_samples=args.samples, label=args.table,
                         persist_stacks=True)
    h = compute_health(result)
    print(f"\n  table: {args.table}   seed: {args.seed}   hands: {args.hands}  "
          f"(persistent stacks)\n")
    print(f"  health_score      {h['health_score']:6.1f}   band: {h['band']}")
    print(f"  rec loss velocity {h['recreational_loss_velocity_bb_per_100']:6.1f} bb/100 hands")
    print(f"  winnings concentr {h['winnings_concentration']:6.3f}   (top winner's share)")
    print(f"  beginner busts    {h['beginner_bust_rate_per_100']:6.2f} /100 hands")
    print(f"  predation         {h['predation_bb_per_100']:6.1f} bb/100 hands\n")
    return 0


def _routing(args) -> int:
    from .service import simulate_routing
    c = simulate_routing(hands=args.hands, seed=args.seed, samples=args.samples,
                         seeds=args.seeds)
    pst, sess, ret, ex, h, rl = (c["paid_seat_time"], c["avg_casual_session_min"],
                                 c["retention_rate"], c["early_exits"], c["health"],
                                 c["rec_loss_velocity"])
    print(f"\n  Standard vs FairPlay routing   (same cohort, {args.seeds} seeds avg, "
          f"≤{args.hands}-hand horizon)\n")
    print(f"  {'':30} {'Standard':>10} {'FairPlay':>10}")
    print("  " + "─" * 52)
    print(f"  {'★ Paid seat-hours (cohort)':30} {pst['standard_hours']:>10.2f} {pst['fairplay_hours']:>10.2f}")
    print(f"  {'  Avg casual session (min)':30} {sess['standard']:>10.1f} {sess['fairplay']:>10.1f}")
    print(f"  {'  New/rec retention (end)':30} {ret['standard']*100:>9.0f}% {ret['fairplay']*100:>9.0f}%")
    print(f"  {'  Early exits (<30 min)':30} {ex['standard']:>10.1f} {ex['fairplay']:>10.1f}")
    print("  " + "·" * 52)
    print(f"  {'Health score':30} {h['standard']:>10.1f} {h['fairplay']:>10.1f}")
    print(f"  {'  Rec loss velocity (bb/100)':30} {rl['standard']:>10.1f} {rl['fairplay']:>10.1f}")
    print(f"\n  ▶ Paid seat-time retained: {pst['delta_hours']:+.2f} hrs ({pst['delta_pct']:+.0f}%)"
          f"   ·   ΔHealth {h['delta']:+.1f}")
    print(f"  → better routing → less play-decay → "
          f"{'MORE retained paid seat-time ✓' if pst['delta_hours'] > 0 else 'no gain ✗'}\n")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(c, indent=2) + "\n")
        print(f"  wrote routing backtest to {args.json}\n")
    return 0


def _population(args) -> int:
    from .population_run import run_population

    out = run_population(
        data_root=args.data_root,
        master_seed=args.seed,
        cap=args.cap,
        equity_samples=args.samples,
        table_ids=args.tables.split(",") if args.tables else None,
    )
    meta = out["meta"]
    print(
        f"\n  population run   seed={meta['master_seed']}   cap={meta['cap']}   "
        f"tables={meta['tables_simulated']}   hands={meta['total_hands']}\n"
    )
    if meta.get("skipped_seats"):
        print(f"  skipped seats (missing player/classification): {len(meta['skipped_seats'])}")
    _write_json(args.out, out, compact=args.compact)
    print(f"  wrote {args.out}\n")
    if args.features:
        feat = {"meta": {**meta, "artifact": "sim_player_features"}, "features": out["features"]}
        _write_json(args.features, feat, compact=args.compact)
        print(f"  wrote {args.features}\n")
    return 0


def _room_sim(args) -> int:
    from .service import simulate_room

    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else None
    res = simulate_room(
        root=args.data_root, seed=args.seed, seeds=seeds,
        horizon_min=args.horizon, equity_samples=args.samples,
        tables=args.tables.split(",") if args.tables else None,
        protect=args.protect, protect_threshold=args.protect_threshold,
        behavior_name=args.behavior,
        debug_trace=args.debug_trace,
        data_root_str=str(args.data_root or ""),
    )
    c = res["comparison"]
    print(
        f"\n  room-sim   seeds={c['seeds']}   horizon={args.horizon}min\n"
        f"  vulnerable paid seat-hours (mean):  "
        f"standard={c['standard_mean']}   fairplay_route={c['fairplay_route_mean']}\n"
        f"  Δ {c['delta_hours']} hrs ({c['delta_pct']}%)   "
        f"routing_helped={c['routing_helped']}\n"
    )
    out_dir = Path(args.out_dir)
    suffix = ".json.gz" if args.gzip else ".json"

    def w(name: str, payload) -> None:
        path = str(out_dir / (name + suffix))
        _write_json(path, payload, compact=args.compact)
        print(f"  wrote {path}")

    w("room_sim_standard", res["standard"])
    w("room_sim_fairplay", res["fairplay"])
    w("room_metrics_standard", res["room_metrics_standard"])
    w("room_metrics_fairplay", res["room_metrics_fairplay"])
    if args.protect and res.get("fairplay_protect"):
        w("room_sim_fairplay_protect", res["fairplay_protect"])
    print()
    return 0


def _tables(args) -> int:
    print("\n  available tables:")
    for name, builder in TABLES.items():
        roster = builder()
        kinds = ", ".join(sorted({p.archetype for p in roster}))
        print(f"    {name:14} {len(roster)} seats — {kinds}")
    print("\n  archetypes:", ", ".join(knobs_for.__globals__["ARCHETYPES"]))
    print()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="playsim", description="FairPlay play-simulation engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="play a table and report calibration")
    r.add_argument("--table", default="healthy_mix")
    r.add_argument("--hands", type=int, default=500)
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--samples", type=int, default=24, help="Monte-Carlo equity samples")
    r.add_argument("--db", help="SQLite path to persist the run")
    r.add_argument("--phh", help="write PHH-shaped hand histories to this JSON path")
    r.add_argument("--features", help="write Contract-1 player features to this JSON path")
    r.set_defaults(fn=_run)

    rp = sub.add_parser("replay", help="re-run a seed twice and verify it is identical")
    rp.add_argument("--table", default="healthy_mix")
    rp.add_argument("--hands", type=int, default=500)
    rp.add_argument("--seed", type=int, default=42)
    rp.add_argument("--samples", type=int, default=24)
    rp.set_defaults(fn=_replay)

    c = sub.add_parser("calibrate", help="tune postflop_aggression until realized AF ≈ target")
    c.add_argument("--rounds", type=int, default=8)
    c.add_argument("--hands", type=int, default=500)
    c.add_argument("--seed", type=int, default=1234)
    c.add_argument("--samples", type=int, default=18)
    c.set_defaults(fn=_calibrate)

    he = sub.add_parser("health", help="play a table out (persistent stacks) and score its health")
    he.add_argument("--table", default="routing_standard")
    he.add_argument("--hands", type=int, default=600)
    he.add_argument("--seed", type=int, default=42)
    he.add_argument("--samples", type=int, default=24)
    he.set_defaults(fn=_health)

    ro = sub.add_parser("routing", help="Standard-vs-FairPlay: paid seat-time retained (north star)")
    ro.add_argument("--hands", type=int, default=400, help="max horizon (players leave sooner)")
    ro.add_argument("--seed", type=int, default=42, help="first seed (averages over --seeds)")
    ro.add_argument("--seeds", type=int, default=6, help="number of seeds to average")
    ro.add_argument("--samples", type=int, default=14)
    ro.add_argument("--json", help="write full routing backtest JSON to this path")
    ro.set_defaults(fn=_routing)

    pop = sub.add_parser(
        "population",
        help="simulate data/players.json rosters (table_roster.json) → playsim-native hand JSON",
    )
    pop.add_argument(
        "--data-root",
        help="repo root containing data/ (default: auto-detect or PLAYSIM_DATA_ROOT)",
    )
    pop.add_argument("--seed", type=int, default=42)
    pop.add_argument("--cap", type=int, default=400, help="max hands per player (min with lifetime_hands)")
    pop.add_argument("--samples", type=int, default=20, help="Monte-Carlo equity samples")
    pop.add_argument("--tables", help="comma-separated table ids (default: all in table_roster.json)")
    pop.add_argument("--out", required=True, help="write playsim_hand_histories JSON here")
    pop.add_argument("--features", help="optional sim_player_features sidecar JSON")
    pop.add_argument("--compact", action="store_true", help="write compact JSON; .gz paths are compressed")
    pop.set_defaults(fn=_population)

    rs = sub.add_parser(
        "room-sim",
        help="closed-loop Standard-vs-FairPlay room routing comparison → room_sim_*.json",
    )
    rs.add_argument("--data-root", help="repo root containing data/ (default: auto-detect or PLAYSIM_DATA_ROOT)")
    rs.add_argument("--seed", type=int, default=42, help="primary seed (canonical outputs use this)")
    rs.add_argument("--seeds", help="comma-separated seed set to average the directional headline (default: just --seed)")
    rs.add_argument("--horizon", type=float, default=480.0, help="horizon in minutes (default 480 = 8h)")
    rs.add_argument("--samples", type=int, default=20, help="Monte-Carlo equity samples")
    rs.add_argument("--tables", help="comma-separated table ids (default: all in table_roster.json)")
    rs.add_argument("--protect", action="store_true", help="also run the experimental FairPlay-protect arm")
    rs.add_argument("--protect-threshold", type=float, default=50.0, help="protect safety threshold (untuned)")
    rs.add_argument("--behavior", choices=["default", "fit-aware"], default="default",
                    help="player behavior model (fit-aware = experimental, illustrative until calibrated)")
    rs.add_argument("--out-dir", default=".", help="directory for room_sim_*/room_metrics_* outputs")
    rs.add_argument("--debug-trace", action="store_true",
                    help="attach the full ranked candidate list to each routing decision (verbose)")
    rs.add_argument("--gzip", action="store_true", help="write .json.gz outputs")
    rs.add_argument("--compact", action="store_true", help="compact JSON")
    rs.set_defaults(fn=_room_sim)

    t = sub.add_parser("tables", help="list available demo tables and archetypes")
    t.set_defaults(fn=_tables)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
