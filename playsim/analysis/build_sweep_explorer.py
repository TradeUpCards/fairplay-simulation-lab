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

    # rate / table shape: cells are single-rate in the static sweep; if a file
    # carries multiple rates we split per rate so the grid stays clean.
    rates = sorted({float(r["arrival_rate_per_hour"]) for r in runs})

    cells = []
    for rate in rates:
        rate_runs = [r for r in runs if float(r["arrival_rate_per_hour"]) == rate]

        # per-policy means across seeds
        means = {}
        for pol in policies:
            pol_runs = [r for r in rate_runs if r["policy"] == pol]
            means[pol] = {
                k: _mean([r.get(k) for r in pol_runs]) for k in METRIC_KEYS
            }

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
                "tables": meta.get("tables"),
                "active_tables": meta.get("active_tables"),
                "rate": rate,
                "source_file": os.path.basename(path),
                "policies": policies,
                "seeds": seeds,
                "means": means,
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


def discover(out_dir):
    datasets = []

    static = sorted(glob.glob(os.path.join(out_dir, "static-capacity-sweep-*-rate-*.json")))
    if static:
        ds = build_dataset("static-capacity", "Static capacity sweep", static)
        if ds:
            datasets.append(ds)

    bench = sorted(glob.glob(os.path.join(out_dir, "large-room-benchmark-*.json")))
    for path in bench:
        name = os.path.splitext(os.path.basename(path))[0]
        ds = build_dataset(name, "Benchmark · " + name.replace("large-room-benchmark-", ""), [path])
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
