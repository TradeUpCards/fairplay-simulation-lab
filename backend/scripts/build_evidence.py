"""Freeze the evidence packets to JSON (Contract 3, the P3 → P4 seam).

Reads the frozen P3 outputs (``data/derived/{integrity_scores,health_scores,
seating_scores,classifications}.json``) plus ``data/seeded_case_labels.json``,
runs ``scoring.evidence.assemble_packets``, and writes
``data/derived/evidence_packets.json`` — the structured, raw-data-free packet the
AI Investigator (P4) consumes.

Run:  python backend/scripts/build_evidence.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scoring.evidence import assemble_packets  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "evidence_packets.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cases = _load(ROOT / "data" / "seeded_case_labels.json")["cases"]

    integrity = _load(DERIVED / "integrity_scores.json")["assessments"]
    health = _load(DERIVED / "health_scores.json")["health_scores"]
    seating = _load(DERIVED / "seating_scores.json")["seeking_players"]
    classifications = _load(DERIVED / "classifications.json")["classifications"]

    integrity_by_group = {a["group_id"]: a for a in integrity}
    health_by_table = {h["table_id"]: h for h in health}
    classification_by_player = {c["player_id"]: c for c in classifications}

    # seating: pick the recommended (top) candidate table for each seeking player,
    # so the packet carries one seating_risk/fit story rather than the whole list.
    seating_by_player: dict[str, dict] = {}
    for sp in seating:
        cands = sp.get("candidate_tables") or []
        if cands:
            seating_by_player[sp["player_id"]] = cands[0]

    packets = assemble_packets(
        cases,
        integrity_by_group=integrity_by_group,
        health_by_table=health_by_table,
        seating_by_player=seating_by_player,
        classification_by_player=classification_by_player,
    )

    out = {
        "meta": {
            "contract": "3 — evidence packet (P3 produces, P4 consumes)",
            "schema": ["case_id", "case_type", "scores", "top_evidence",
                       "counter_evidence", "uncertainties", "recommended_action",
                       "allowed_actions"],
            "count": len(packets),
            "note": "Structured evidence only — no raw player/session rows. "
                    "The AI Investigator sees this and nothing else.",
        },
        "packets": [p.as_dict() for p in packets],
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} — {len(packets)} packets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
