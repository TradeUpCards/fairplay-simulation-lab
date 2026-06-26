from __future__ import annotations

from collections import Counter

from playsim.arrivals import build_arrival_intents, unseated_pool
from playsim.large_room_fixture import build_large_room_fixture, write_large_room_fixture
from playsim.population import load_classifications, load_players_by_id, load_table_roster
from playsim.router_adapter import RouterAdapter


def test_large_room_fixture_shape_defaults():
    payload = build_large_room_fixture(seed=7)
    players = payload["players"]["players"]
    tables = payload["table_roster"]["tables"]
    seated = [pid for t in tables for pid in t["seated_player_ids"]]

    assert len(players) == 1000
    assert len(tables) == 50
    assert sum(1 for t in tables if t["seated_count"] > 0) == 35
    assert sum(1 for t in tables if t["seated_count"] == 0) == 15
    assert len(seated) == len(set(seated))
    assert set(seated) <= {p["player_id"] for p in players}
    assert Counter(c["archetype"] for c in payload["classifications"]["classifications"])


def test_large_room_fixture_can_drive_rate_based_arrivals(tmp_path):
    write_large_room_fixture(tmp_path, seed=7)

    players = load_players_by_id(tmp_path)
    classes = load_classifications(tmp_path)
    tables = load_table_roster(tmp_path)
    pool = unseated_pool(tmp_path)

    assert len(players) == 1000
    assert len(classes) == 1000
    assert len(tables) == 50
    assert len(pool) > 700

    intents = build_arrival_intents(
        480,
        seed=7,
        root=tmp_path,
        mode="continuous",
        arrival_rate_per_hour=40,
    )
    assert 250 <= len(intents) <= 380
    assert len({i.player_id for i in intents}) == len(intents)
    assert len(intents) < len(pool)


def test_large_room_fixture_external_root_routes_with_backend_adapter(tmp_path):
    write_large_room_fixture(tmp_path, seed=7, player_count=200, table_count=12, active_table_count=8)

    adapter = RouterAdapter(tmp_path)
    tables = load_table_roster(tmp_path)
    pool = unseated_pool(tmp_path)
    placement = adapter.recommend(int(pool[0][2:]), tables)

    assert placement.operator_view
