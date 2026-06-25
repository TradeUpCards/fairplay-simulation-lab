"""Shared seeded arrival-intent stream for the room simulator.

The A/B's *demand* is policy-independent: a single seeded list of who seeks a
seat and when, generated once and replayed unchanged by both the Standard and
FairPlay arms. Only the *placement* of each arrival differs by policy.

Pool = players in ``data/players.json`` who are NOT seated in the hour-0
``data/table_roster.json`` (the unseated ~54). Each pool player produces
**exactly one** arrival intent. The arrival schedule is flat (uniform over the
horizon) — explicitly **no** health-modulated arrival rates, which would make
the two arms see different demand and confound the comparison.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from .population import (
    derive_table_seed,
    load_classifications,
    load_players_by_id,
    load_table_roster,
    parse_player_id,
)


@dataclass(frozen=True)
class ArrivalIntent:
    player_id: int      # playsim int id
    archetype: str
    arrive_at_min: float


def unseated_pool(root: Path | None = None) -> list[str]:
    """``P-*`` ids present in players.json but not seated at hour 0, sorted."""
    players_by_id = load_players_by_id(root)
    roster = load_table_roster(root)
    seated = {pid for t in roster for pid in t.get("seated_player_ids", [])}
    return sorted(pid for pid in players_by_id if pid not in seated)


def build_arrival_intents(
    horizon_min: float,
    *,
    seed: int,
    root: Path | None = None,
    warmup_min: float = 0.0,
    mode: str = "fixture-once",
    arrival_rate_per_hour: float | None = None,
) -> list[ArrivalIntent]:
    """Deterministic, policy-independent arrival stream.

    ``fixture-once`` preserves the original MVP behavior: every unseated fixture
    player produces exactly one intent, with flat-uniform arrival time over the
    horizon.

    ``continuous`` is a conservative rate-controlled variation: intents arrive as
    a seeded Poisson process, drawing without replacement from the existing
    unseated fixture pool. It does not invent synthetic players; if the pool is
    exhausted, demand stops.
    """
    classifications = load_classifications(root)
    # only classified players can be simulated; skip any players.json/
    # classifications.json drift rather than crashing the whole room sim
    pool = [pid for pid in unseated_pool(root) if pid in classifications]
    rng = random.Random(derive_table_seed(seed, "arrivals"))

    if mode not in {"fixture-once", "continuous"}:
        raise ValueError(f"unknown arrival mode {mode!r}")

    intents: list[ArrivalIntent] = []
    if mode == "fixture-once":
        for pid in pool:
            arrive_at = round(rng.uniform(warmup_min, horizon_min), 1)
            intents.append(ArrivalIntent(parse_player_id(pid), classifications[pid], arrive_at))
    else:
        if horizon_min <= warmup_min or not pool:
            return []
        rate_per_hour = (
            float(arrival_rate_per_hour)
            if arrival_rate_per_hour is not None
            else len(pool) / max((horizon_min - warmup_min) / 60.0, 1e-9)
        )
        if rate_per_hour <= 0:
            raise ValueError("arrival_rate_per_hour must be positive for continuous arrivals")
        shuffled_pool = list(pool)
        rng.shuffle(shuffled_pool)
        t = float(warmup_min)
        rate_per_min = rate_per_hour / 60.0
        for pid in shuffled_pool:
            t += rng.expovariate(rate_per_min)
            if t > horizon_min:
                break
            intents.append(ArrivalIntent(parse_player_id(pid), classifications[pid], round(t, 1)))

    # stable order by time then id so consumers iterate deterministically
    intents.sort(key=lambda a: (a.arrive_at_min, a.player_id))
    return intents
