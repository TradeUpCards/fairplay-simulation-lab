"""Generate a large playsim-only room fixture.

The canonical ``data/players.json`` / ``data/table_roster.json`` files are demo
and scoring fixtures. This module creates a separate data root for room-economics
experiments: more tables, more players, and enough unseated demand for rate-based
arrivals to be meaningful.
"""

from __future__ import annotations

import random
from pathlib import Path


ARCHETYPE_MIX = {
    "new": 0.07,
    "recreational": 0.28,
    "promo_hunter": 0.07,
    "regular": 0.20,
    "healthy_anchor": 0.17,
    "grinder": 0.10,
    "aggressive_predatory": 0.06,
    "shared_device_household": 0.03,
    "cluster_member": 0.015,
    "bot_like": 0.005,
}

STYLE_BY_BUCKET = [
    ("Low Stakes / Beginner-Friendly", "growing", 0.30),
    ("Balanced / Healthy Mix", "stable", 0.35),
    ("Regular-Heavy / Long Session", "stable", 0.18),
    ("High Volatility / Predatory-Mix", "declining", 0.12),
    ("Promo-Short / Low Action", "flat", 0.05),
]


def _choice_weighted(rng: random.Random, weights: dict[str, float]) -> str:
    total = sum(weights.values())
    x = rng.random() * total
    acc = 0.0
    for key, weight in weights.items():
        acc += weight
        if x <= acc:
            return key
    return next(reversed(weights))


def _style(rng: random.Random) -> tuple[str, str]:
    weights = {f"{i}": row[2] for i, row in enumerate(STYLE_BY_BUCKET)}
    row = STYLE_BY_BUCKET[int(_choice_weighted(rng, weights))]
    return row[0], row[1]


def _player(pid: int, archetype: str, rng: random.Random) -> dict:
    profiles = {
        "new": (7, 260, 24, 3, 0.34, 0.12, 1.0, 10, 0, True),
        "recreational": (180, 1400, 72, 8, 0.42, 0.18, 1.3, 16, 1, True),
        "promo_hunter": (90, 520, 38, 6, 0.24, 0.08, 0.7, 8, 9, True),
        "regular": (420, 5200, 135, 14, 0.27, 0.18, 2.0, 18, 1, False),
        "healthy_anchor": (360, 4400, 205, 12, 0.28, 0.16, 1.8, 15, 1, False),
        "grinder": (600, 11000, 320, 24, 0.31, 0.23, 2.8, 24, 0, False),
        "aggressive_predatory": (500, 8200, 245, 18, 0.58, 0.44, 4.2, 31, 0, False),
        "shared_device_household": (240, 1600, 115, 7, 0.32, 0.13, 1.1, 12, 1, True),
        "cluster_member": (510, 6400, 175, 16, 0.35, 0.24, 2.3, 20, 0, False),
        "bot_like": (480, 7600, 180, 20, 0.26, 0.20, 2.1, 17, 0, False),
    }
    days, hands, session, sessions, vpip, pfr, af, pot, promo, eligible = profiles[archetype]
    jitter = lambda base, pct: max(0, base * rng.uniform(1 - pct, 1 + pct))
    return {
        "player_id": f"P-{pid}",
        "display_name": f"{archetype.replace('_', ' ').title()} {pid}",
        "registered_days_ago": int(jitter(days, 0.25)),
        "lifetime_hands": int(jitter(hands, 0.35)),
        "avg_session_minutes": round(jitter(session, 0.20), 1),
        "sessions_last_30d": max(1, int(jitter(sessions, 0.30))),
        "vpip": round(min(0.95, max(0.02, jitter(vpip, 0.10))), 3),
        "pfr": round(min(0.90, max(0.01, jitter(pfr, 0.12))), 3),
        "aggression_factor": round(max(0.1, jitter(af, 0.20)), 2),
        "avg_pot_size_bb": round(jitter(pot, 0.25), 1),
        "promo_redemptions_30d": max(0, int(jitter(promo, 0.30))),
        "promo_eligible": eligible,
        "device_group_id": None,
        "household_id": None,
        "cluster_id": None,
        "bot_similarity_score": round(0.88 if archetype == "bot_like" else rng.uniform(0.02, 0.35), 3),
        "soft_play_delta": round(-0.35 if archetype == "cluster_member" else rng.uniform(-0.08, 0.02), 3),
        "timing_regularity": round(0.94 if archetype == "bot_like" else rng.uniform(0.2, 0.75), 3),
    }


