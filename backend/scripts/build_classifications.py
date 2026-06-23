"""Freeze the classification champion's output to JSON (Contract 2, score ①).

Reads ``data/players.json``, runs ``scoring.classify`` over every player, and
writes ``data/derived/classifications.json`` — the frozen artifact P1 (lobby /
pit-boss) and P4 (evidence packet) consume. Deterministic: same input → same
output, byte for byte.

Run:  python scripts/build_classifications.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scoring.classify import ARCHETYPES, classify  # noqa: E402

SRC = ROOT / "data" / "players.json"
OUT_DIR = ROOT / "data" / "derived"
OUT = OUT_DIR / "classifications.json"


def main() -> int:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    players = raw["players"] if isinstance(raw, dict) else raw

    classifications = []
    for p in players:
        res = classify(p)
        classifications.append({
            "player_id": p["player_id"],
            "archetype": res.archetype,
            "reason_codes": [rc.as_dict() for rc in res.reason_codes],
        })

    src_meta = raw.get("meta", {}) if isinstance(raw, dict) else {}
    out = {
        "meta": {
            "schema_version": "1.0.0",
            "contract": "Contract 2 — scores + recommendations (P3)",
            "score": "1. classification (champion: deterministic threshold rules)",
            "source": "data/players.json",
            "source_schema_version": src_meta.get("schema_version"),
            "source_seed": src_meta.get("seed"),
            "archetypes": list(ARCHETYPES),
            "note": (
                "Deterministic champion classifier. Reason codes are the audit "
                "trail behind each label — UI/evidence packet must render these, "
                "never hand-write the 'why'. OPERATOR-FACING: archetypes and "
                "reason codes must NOT appear in any player-facing lobby path."
            ),
            "total_players": len(classifications),
        },
        "classifications": classifications,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(classifications)} classifications -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
