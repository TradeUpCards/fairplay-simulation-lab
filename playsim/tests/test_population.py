"""Population fixture smoke tests."""

from pathlib import Path

from playsim.fixture_paths import find_data_root
from playsim.population import derive_table_seed, parse_player_id
from playsim.population_run import run_population
from playsim.runner import Player, run_session


REPO = Path(__file__).resolve().parents[2]


def test_parse_player_id():
    assert parse_player_id("P-104") == 104
    assert parse_player_id(104) == 104


def test_derive_table_seed_stable():
    assert derive_table_seed(42, "T-22") == derive_table_seed(42, "T-22")
    assert derive_table_seed(42, "T-22") != derive_table_seed(42, "T-11")


def test_population_one_table_smoke():
    try:
        root = find_data_root(REPO)
    except FileNotFoundError:
        root = find_data_root()
    a = run_population(data_root=root, master_seed=42, cap=40, equity_samples=12, table_ids=["T-11"])
    b = run_population(data_root=root, master_seed=42, cap=40, equity_samples=12, table_ids=["T-11"])
    assert a["meta"]["total_hands"] == b["meta"]["total_hands"] > 0
    assert "P-198" in a["player_index"]
    hand = a["hands"][0]
    assert hand["table_id"] == "T-11"
    assert "actions" in hand and "seats" in hand
    assert a["features"]["P-198"]["hands_dealt"] > 0
    for pid, row in a["player_index"].items():
        assert row["hands_dealt"] == row["hands_target"], pid


def test_quota_leave_mixed_table():
    roster = [
        Player(101, "new"),
        Player(201, "grinder"),
        Player(301, "regular"),
    ]
    result = run_session(
        roster,
        6,
        seed=11,
        equity_samples=8,
        quota_hands={101: 2, 201: 6, 301: 6},
    )

    assert result.hands_played == {101: 2, 201: 6, 301: 6}
    assert result.features[101]["hands_dealt"] == 2
    assert all(101 not in h.seat_player_ids for h in result.hands[2:])
