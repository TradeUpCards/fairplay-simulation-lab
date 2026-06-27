"""Tests for the dashboard data pipeline: RoomSim interval sampling + the
build_dashboard_data emitter (normalized regime payload + seed-averaged series)."""

from __future__ import annotations

import json
import os
import sys

import pytest

from playsim.policies import StandardPolicy
from playsim.room import RoomSim

ANALYSIS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis")
if ANALYSIS_DIR not in sys.path:
    sys.path.insert(0, ANALYSIS_DIR)

import build_dashboard_data as bdd  # noqa: E402
import build_sweep_explorer as bse  # noqa: E402


# --- RoomSim interval sampling ------------------------------------------------

def _run(**kw):
    return RoomSim(StandardPolicy(), master_seed=42, horizon_min=120,
                   equity_samples=2, **kw).run()


def test_sampling_disabled_by_default():
    assert _run().samples == []


def test_samples_deterministic_and_monotonic():
    a = _run(sample_interval_min=20.0)
    b = _run(sample_interval_min=20.0)
    assert a.samples == b.samples                       # byte-identical replay
    assert len(a.samples) >= 6
    totals = [s["total_paid_seat_min"] for s in a.samples]
    assert all(y >= x for x, y in zip(totals, totals[1:]))   # cumulative, non-decreasing
    for s in a.samples:                                 # carries the chart's fields
        assert {"t_min", "total_paid_seat_min", "cohort_paid_seat_min", "active_tables"} <= set(s)


def test_final_sample_reaches_horizon():
    r = _run(sample_interval_min=20.0)
    assert r.samples[-1]["t_min"] == pytest.approx(120.0)


def test_final_sample_equals_true_total():
    """The closing snapshot must include the final step's accrual, so the hero's
    endpoint equals the sweep summary total (not one step short)."""
    base = _run()  # identical sim, no sampling -> the true realized total
    sampled = _run(sample_interval_min=20.0)
    true_total = round(sum(base.seat_minutes.values()), 1)
    n = len(base.seat_minutes)
    # within per-player rounding only (NOT a whole missing step, which would be
    # many minutes of room-wide accrual).
    assert sampled.samples[-1]["total_paid_seat_min"] == pytest.approx(true_total, abs=0.05 * n + 0.2)


def test_sampling_does_not_perturb_the_sim():
    """Observation only: enabling sampling must not change any sim outcome."""
    base = _run()
    sampled = _run(sample_interval_min=15.0)
    assert base.seat_minutes == sampled.seat_minutes
    assert base.routing_decisions == sampled.routing_decisions
    assert base.hands_total == sampled.hands_total


def test_invalid_interval_rejected():
    with pytest.raises(ValueError):
        _run(sample_interval_min=0)


# --- emit pipeline ------------------------------------------------------------

def _fake_run(seed, rate, policy, totals_min, cohort_min):
    """A minimal sweep run row carrying both summary keys (for the explorer
    normalize) and a per-interval series (for the timeseries emit)."""
    series = [
        {"t_min": t, "total_paid_seat_min": tm, "cohort_paid_seat_min": cm,
         "active_tables": 2, "forming_tables": 0, "breaks_so_far": 0}
        for t, tm, cm in zip((20.0, 40.0), totals_min, cohort_min)
    ]
    return {
        "seed": seed, "arrival_rate_per_hour": float(rate), "policy": policy,
        "tables": None,  # overwritten by caller
        "total_paid_seat_hours": round(totals_min[-1] / 60.0, 3),
        "vulnerable_paid_seat_hours": round(cohort_min[-1] / 60.0, 3),
        "break_count": 0, "wait_balk_count": 0, "forming_seat_count": 0,
        "formation_activation_count": 0, "final_active_tables": 2,
        "series": series,
    }


def _write_sweep_file(path, tables, rates):
    runs = []
    for rate in rates:
        for seed in (42, 7):
            for policy in ("standard", "fairplay"):
                r = _fake_run(seed, rate, policy,
                              totals_min=[60.0, 120.0], cohort_min=[30.0, 60.0])
                r["tables"] = tables
                runs.append(r)
    payload = {
        "meta": {"fixture": "test", "tables": tables, "sample_interval_min": 20.0,
                 "horizon_min": 40.0, "policies": ["standard", "fairplay"]},
        "runs": runs,
    }
    path.write_text(json.dumps(payload))


def test_emit_produces_grid_and_aligned_timeseries(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    _write_sweep_file(out / "static-capacity-sweep-tables10-rate-grid.json", 10, [20.0, 40.0])
    _write_sweep_file(out / "static-capacity-sweep-tables20-rate-grid.json", 20, [20.0, 40.0])

    datasets = bse.discover(str(out))
    assert len(datasets) == 1
    ds = datasets[0]
    assert ds["kind"] == "grid"                       # 2 inventories × 2 rates
    assert ds["table_axis"] == [10, 20]
    assert ds["rate_axis"] == [20.0, 40.0]

    ts = bdd.build_timeseries(str(out))
    sc = ts["static-capacity"]
    assert sc["interval_min"] == 20.0 and sc["horizon_min"] == 40.0
    assert set(sc["cells"]) == {"10|20.0", "10|40.0", "20|20.0", "20|40.0"}

    cell = sc["cells"]["10|20.0"]
    assert cell["tables"] == 10 and cell["rate"] == 20.0
    assert cell["seeds"] == [7, 42]
    # both seeds carry identical fake series -> seed-average equals the input,
    # minutes converted to hours (120 min -> 2.0 hr at the final sample).
    assert cell["policies"]["standard"]["total_paid_seat_hours"] == [1.0, 2.0]
    assert cell["policies"]["standard"]["vulnerable_paid_seat_hours"] == [0.5, 1.0]
    assert cell["t_hr"] == [0.333, 0.667]   # minutes/60, rounded to 3dp by the emitter


def test_seed_averaging_is_a_real_mean(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    runs = [
        _fake_run(42, 20.0, "standard", [60.0, 120.0], [0.0, 0.0]),
        _fake_run(7, 20.0, "standard", [0.0, 60.0], [0.0, 0.0]),
    ]
    for r in runs:
        r["tables"] = 10
    (out / "static-capacity-sweep-tables10-rate-grid.json").write_text(
        json.dumps({"meta": {"tables": 10, "sample_interval_min": 20.0,
                             "horizon_min": 40.0, "policies": ["standard"]}, "runs": runs})
    )
    cell = bdd.build_timeseries(str(out))["static-capacity"]["cells"]["10|20.0"]
    # totals: seed42=[60,120], seed7=[0,60] -> mean minutes [30,90] -> hours [0.5,1.5]
    assert cell["policies"]["standard"]["total_paid_seat_hours"] == [0.5, 1.5]
