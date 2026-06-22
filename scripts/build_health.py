"""Freeze the table-health score's output to JSON (Contract 2, scores ③–⑥).

Reads ``data/{table_roster,players,relationships,sessions}.json``, runs the
integrity score ② (for P_clus) and ``scoring.health.score_all_tables``, and
writes ``data/derived/health_scores.json`` — the frozen per-table Health(T) +
terms + band P1 (lobby routing / pit-boss console) and P4 consume.

Run:  python scripts/build_health.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.integrity import score_integrity  # noqa: E402
from scoring.health import build_cluster_band_index, score_all_tables  # noqa: E402

OUT_DIR = ROOT / "data" / "derived"
OUT = OUT_DIR / "health_scores.json"


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
    scores = [h.as_dict() for h in score_all_tables(roster, by, cbi, sessions=sessions)]

    out = {
        "meta": {
            "schema_version": "1.0.0",
            "contract": "Contract 2 — scores + recommendations (P3)",
            "score": "3-6. table health (champion: Health(T) = 100 - P_pred - P_frag - P_clus - P_bleed)",
            "sources": ["data/table_roster.json", "data/players.json",
                        "data/relationships.json", "data/sessions.json"],
            "bands": ["healthy", "fragile", "beginner_unfriendly", "collapsed"],
            "note": (
                "Per-table health. Composition terms (P_pred/P_frag/P_clus) lead; "
                "observed P_bleed lags and is 0 in this static snapshot. "
                "integrity_candidate flags a seated high-band cluster for the "
                "pit-boss queue regardless of numeric health. OPERATOR-FACING: "
                "numeric health scores must NEVER appear in the player lobby — "
                "the lobby shows only neutral badges derived from the band."
            ),
            "total_tables": len(scores),
        },
        "health_scores": scores,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(scores)} table-health scores -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
