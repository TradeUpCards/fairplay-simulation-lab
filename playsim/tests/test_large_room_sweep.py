from __future__ import annotations

from playsim.cli import main
from playsim.large_room_sweep import run_large_room_sweep


def _small_sweep(tmp_path):
    return run_large_room_sweep(
        data_root=tmp_path / "data",
        fixture_seed=11,
        seeds=[5],
        arrival_rates_per_hour=[18.0],
        horizon_min=20.0,
        equity_samples=3,
        policies=("standard", "fairplay", "fairplay_liveness"),
        players=140,
        tables=12,
        active_tables=8,
        regenerate_fixture=True,
    )


def test_large_room_sweep_is_deterministic(tmp_path):
    first = _small_sweep(tmp_path)
    second = _small_sweep(tmp_path)

    assert first == second
    assert first["meta"]["deterministic"] is True
    assert len(first["runs"]) == 3
    assert {row["policy"] for row in first["runs"]} == {
        "standard",
        "fairplay",
        "fairplay_liveness",
    }


def test_large_room_sweep_reuses_shared_arrivals_by_policy(tmp_path):
    payload = _small_sweep(tmp_path)
    arrival_counts = {
        row["arrival_count"]
        for row in payload["runs"]
        if row["seed"] == 5 and row["arrival_rate_per_hour"] == 18.0
    }

    assert len(arrival_counts) == 1
    assert next(iter(arrival_counts)) > 0
    assert all(row["total_paid_seat_hours"] >= row["vulnerable_paid_seat_hours"]
               for row in payload["runs"])


DEPARTURE_KEYS = (
    "left_satisfied_count",
    "left_damaged_count",
    "couldnt_seat_count",
    "cohort_left_satisfied_count",
    "cohort_left_damaged_count",
    "cohort_couldnt_seat_count",
)


def test_large_room_sweep_reports_departure_buckets(tmp_path):
    payload = _small_sweep(tmp_path)

    for row in payload["runs"]:
        # every bucket present as a non-negative int
        for key in DEPARTURE_KEYS:
            assert key in row, f"missing {key} in run row"
            assert isinstance(row[key], int) and row[key] >= 0
        # the cohort split can never exceed the all-players bucket
        assert row["cohort_left_satisfied_count"] <= row["left_satisfied_count"]
        assert row["cohort_left_damaged_count"] <= row["left_damaged_count"]
        assert row["cohort_couldnt_seat_count"] <= row["couldnt_seat_count"]
        # couldn't-seat is balked + wait-balked, so it covers wait-balks at least
        assert row["couldnt_seat_count"] >= row["wait_balk_count"]

    # buckets seed-average into the summary alongside the existing metrics
    for row in payload["summary"]:
        for key in DEPARTURE_KEYS:
            assert f"{key}_mean" in row


def test_large_room_sweep_cli_writes_outputs(tmp_path):
    rc = main([
        "large-room-sweep",
        "--fixture-out", str(tmp_path / "fixture"),
        "--regenerate-fixture",
        "--players", "140",
        "--tables", "12",
        "--active-tables", "8",
        "--seeds", "5",
        "--arrival-rates", "18",
        "--horizon", "20",
        "--samples", "3",
        "--out-json", str(tmp_path / "sweep.json"),
        "--out-md", str(tmp_path / "sweep.md"),
    ])

    assert rc == 0
    assert (tmp_path / "sweep.json").is_file()
    assert (tmp_path / "sweep.md").read_text(encoding="utf-8").startswith(
        "# Playsim large-room economics sweep"
    )