def build_large_room_fixture(
    *,
    seed: int = 42,
    player_count: int = 1000,
    table_count: int = 50,
    active_table_count: int = 35,
    max_seats: int = 6,
    start_fill_min: int = 4,
    start_fill_max: int = 6,
) -> dict:
    """Return a self-contained playsim data-root payload."""
    if not 0 <= active_table_count <= table_count:
        raise ValueError("active_table_count must be between 0 and table_count")
    if start_fill_min < 2 or start_fill_max > max_seats or start_fill_min > start_fill_max:
        raise ValueError("invalid start fill bounds")

    rng = random.Random(seed)
    archetypes = [_choice_weighted(rng, ARCHETYPE_MIX) for _ in range(player_count)]
    players = [_player(10_000 + i, arch, rng) for i, arch in enumerate(archetypes)]
    classifications = [
        {"player_id": p["player_id"], "archetype": arch}
        for p, arch in zip(players, archetypes)
    ]

    shuffled = [p["player_id"] for p in players]
    rng.shuffle(shuffled)
    cursor = 0
    tables = []
    for i in range(table_count):
        style, trend = _style(rng)
        seated_n = rng.randint(start_fill_min, start_fill_max) if i < active_table_count else 0
        seated = shuffled[cursor:cursor + seated_n]
        cursor += seated_n
        tid = f"LR-{i + 1:02d}"
        tables.append({
            "table_id": tid,
            "stakes": "$0.50/$1" if i % 3 else "$1/$2",
            "game_type": "NLHE",
            "max_seats": max_seats,
            "seated_count": len(seated),
            "open_seats": max_seats - len(seated),
            "seated_player_ids": seated,
            "running_time_min": rng.randint(10, 240) if seated else 0,
            "avg_pot_size_usd": round(rng.uniform(8.0, 45.0), 2),
            "avg_session_length_min": round(rng.uniform(35.0, 180.0), 1),
            "hands_per_hour": rng.randint(55, 90),
            "pace_label": "normal",
            "style_volatility_label": style,
            "paid_seat_time_trend": trend if seated else "empty",
        })

    return {
        "players": {
            "meta": {
                "schema_version": "playsim-large-room-1.0",
                "generated": "deterministic",
                "seed": seed,
                "total_players": player_count,
                "fixture_note": (
                    "Generated playsim-only large-room fixture. Not canonical "
                    "product/demo data; use for room-economics simulations."
                ),
            },
            "players": players,
        },
        "classifications": {
            "meta": {
                "schema_version": "playsim-large-room-1.0",
                "source": "generated",
                "seed": seed,
            },
            "classifications": classifications,
        },
        "table_roster": {
            "schema_version": "playsim-large-room-1.0",
            "generated": "deterministic",
            "fixture_note": (
                f"Generated playsim large room: {table_count} tables, "
                f"{active_table_count} active at hour 0, {player_count} players."
            ),
            "tables": tables,
        },
        "relationships": {
            "meta": {
                "schema_version": "playsim-large-room-1.0",
                "generated": "deterministic",
                "seed": seed,
                "note": "Empty relationship graph for room-economics experiments.",
            },
            "clusters": [],
            "households": [],
            "regular_overlaps": [],
        },
        "devices": {
            "meta": {
                "schema_version": "playsim-large-room-1.0",
                "generated": "deterministic",
                "seed": seed,
            },
            "device_groups": [],
        },
    }


def write_large_room_fixture(out_dir: Path, **kwargs) -> None:
    import json

    payload = build_large_room_fixture(**kwargs)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "derived").mkdir(exist_ok=True)
    files = {
        out_dir / "players.json": payload["players"],
        out_dir / "table_roster.json": payload["table_roster"],
        out_dir / "relationships.json": payload["relationships"],
        out_dir / "devices.json": payload["devices"],
        out_dir / "derived" / "classifications.json": payload["classifications"],
    }
    for path, data in files.items():
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
