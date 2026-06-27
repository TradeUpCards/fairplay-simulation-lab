"""Emit the frozen JSON the React /dashboard route binds.

Reads the same ``out/`` sweep files the standalone sweep-explorer discovers and
writes two artifacts into the repo ``data/`` dir (the frontend's ``@data`` import
root):

* ``room_sweep.json``      — the NORMALIZED regime payload (``{generated_at,
  datasets}``), produced by reusing ``build_sweep_explorer`` so the heatmap /
  win-stability math lives in exactly one place (Python). Identical shape to what
  the standalone HTML embeds.
* ``room_timeseries.json`` — per-cell, per-policy, seed-AVERAGED cumulative
  trace (total / cohort paid seat-hours, active tables) sampled at the sweep's
  ``sample_interval_min`` cadence. This is what the animated hero chart plays;
  it is keyed by the same ``"<tables>|<rate>"`` cell identity as the heatmap so a
  selected cell drives the replay.

Usage (from playsim/, in the venv):

    .venv/bin/python analysis/build_dashboard_data.py
    .venv/bin/python analysis/build_dashboard_data.py --out-dir out --data-dir ../data

The numbers are illustrative synthetic-model outputs, never a validated retention
claim (see CLAUDE.md). The frontend surfaces that banner.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
from collections import defaultdict

import build_sweep_explorer as bse

# (source field on a sample snapshot, emitted key, scale). Seat-time is converted
# minutes -> hours so the chart axis matches the heatmap's seat-hours.
TS_METRICS = [
    ("total_paid_seat_min", "total_paid_seat_hours", 1.0 / 60.0),
    ("cohort_paid_seat_min", "vulnerable_paid_seat_hours", 1.0 / 60.0),
    ("active_tables", "active_tables", 1.0),
]


def _avg_series(runs: list[dict]) -> dict:
    """Seed-average a group of runs (same tables/rate/policy) onto a shared t grid.

    Indexed by ``t_min`` so runs of unequal length (e.g. an early-terminating
    seed) still align; each t averages only the seeds that reached it.
    """
    by_t: dict[float, list[dict]] = defaultdict(list)
    for r in runs:
        for snap in r.get("series", []):
            by_t[round(float(snap["t_min"]), 1)].append(snap)
    ts = sorted(by_t)
    metrics: dict[str, list[float]] = {}
    for src, dst, scale in TS_METRICS:
        metrics[dst] = [
            round(sum(s[src] for s in by_t[t]) / len(by_t[t]) * scale, 3) for t in ts
        ]
    return {
        "t_min": ts,
        "t_hr": [round(t / 60.0, 3) for t in ts],
        "metrics": metrics,
    }


def build_timeseries(out_dir: str) -> dict:
    datasets: dict[str, dict] = {}
    for dataset_id, label, paths in bse.dataset_files(out_dir):
        groups: dict[tuple, list[dict]] = defaultdict(list)
        seeds_by_cell: dict[str, set] = defaultdict(set)
        interval_min = None
        horizon_min = None
        for path in paths:
            with open(path) as fh:
                raw = json.load(fh)
            meta = raw.get("meta", {})
            interval_min = interval_min or meta.get("sample_interval_min")
            horizon_min = horizon_min or meta.get("horizon_min")
            for run in raw.get("runs", []):
                tables = run.get("tables", meta.get("tables"))
                rate = float(run["arrival_rate_per_hour"])
                groups[(tables, rate, run["policy"])].append(run)
                seeds_by_cell[f"{tables}|{rate}"].add(run.get("seed"))

        cells: dict[str, dict] = {}
        for (tables, rate, policy), runs in sorted(groups.items()):
            key = f"{tables}|{rate}"
            avg = _avg_series(runs)
            cell = cells.setdefault(
                key,
                {"tables": tables, "rate": rate, "t_min": avg["t_min"],
                 "t_hr": avg["t_hr"], "policies": {}},
            )
            cell["policies"][policy] = avg["metrics"]
        for key, cell in cells.items():
            cell["seeds"] = sorted(s for s in seeds_by_cell[key] if s is not None)

        if cells:
            datasets[dataset_id] = {
                "label": label,
                "interval_min": interval_min,
                "horizon_min": horizon_min,
                "cells": cells,
            }
    return datasets


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    default_out = os.path.normpath(os.path.join(here, "..", "out"))
    default_data = os.path.normpath(os.path.join(here, "..", "..", "data"))

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=default_out,
                    help="dir holding sweep JSON (default: playsim/out)")
    ap.add_argument("--data-dir", default=default_data,
                    help="dir to write frozen dashboard JSON (default: repo data/)")
    args = ap.parse_args(argv)

    datasets = bse.discover(args.out_dir)
    if not datasets:
        raise SystemExit(f"No sweep result files found under {args.out_dir!r}")
    timeseries = build_timeseries(args.out_dir)

    generated_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(args.data_dir, exist_ok=True)

    sweep_path = os.path.join(args.data_dir, "room_sweep.json")
    with open(sweep_path, "w") as fh:
        json.dump({"generated_at": generated_at, "datasets": datasets}, fh, indent=2)
        fh.write("\n")

    ts_path = os.path.join(args.data_dir, "room_timeseries.json")
    with open(ts_path, "w") as fh:
        json.dump({"generated_at": generated_at, "datasets": timeseries}, fh, indent=2)
        fh.write("\n")

    n_cells = sum(len(d["cells"]) for d in datasets)
    n_ts = sum(len(d["cells"]) for d in timeseries.values())
    print(f"Wrote {sweep_path}  ({len(datasets)} datasets, {n_cells} regime cells)")
    print(f"Wrote {ts_path}  ({n_ts} time-series cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
