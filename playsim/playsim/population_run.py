"""Run playsim over the full ``players.json`` population (table_roster seating)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fixture_paths import find_data_root
from .hand_export import (
    build_player_index,
    features_for_export,
    session_to_hand_docs,
)
from .population import (
    build_table_roster,
    derive_table_seed,
    format_player_id,
    hands_target,
    load_classifications,
    load_players_by_id,
    load_table_roster,
)
from .runner import run_session


def run_population(
    *,
    data_root: str | Path | None = None,
    master_seed: int = 42,
    cap: int = 400,
    equity_samples: int = 20,
    table_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Simulate every (or selected) fixture table; return playsim-native JSON dict."""
    root = find_data_root(data_root)
    players_by_id = load_players_by_id(root)
    archetypes = load_classifications(root)
    tables = load_table_roster(root)
    if table_ids:
        allow = set(table_ids)
        tables = [t for t in tables if t["table_id"] in allow]

    all_hands: list[dict] = []
    all_features: dict[str, dict] = {}
    table_meta: list[dict] = []
    skipped_seats: list[dict] = []
    targets_by_pid: dict[str, int] = {}

    for table in tables:
        tid = table["table_id"]
        roster, skipped = build_table_roster(table, players_by_id, archetypes)
        for sid in skipped:
            skipped_seats.append({"table_id": tid, "player_id": sid})
        if len(roster) < 2:
            table_meta.append({
                "table_id": tid, "status": "skipped", "reason": "fewer than 2 seated players",
            })
            continue

        table_targets: dict[int, int] = {}
        for p in roster:
            pid_s = format_player_id(p.player_id)
            target = hands_target(players_by_id[pid_s], cap)
            targets_by_pid[pid_s] = target
            table_targets[p.player_id] = target

        n_hands = max(table_targets.values())
        seed = derive_table_seed(master_seed, tid)
        result = run_session(
            roster,
            n_hands,
            seed=seed,
            equity_samples=equity_samples,
            label=tid,
            quota_hands=table_targets,
        )
        dealt = result.hands_played

        docs = session_to_hand_docs(result, table_id=tid)
        all_hands.extend(docs)
        all_features.update(features_for_export(result))
        table_meta.append({
            "table_id": tid,
            "status": "ok",
            "seed": seed,
            "hands_played": result.n_hands,
            "hands_horizon": n_hands,
            "seated": len(roster),
            "hands_dealt_by_player": {
                format_player_id(pid): dealt[pid] for pid in dealt
            },
        })

    player_index = build_player_index(all_hands, targets=targets_by_pid)
    return {
        "meta": {
            "schema_version": "1.0.0",
            "engine": "playsim",
            "format": "playsim_hand_histories",
            "master_seed": master_seed,
            "cap": cap,
            "equity_samples": equity_samples,
            "data_root": str(root),
            "tables_simulated": sum(1 for t in table_meta if t.get("status") == "ok"),
            "total_hands": len(all_hands),
            "skipped_seats": skipped_seats,
            "fixture_note": (
                "Playsim-native hand corpus from data/players.json + table_roster.json. "
                "Archetypes from data/derived/classifications.json. "
                "Synthetic sandbox data — not real play."
            ),
        },
        "tables": table_meta,
        "hands": all_hands,
        "player_index": player_index,
        "features": all_features,
    }
