"""Build a self-contained, interactive sweep-explorer web UI from playsim outputs.

Scans ``playsim/out/`` for sweep / benchmark result files (the ``{meta, runs,
summary}`` JSON shape written by ``large-room-sweep`` and the static-capacity
sweep), normalizes them into a single dataset, computes per-seed win stability,
and writes one self-contained ``sweep-explorer.html`` (data embedded inline, no
network, no build step). Teammates open the file by double-clicking it.

Usage (from the playsim/ dir):

    .venv/bin/python analysis/build_sweep_explorer.py
    .venv/bin/python analysis/build_sweep_explorer.py --out-dir out --out sweep-explorer.html

Re-run it whenever new sweeps land in ``out/`` — datasets are discovered
generically, so future table-shape / rate grids appear automatically.

The numbers are illustrative synthetic-model outputs, never a validated
retention claim (see CLAUDE.md). The UI surfaces that banner prominently.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
from collections import defaultdict

# Metric registry: (key, label, unit, lower_is_better)
# unit: "hrs" -> 1 decimal, "n" -> count (mean may be fractional -> 1 decimal)
METRICS = [
    ("total_paid_seat_hours", "Total paid seat-hrs", "hrs", False),
    ("vulnerable_paid_seat_hours", "Vulnerable seat-hrs", "hrs", False),
    ("arrival_count", "Arrivals", "n", False),
    ("arrival_seated_count", "Arrivals seated", "n", False),
    ("arrival_balk_count", "Arrival balks", "n", True),
    ("arrival_balk_rate", "Arrival balk rate", "pct", True),
    ("demand_drop_rate", "Demand drop rate", "pct", True),
    ("seated_departure_count", "Seated departures", "n", True),
    ("terminal_churn_count", "Non-reseat exits", "n", True),
    ("reseek_departure_count", "Re-seat departures", "n", True),
    ("departure_rate_per_hour", "Departures / hr", "rate", True),
    ("terminal_churn_rate_per_hour", "Non-reseat exits / hr", "rate", True),
    ("reseek_departure_rate_per_hour", "Re-seat departures / hr", "rate", True),
    ("wait_balk_count", "Wait balks", "n", True),
    ("break_count", "Table breaks", "n", True),
    ("break_balk_count", "Break balks", "n", True),
    ("no_good_existing_seat_count", "No-good-seat moments", "n", True),
    ("forming_seat_count", "Forming seats", "n", False),
    ("formation_activation_count", "Formation activations", "n", False),
    ("table_reactivation_count", "Table reactivations", "n", False),
    ("final_active_tables", "Final active tables", "n", False),
    ("final_forming_tables", "Final forming tables", "n", False),
    ("final_empty_tables", "Final empty tables", "n", False),
    ("hands_total", "Hands dealt", "n", False),
]
METRIC_KEYS = [m[0] for m in METRICS]

# Terminal site-departure buckets, carried per cell/policy as DESCRIPTIVE room
# context — NOT registered in METRICS, so they never appear in the heatmap/table
# comparison selector. Departure counts are flat across routing arms (the
# FairPlay win is session duration, not who leaves), so they describe the room,
# they don't rank the policy. The frontend labels these.
DEPARTURE_KEYS = [
    "left_satisfied_count",
    "left_damaged_count",
    "couldnt_seat_count",
    "cohort_left_satisfied_count",
    "cohort_left_damaged_count",
    "cohort_couldnt_seat_count",
]

# Stability is computed against this baseline policy for each comparison metric.
BASELINE = "standard"
STABILITY_METRICS = ["vulnerable_paid_seat_hours", "total_paid_seat_hours"]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def normalize_cell(path):
    """Load one {meta, runs, summary} file into a normalized cell dict."""
    with open(path) as fh:
        raw = json.load(fh)
    meta = raw.get("meta", {})
    runs = raw.get("runs", [])
    if not runs:
        return None

    policies = meta.get("policies") or sorted({r["policy"] for r in runs})
    seeds = sorted({r["seed"] for r in runs})

    # rate / table shape: older files carry table shape in meta; agentic runs
    # carry it per-row because a single result can contain multiple cells.
    shape_keys = sorted({
        (
            r.get("tables", meta.get("tables")),
            r.get("active_tables", meta.get("active_tables")),
            float(r["arrival_rate_per_hour"]),
        )
        for r in runs
    })

    cells = []
    for tables, active_tables, rate in shape_keys:
        rate_runs = [
            r for r in runs
            if r.get("tables", meta.get("tables")) == tables
            and r.get("active_tables", meta.get("active_tables")) == active_tables
            and float(r["arrival_rate_per_hour"]) == rate
        ]

        # per-policy means across seeds
        means = {}
        departures = {}
        for pol in policies:
            pol_runs = [r for r in rate_runs if r["policy"] == pol]
            means[pol] = {
                k: _mean([r.get(k) for r in pol_runs]) for k in METRIC_KEYS
            }
            # descriptive departure context — only present once the sweep was run
            # with the departure buckets (older files lack the keys -> all None).
            dep = {k: _mean([r.get(k) for r in pol_runs]) for k in DEPARTURE_KEYS}
            if any(v is not None for v in dep.values()):
                departures[pol] = dep

        # per-seed lookup for stability + drilldown
        by_seed = defaultdict(dict)
        for r in rate_runs:
            by_seed[r["seed"]][r["policy"]] = r

        stability = {}
        for pol in policies:
            if pol == BASELINE:
                continue
            stability[pol] = {}
            for metric in STABILITY_METRICS:
                deltas = {}
                wins = 0
                n = 0
                for seed in seeds:
                    base = by_seed.get(seed, {}).get(BASELINE)
                    cand = by_seed.get(seed, {}).get(pol)
                    if base is None or cand is None:
                        continue
                    d = round(cand.get(metric, 0) - base.get(metric, 0), 4)
                    deltas[str(seed)] = d
                    n += 1
                    if d > 0:
                        wins += 1
                stability[pol][metric] = {
                    "wins": wins,
                    "n": n,
                    "deltas": deltas,
                    "mean_delta": _mean(list(deltas.values())),
                }

        # trim runs to the registered metric fields (+ seed/policy)
        slim_runs = []
        for r in sorted(rate_runs, key=lambda x: (x["seed"], x["policy"])):
            row = {"seed": r["seed"], "policy": r["policy"]}
            for k in METRIC_KEYS:
                row[k] = r.get(k)
            slim_runs.append(row)

        cells.append(
            {
                "tables": tables,
                "active_tables": active_tables,
                "rate": rate,
                "source_file": os.path.basename(path),
                "policies": policies,
                "seeds": seeds,
                "means": means,
                "departures": departures,
                "runs": slim_runs,
                "stability": stability,
            }
        )
    return meta, cells


def build_dataset(dataset_id, label, paths):
    all_cells = []
    config = {}
    policies_seen = []
    seeds_seen = set()
    for path in paths:
        loaded = normalize_cell(path)
        if not loaded:
            continue
        meta, cells = loaded
        if not config:
            fixed = meta.get("fixed", {})
            config = {
                k: meta.get(k)
                for k in (
                    "fixture",
                    "players",
                    "fixture_seed",
                    "horizon_min",
                    "equity_samples",
                    "arrival_mode",
                    "formation_mode",
                    "behavior",
                    "deterministic",
                    "note",
                )
            }
            if fixed:
                config.update({
                    "players": fixed.get("players"),
                    "fixture_seed": fixed.get("fixture_seed"),
                    "horizon_min": fixed.get("horizon_min"),
                    "equity_samples": fixed.get("samples"),
                    "formation_mode": fixed.get("formation_mode"),
                    "behavior": fixed.get("behavior"),
                })
                config["agentic_experiment"] = meta.get("experiment")
        for c in cells:
            seeds_seen.update(c["seeds"])
            for p in c["policies"]:
                if p not in policies_seen:
                    policies_seen.append(p)
        all_cells.extend(cells)

    if not all_cells:
        return None

    table_axis = sorted({c["tables"] for c in all_cells if c["tables"] is not None})
    rate_axis = sorted({c["rate"] for c in all_cells})
    kind = "grid" if len(table_axis) > 1 and len(rate_axis) > 1 else "single"

    # order policies: baseline first, then the rest in a stable order
    ordered_pol = [p for p in [BASELINE] if p in policies_seen]
    ordered_pol += [p for p in policies_seen if p != BASELINE]

    present = {k for c in all_cells for pol in c["means"] for k in c["means"][pol]}
    metrics = [
        {"key": k, "label": lbl, "unit": u, "lower_is_better": lib}
        for (k, lbl, u, lib) in METRICS
        if k in present
    ]

    return {
        "id": dataset_id,
        "label": label,
        "kind": kind,
        "config": config,
        "seeds": sorted(seeds_seen),
        "policies": ordered_pol,
        "table_axis": table_axis,
        "rate_axis": rate_axis,
        "metrics": metrics,
        "cells": sorted(all_cells, key=lambda c: (c["tables"] or 0, c["rate"])),
    }


def dataset_files(out_dir):
    """Group discoverable sweep files into (dataset_id, label, paths). The single
    source of which files belong to which dataset — reused by the dashboard-data
    emitter so its time-series cells line up with the explorer's regime cells."""
    groups = []
    static = sorted(glob.glob(os.path.join(out_dir, "static-capacity-sweep-*-rate-*.json")))
    if static:
        groups.append(("static-capacity", "Static capacity sweep", static))
    bench = sorted(glob.glob(os.path.join(out_dir, "large-room-benchmark-*.json")))
    for path in bench:
        name = os.path.splitext(os.path.basename(path))[0]
        groups.append((name, "Benchmark · " + name.replace("large-room-benchmark-", ""), [path]))
    agentic_groups = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(out_dir, "agentic*", "experiment-*-results.json"))):
        parent = os.path.basename(os.path.dirname(path))
        agentic_groups[parent].append(path)
    for parent, paths in sorted(agentic_groups.items()):
        groups.append((parent, "Agentic · " + parent.replace("agentic-", ""), paths))
    return groups


def discover(out_dir):
    datasets = []
    for dataset_id, label, paths in dataset_files(out_dir):
        ds = build_dataset(dataset_id, label, paths)
        if ds:
            datasets.append(ds)
    return datasets


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_out = os.path.normpath(os.path.join(here, "..", "out"))

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=default_out, help="dir holding sweep JSON (default: playsim/out)")
    ap.add_argument("--out", default="sweep-explorer.html", help="output html filename (written into --out-dir)")
    args = ap.parse_args()

    datasets = discover(args.out_dir)
    if not datasets:
        raise SystemExit(f"No sweep result files found under {args.out_dir!r}")

    payload = {
        "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "datasets": datasets,
    }

    template_path = os.path.join(here, "sweep_explorer_template.html")
    with open(template_path) as fh:
        template = fh.read()

    html = template.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
    out_path = os.path.join(args.out_dir, args.out)
    with open(out_path, "w") as fh:
        fh.write(html)

    n_cells = sum(len(d["cells"]) for d in datasets)
    print(f"Wrote {out_path}")
    print(f"  datasets: {len(datasets)} ({', '.join(d['id'] for d in datasets)})")
    print(f"  cells:    {n_cells}")


if __name__ == "__main__":
    main()
