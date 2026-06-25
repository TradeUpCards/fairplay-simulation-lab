"""Validate the evidence packets against the Contract-3 schema and the hard rules.

Asserts, for every packet in ``data/derived/evidence_packets.json``:
  * all eight Contract-3 fields present and non-trivial;
  * ``case_type`` is a known lens (health ≠ integrity kept distinct);
  * ``counter_evidence`` and ``uncertainties`` are non-empty (always surfaced);
  * ``allowed_actions`` ⊆ the safe operator menu and contains NO enforcement verb
    (no ban/freeze/suspend/restrict/lock/close) — the system never auto-enforces;
  * ``recommended_action`` is a human action, never an enforcement verb;
  * no obvious raw-data leakage (packets carry IDs + scores, not raw player rows).

Run:  python backend/scripts/validate_evidence.py   (exit 0 = all pass)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scoring.evidence import ALLOWED_ACTIONS, CASE_TYPES  # noqa: E402

PACKETS = ROOT / "data" / "derived" / "evidence_packets.json"
REQUIRED = ["case_id", "case_type", "scores", "top_evidence", "counter_evidence",
            "uncertainties", "recommended_action", "allowed_actions"]
ENFORCEMENT_WORDS = {"ban", "banned", "freeze", "frozen", "suspend", "suspended",
                     "restrict", "restricted", "lock", "locked", "close", "closed",
                     "confiscate", "seize"}
# raw-row keys that must never appear inside a packet's evidence/scores
RAW_LEAK_KEYS = {"hole_cards", "hand_history", "raw_sessions", "card", "cards"}


def _has_enforcement(text: str) -> str | None:
    low = (text or "").lower().replace("-", "_")
    for w in ENFORCEMENT_WORDS:
        # word-ish boundary check
        if w in low.split() or f"_{w}" in low or low.startswith(w) or low.endswith(w):
            return w
    return None


def main() -> int:
    doc = json.loads(PACKETS.read_text(encoding="utf-8"))
    packets = doc["packets"]
    errors: list[str] = []

    if not packets:
        errors.append("no packets produced")

    for p in packets:
        cid = p.get("case_id", "<?>")
        for fld in REQUIRED:
            if fld not in p:
                errors.append(f"{cid}: missing field '{fld}'")
        if p.get("case_type") not in CASE_TYPES:
            errors.append(f"{cid}: unknown case_type {p.get('case_type')!r}")
        if not p.get("counter_evidence"):
            errors.append(f"{cid}: counter_evidence is empty (must always be surfaced)")
        if not p.get("uncertainties"):
            errors.append(f"{cid}: uncertainties is empty (must always be surfaced)")
        if not p.get("recommended_action"):
            errors.append(f"{cid}: recommended_action is empty")

        # allowed_actions must be a safe subset with no enforcement verb
        for a in p.get("allowed_actions", []):
            if a not in ALLOWED_ACTIONS:
                errors.append(f"{cid}: allowed_action {a!r} not in the safe menu")
            if _has_enforcement(a):
                errors.append(f"{cid}: allowed_action {a!r} is an enforcement verb")
        # recommended_action must not be enforcement
        w = _has_enforcement(p.get("recommended_action", ""))
        if w:
            errors.append(f"{cid}: recommended_action contains enforcement verb {w!r}")

        # no raw-row leakage anywhere in the packet
        blob = json.dumps(p).lower()
        for k in RAW_LEAK_KEYS:
            if f'"{k}"' in blob:
                errors.append(f"{cid}: possible raw-data leak — key {k!r} present")

    if errors:
        print(f"FAIL — {len(errors)} issue(s):")
        for e in errors:
            print("  -", e)
        return 1
    print(f"OK — {len(packets)} packets pass all Contract-3 + hard-rule checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
