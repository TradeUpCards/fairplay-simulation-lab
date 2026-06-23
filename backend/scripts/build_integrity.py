"""Freeze the integrity score's output to JSON (Contract 2, score ②).

Reads ``data/relationships.json`` + ``data/players.json``, runs
``scoring.integrity.score_integrity``, and writes
``data/derived/integrity_scores.json`` — the frozen per-group integrity
assessment P1 (pit-boss console) and P4 (evidence packet) consume.

Run:  python scripts/build_integrity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scoring.integrity import score_integrity  # noqa: E402

OUT_DIR = ROOT / "data" / "derived"
OUT = OUT_DIR / "integrity_scores.json"


def main() -> int:
    rel = json.loads((ROOT / "data" / "relationships.json").read_text(encoding="utf-8"))
    praw = json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8"))
    players = praw["players"] if isinstance(praw, dict) else praw

    assessments = [a.as_dict() for a in score_integrity(rel, players)]

    out = {
        "meta": {
            "schema_version": "1.0.0",
            "contract": "Contract 2 — scores + recommendations (P3)",
            "score": "2. integrity (champion: convergence rule, NOT a trained model)",
            "sources": ["data/relationships.json", "data/players.json"],
            "bands": ["low", "neutral", "high", "manual_review"],
            "note": (
                "Per-group integrity assessment by convergence of independent "
                "signal families net of counter-evidence. OPERATOR-FACING ONLY — "
                "integrity/'predator' language must never reach the player lobby. "
                "Bands recommend a human review action; they never assert "
                "collusion as fact. Counter-evidence is always surfaced."
            ),
            "total_assessments": len(assessments),
        },
        "assessments": assessments,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(assessments)} integrity assessments -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
