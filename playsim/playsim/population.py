"""Load the Day-2 fixture population and build table rosters for simulation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .fixture_paths import data_dir, find_data_root
from .runner import Player


def parse_player_id(raw: str | int) -> int:
    if isinstance(raw, int):
        return raw
    s = str(raw).strip()
    if s.startswith("P-"):
        return int(s[2:])
    return int(s)


def format_player_id(pid: int) -> str:
    return f"P-{pid}"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_players_by_id(root: Path | None = None) -> dict[str, dict]:
    raw = _load_json(data_dir(root) / "players.json")
    rows = raw["players"] if isinstance(raw, dict) else raw
    return {p["player_id"]: p for p in rows}


def load_classifications(root: Path | None = None) -> dict[str, str]:
    """Archetype per ``P-*`` id from frozen ``data/derived/classifications.json``."""
    path = data_dir(root) / "derived" / "classifications.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"missing {path} — run: python backend/scripts/build_classifications.py"
        )
    raw = _load_json(path)
    return {c["player_id"]: c["archetype"] for c in raw["classifications"]}


def load_table_roster(root: Path | None = None) -> list[dict]:
    raw = _load_json(data_dir(root) / "table_roster.json")
    return list(raw["tables"])


def hands_target(player: dict, cap: int) -> int:
    return min(int(player.get("lifetime_hands", 0)), cap)


def player_to_roster_entry(
    player_id: str,
    players_by_id: dict[str, dict],
    archetypes: dict[str, str],
) -> Player | None:
    row = players_by_id.get(player_id)
    if row is None:
        return None
    arch = archetypes.get(player_id)
    if not arch:
        return None
    pid = parse_player_id(player_id)
    return Player(
        pid,
        arch,
        cluster_id=row.get("cluster_id"),
        household_id=row.get("household_id"),
    )


def build_table_roster(
    table: dict,
    players_by_id: dict[str, dict],
    archetypes: dict[str, str],
) -> tuple[list[Player], list[str]]:
    """Return (roster, skipped_ids) for one ``table_roster.json`` entry."""
    roster: list[Player] = []
    skipped: list[str] = []
    for raw_id in table.get("seated_player_ids", []):
        p = player_to_roster_entry(raw_id, players_by_id, archetypes)
        if p is None:
            skipped.append(raw_id)
            continue
        roster.append(p)
    return roster, skipped


def table_hand_horizon(roster: list[Player], players_by_id: dict[str, dict], cap: int) -> int:
    if not roster:
        return 0
    targets = []
    for p in roster:
        row = players_by_id[format_player_id(p.player_id)]
        targets.append(hands_target(row, cap))
    return max(targets)


def derive_table_seed(master_seed: int, table_id: str) -> int:
    digest = hashlib.sha256(f"{master_seed}:{table_id}".encode()).digest()
    h = int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
    return h if h else master_seed + 1


def trim_hands_to_quotas(hands, roster: list[Player], players_by_id: dict[str, dict], cap: int):
    """Keep prefix of hands until every roster player reaches ``min(lifetime_hands, cap)``."""
    targets = {
        p.player_id: hands_target(players_by_id[format_player_id(p.player_id)], cap)
        for p in roster
    }
    dealt = {pid: 0 for pid in targets}
    out = []
    for h in hands:
        if all(dealt[pid] >= targets[pid] for pid in targets):
            break
        out.append(h)
        for pid in h.seat_player_ids:
            if pid in dealt:
                dealt[pid] += 1
    return out, dealt
