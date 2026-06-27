"""Freeze a *sequence* of routed lobbies across simulated room churn (demo Part 2).

Produces ``data/derived/lobby_sequence.json``: one room shown over several churn
steps, each step ordered two ways for a seeking player —

  - ``standard``: the naive most-full ordering (sort by seated_count desc),
  - ``fairplay``: the real router ordering (Rank = 0.30·Fit + 0.40·Health + 0.30·ΔHealth).

Both arrays hold the *same* player-safe tables; only the order differs. Between
steps a seeded churn stands some seated players and sits some unseated ones, which
changes table composition, so re-running the **real router** re-ranks FairPlay (and
fullness re-ranks Standard). This is the data behind the side-by-side lobby demo.

Player-safe: the rows come from the router's ``player_lobby`` view (neutral badges +
safe facts only — no scores/risk/archetype), plus stat columns from the roster.

Run:  python backend/scripts/build_lobby_sequence.py [--data-root DIR] [--player P-104]
Saturday: point ``--data-root`` at the large-room fixture for the 50-table version.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scoring.integrity import score_integrity  # noqa: E402
from scoring.health import build_cluster_band_index, score_all_tables  # noqa: E402
from scoring.router import route  # noqa: E402

OUT = ROOT / "data" / "derived" / "lobby_sequence.json"

# Stat columns the lobby shows; pulled from the roster entry when present.
STAT_KEYS = {"avg_pot_size_usd": "avg_pot_usd", "hands_per_hour": "hands_per_hour"}


def _load(data_root: Path) -> dict:
    rel = json.loads((data_root / "relationships.json").read_text(encoding="utf-8"))
    praw = json.loads((data_root / "players.json").read_text(encoding="utf-8"))
    players = praw["players"] if isinstance(praw, dict) else praw
    roster = json.loads((data_root / "table_roster.json").read_text(encoding="utf-8"))["tables"]
    sess_path = data_root / "sessions.json"
    sessions = []
    if sess_path.exists():
        sessions = [s for s in json.loads(sess_path.read_text(encoding="utf-8")).get("sessions", [])
                    if "session_id" in s]
    return {"rel": rel, "players": players, "roster": roster, "sessions": sessions}


def _route_once(ctx: dict, roster: list[dict], player_id: str) -> list[dict]:
    """Run the real scoring pipeline on the current roster → player_lobby rows."""
    by = {p["player_id"]: p for p in ctx["players"]}
    integ = score_integrity(ctx["rel"], ctx["players"])
    cbi = build_cluster_band_index(ctx["rel"], integ)
    health = {h.table_id: h for h in score_all_tables(roster, by, cbi, sessions=ctx["sessions"])}
    routed = route(player_id, roster, by, cbi, health)
    return routed["player_lobby"]


def _with_stats(rows: list[dict], roster_by_id: dict, rng: random.Random) -> list[dict]:
    """Attach player-safe stat columns (from roster; plrs/flop synthesized, seeded)."""
    out = []
    for r in rows:
        rentry = roster_by_id.get(r["table_id"], {})
        row = dict(r)
        for src, dst in STAT_KEYS.items():
            if src in rentry:
                row[dst] = rentry[src]
        # plrs/flop% isn't in the roster — seed a stable value per table for the column.
        seed = sum(ord(c) for c in r["table_id"])
        row["plrs_per_flop_pct"] = 26 + (seed % 38)
        out.append(row)
    return out


def _churn(roster: list[dict], players: list[dict], rng: random.Random, n_stand: int, n_sit: int) -> dict:
    """Seeded: stand n_stand seated players, sit n_sit unseated ones. Mutates roster."""
    seated_ids = {pid for t in roster for pid in t.get("seated_player_ids", [])}
    # stand
    standable = [(t, pid) for t in roster for pid in list(t.get("seated_player_ids", []))]
    rng.shuffle(standable)
    stood = 0
    for t, pid in standable:
        if stood >= n_stand:
            break
        if pid in t["seated_player_ids"] and t["seated_count"] > 0:
            t["seated_player_ids"].remove(pid)
            t["seated_count"] -= 1
            t["open_seats"] = t.get("open_seats", 0) + 1
            seated_ids.discard(pid)
            stood += 1
    # sit
    pool = [p["player_id"] for p in players if p["player_id"] not in seated_ids]
    rng.shuffle(pool)
    open_tables = [t for t in roster if t.get("open_seats", 0) > 0]
    sat = 0
    for pid in pool:
        if sat >= n_sit or not open_tables:
            break
        t = rng.choice([t for t in roster if t.get("open_seats", 0) > 0] or [None])
        if t is None:
            break
        t["seated_player_ids"].append(pid)
        t["seated_count"] += 1
        t["open_seats"] -= 1
        sat += 1
    return {"stood": stood, "sat": sat}


def _standard_order(fairplay_rows: list[dict]) -> list[dict]:
    """Same tables, sorted naive most-full (the Standard policy)."""
    return sorted(fairplay_rows, key=lambda r: (-r["seated_count"], r["table_id"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=str(ROOT / "data"))
    ap.add_argument("--player", default="P-104")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--stand", type=int, default=6)
    ap.add_argument("--sit", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    data_root = Path(args.data_root)
    ctx = _load(data_root)
    rng = random.Random(args.seed)
    roster_by_id = {t["table_id"]: t for t in ctx["roster"]}

    steps = []
    for i in range(args.steps):
        churn = None
        if i > 0:
            churn = _churn(ctx["roster"], ctx["players"], rng, args.stand, args.sit)
            roster_by_id = {t["table_id"]: t for t in ctx["roster"]}
        fairplay = _with_stats(_route_once(ctx, ctx["roster"], args.player), roster_by_id, rng)
        standard = _standard_order(fairplay)
        label = "Open" if i == 0 else f"After churn {i}"
        steps.append({"label": label, "churn": churn, "standard": standard, "fairplay": fairplay})

    out = {
        "meta": {
            "source": str(data_root.name),
            "seed": args.seed,
            "player_id": args.player,
            "note": ("One room over churn steps, ordered two ways for the seeking player. "
                     "standard = most-full; fairplay = real router. Same tables, different order. "
                     "Player-safe (router player_lobby view + roster stat columns)."),
        },
        "steps": steps,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(steps)}-step lobby sequence ({len(steps[0]['fairplay'])} tables) "
          f"for {args.player} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
