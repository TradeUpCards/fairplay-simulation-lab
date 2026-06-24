"""U8 — service.simulate_room + CLI room-sim + multi-seed comparison.

The directional hypothesis (FairPlay-route >= Standard on vulnerable paid
seat-time) is a *product hypothesis*, not an invariant: it is reported in the
``comparison`` block over a pinned seed set, not asserted here (single-config MVP
runs are config-dependent). These tests pin the harness correctness, determinism,
shared-arrival invariant, and CLI output — the things that must always hold.
"""

from __future__ import annotations

from pathlib import Path

from playsim.cli import main
from playsim.service import simulate_room

TABLES = ["T-22", "T-8"]
PINNED_SEEDS = [42, 7]


def _run(**kw):
    return simulate_room(seeds=PINNED_SEEDS, horizon_min=20, equity_samples=6,
                         tables=TABLES, **kw)


def test_comparison_is_well_formed():
    res = _run()
    assert set(res) >= {"standard", "fairplay", "room_metrics_standard",
                        "room_metrics_fairplay", "comparison"}
    c = res["comparison"]
    assert c["metric"] == "vulnerable_paid_seat_hours"
    assert c["seeds"] == PINNED_SEEDS
    assert len(c["per_seed"]["standard"]) == len(PINNED_SEEDS)
    assert len(c["per_seed"]["fairplay_route"]) == len(PINNED_SEEDS)
    assert isinstance(c["routing_helped"], bool)


def test_means_computed_from_per_seed():
    c = _run()["comparison"]
    n = len(PINNED_SEEDS)
    assert c["standard_mean"] == round(sum(c["per_seed"]["standard"]) / n, 3)
    assert c["fairplay_route_mean"] == round(sum(c["per_seed"]["fairplay_route"]) / n, 3)
    assert c["delta_hours"] == round(c["fairplay_route_mean"] - c["standard_mean"], 3)


def test_comparison_is_deterministic_over_pinned_seeds():
    a = _run()["comparison"]
    b = _run()["comparison"]
    assert a == b          # pinned seed set -> identical averaged result


def test_both_arms_share_identical_arrivals():
    res = _run()
    assert res["standard"]["arrival_intents"] == res["fairplay"]["arrival_intents"]


def test_protect_arm_optional():
    res = _run(protect=True)
    assert "fairplay_protect" in res
    assert res["fairplay_protect"]["meta"]["engine"] == "playsim"


def test_cli_room_sim_writes_outputs(tmp_path: Path):
    rc = main(["room-sim", "--seed", "42", "--horizon", "20", "--samples", "6",
               "--tables", "T-22,T-8", "--out-dir", str(tmp_path)])
    assert rc == 0
    for name in ("room_sim_standard", "room_sim_fairplay",
                 "room_metrics_standard", "room_metrics_fairplay"):
        assert (tmp_path / f"{name}.json").is_file()
