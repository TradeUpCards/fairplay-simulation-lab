"""Freeze the router output to JSON (Contract 2, score ⑧).

For each seeking player computes the routed lobby — operator view (full rank /
score breakdown) and player_lobby view (neutral badges + safe table facts only)
— and writes ``data/derived/router_lobby.json``. The two views make the
player-facing / operator-facing seam explicit in the artifact.

Run:  python scripts/build_router.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.integrity import score_integrity  # noqa: E402
from scoring.health import build_cluster_band_index, score_all_tables  # noqa: E402
from scoring.router import route  # noqa: E402

OUT_DIR = ROOT / "data" / "derived"
OUT = OUT_DIR / "router_lobby.json"

SEEKING_PLAYERS = ["P-104"]


def main() -> int:
    rel = json.loads((ROOT / "data" / "relationships.json").read_text(encoding="utf-8"))
    praw = json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8"))
    players = praw["players"] if isinstance(praw, dict) else praw
    by = {p["player_id"]: p for p in players}
    roster = json.loads((ROOT / "data" / "table_roster.json").read_text(encoding="utf-8"))["tables"]
    sessions = [s for s in json.loads((ROOT / "data" / "sessions.json").read_text(encoding="utf-8"))["sessions"]
                if "session_id" in s]

    integ = score_integrity(rel, players)
    cbi = build_cluster_band_index(rel, integ)
    health = {h.table_id: h for h in score_all_tables(roster, by, cbi, sessions=sessions)}

    routed = [route(pid, roster, by, cbi, health) for pid in SEEKING_PLAYERS]

    out = {
        "meta": {
            "schema_version": "1.0.0",
            "contract": "Contract 2 — scores + recommendations (P3)",
            "score": "8. router (frozen policy: Rank = 0.30·Fit + 0.40·Health + 0.30·ΔHealth)",
            "sources": ["data/table_roster.json", "data/players.json",
                        "data/relationships.json", "data/sessions.json"],
            "note": (
                "Deterministic, no-model routing policy with integrity hard-gate "
                "first and a vulnerable-protection gate (promotion requires LOW "
                "seating-risk). Each seeking player has TWO views: 'operator_view' "
                "(OPERATOR-FACING — full rank/score/risk breakdown for the "
                "pit-boss console) and 'player_lobby' (PLAYER-FACING — neutral "
                "badges + safe table facts only; NO scores, risk, or integrity "
                "language). The lobby view is the only player-visible output."
            ),
        },
        "routed": routed,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote routed lobby for {len(routed)} player(s) -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
