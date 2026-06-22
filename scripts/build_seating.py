"""Freeze the seating scores to JSON (Contract 2, score ⑦).

For each "seeking" player (the demo's new player P-104) computes Fit / ΔHealth /
seating-risk across every table with an open seat, and writes
``data/derived/seating_scores.json`` — what the router (⑧) consumes and the
pit-boss console / lobby render. Integrity-hard-gated tables are marked (the
router removes them from candidates entirely).

Run:  python scripts/build_seating.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.integrity import score_integrity  # noqa: E402
from scoring.health import build_cluster_band_index, score_all_tables  # noqa: E402
from scoring.seating import score_seating  # noqa: E402

OUT_DIR = ROOT / "data" / "derived"
OUT = OUT_DIR / "seating_scores.json"

# The demo's seeking player(s). Extend as more routing scenarios are wired.
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

    seeking = []
    for pid in SEEKING_PLAYERS:
        candidates = []
        for t in roster:
            if t.get("open_seats", 0) <= 0:
                continue
            s = score_seating(pid, t, by, cbi, health[t["table_id"]])
            d = s.as_dict()
            d["table_health"] = round(health[t["table_id"]].health, 1)
            d["table_band"] = health[t["table_id"]].band
            candidates.append(d)
        seeking.append({"player_id": pid, "candidate_tables": candidates})

    out = {
        "meta": {
            "schema_version": "1.0.0",
            "contract": "Contract 2 — scores + recommendations (P3)",
            "score": "7. seating (Fit champion + ΔHealth + seating-risk)",
            "sources": ["data/table_roster.json", "data/players.json",
                        "data/relationships.json", "data/sessions.json"],
            "note": (
                "Per player×table seating scores. ΔHealth is the marginal "
                "composition-health change (P_bleed held fixed); it can be "
                "positive even where seating-risk is HIGH — the new-player danger "
                "lives in seating_risk + table band, not the ΔHealth sign. "
                "integrity_gated tables are removed from router candidates "
                "entirely. OPERATOR-FACING: seating-risk / numeric scores must "
                "never reach the player lobby."
            ),
        },
        "seeking_players": seeking,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    n = sum(len(s["candidate_tables"]) for s in seeking)
    print(f"Wrote seating scores for {len(seeking)} player(s), {n} pairs -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
