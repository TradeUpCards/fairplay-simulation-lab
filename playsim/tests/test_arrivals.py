"""U3 — shared seeded arrival-intent stream."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from playsim.arrivals import ArrivalIntent, build_arrival_intents, unseated_pool
from playsim.population import format_player_id, load_players_by_id, load_table_roster

REPO = Path(__file__).resolve().parents[2]


def _root():
    # mirror test_population's data-root resolution
    from playsim.fixture_paths import find_data_root
    try:
        find_data_root()
        return None
    except Exception:
        return REPO


def test_same_seed_is_byte_identical_both_arms():
    root = _root()
    a = build_arrival_intents(480, seed=42, root=root)
    b = build_arrival_intents(480, seed=42, root=root)
    assert a == b           # AE1: both arms consume the identical stream


def test_different_seed_differs():
    root = _root()
    a = build_arrival_intents(480, seed=42, root=root)
    b = build_arrival_intents(480, seed=43, root=root)
    assert a != b


def test_pool_is_unseated_and_classified():
    root = _root()
    players = set(load_players_by_id(root))
    seated = {pid for t in load_table_roster(root) for pid in t["seated_player_ids"]}
    intents = build_arrival_intents(480, seed=42, root=root)

    for it in intents:
        pid = format_player_id(it.player_id)
        assert pid in players          # real player
        assert pid not in seated       # not seated at hour 0
        assert it.archetype            # carries a classification


def test_exactly_one_intent_per_pool_player():
    root = _root()
    pool = unseated_pool(root)
    intents = build_arrival_intents(480, seed=42, root=root)
    ids = [it.player_id for it in intents]
    assert len(ids) == len(set(ids))           # no duplicates
    assert len(ids) == len(pool)               # one per pool player
    assert len(pool) == 122 - 68               # the unseated ~54


def test_no_demand_modulation_in_signature():
    """The stream must not take any table-health input — that would make the two
    arms see different demand."""
    params = set(inspect.signature(build_arrival_intents).parameters)
    assert not (params & {"health", "health_by_id", "tables", "room_state"})


def test_arrival_times_within_horizon():
    root = _root()
    intents = build_arrival_intents(480, seed=42, root=root)
    assert all(0.0 <= it.arrive_at_min <= 480 for it in intents)
    # sorted by (time, id)
    assert intents == sorted(intents, key=lambda a: (a.arrive_at_min, a.player_id))


def test_continuous_arrivals_are_seeded_and_rate_limited():
    root = _root()
    a = build_arrival_intents(
        480, seed=42, root=root, mode="continuous", arrival_rate_per_hour=2.0,
    )
    b = build_arrival_intents(
        480, seed=42, root=root, mode="continuous", arrival_rate_per_hour=2.0,
    )
    fixture = build_arrival_intents(480, seed=42, root=root)
    ids = [it.player_id for it in a]

    assert a == b
    assert 0 < len(a) < len(fixture)
    assert len(ids) == len(set(ids))
    assert all(0.0 <= it.arrive_at_min <= 480 for it in a)
    assert a == sorted(a, key=lambda it: (it.arrive_at_min, it.player_id))
