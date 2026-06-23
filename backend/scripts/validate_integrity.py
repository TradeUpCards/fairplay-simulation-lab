"""Validate the integrity score (kickoff §2 ② acceptance).

Checks the convergence-rule bands against the seeded answer key:

* CL-001 (CASE-C)  -> high            (4 families converge -> hold for review)
* CL-002           -> neutral         (sub-threshold, monitor only)
* H-01 (CASE-E)    -> neutral         (household FP trap — NEVER escalate)
* OVL-001 (CASE-D) -> low             (schedule overlap — do NOT over-escalate)
* P-221 (CASE-G)   -> manual_review   (bot queue, kept out of collusion path)

Run:  python scripts/validate_integrity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scoring.integrity import score_integrity  # noqa: E402

EXPECTED = {
    "CL-001": "high",
    "CL-002": "neutral",
    "H-01": "neutral",
    "H-02": "neutral",
    "H-03": "neutral",
    "OVL-001": "low",
    "P-221": "manual_review",
}


def main() -> int:
    rel = json.loads((ROOT / "data" / "relationships.json").read_text(encoding="utf-8"))
    praw = json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8"))
    players = praw["players"] if isinstance(praw, dict) else praw

    results = {a.group_id: a for a in score_integrity(rel, players)}

    print("=== Integrity convergence-rule acceptance ===")
    failures = []
    for gid, expected in EXPECTED.items():
        a = results.get(gid)
        got = a.band if a else "<missing>"
        ok = got == expected
        if not ok:
            failures.append((gid, expected, got))
        fam = ",".join(e.code for e in a.signal_families) if a else ""
        ctr = ",".join(e.code for e in a.counter_evidence) if a else ""
        print(f"  {'PASS' if ok else 'FAIL'}  {gid:8} expect {expected:13} got {got:13} "
              f"[n={a.convergence_count if a else '-'} families={fam or '-'} "
              f"counter={ctr or '-'}]")

    # Guardrail assertions (hard rules — these are failing evals if violated)
    print("\n=== Guardrail checks ===")
    guards = []
    h01 = results.get("H-01")
    guards.append(("household never escalates (CASE-E)",
                   h01 and h01.band in ("low", "neutral") and h01.counter_evidence))
    ovl = results.get("OVL-001")
    guards.append(("schedule overlap not over-escalated (CASE-D)",
                   ovl and ovl.band == "low" and ovl.counter_evidence))
    bot = results.get("P-221")
    guards.append(("bot kept out of collusion path (CASE-G)",
                   bot and bot.group_kind == "bot_account" and bot.band == "manual_review"))
    cl1 = results.get("CL-001")
    guards.append(("CL-001 surfaces >= 4 convergent families",
                   cl1 and cl1.convergence_count >= 4))
    for name, ok in guards:
        if not ok:
            failures.append((name, "guardrail", "VIOLATED"))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")

    if failures:
        print(f"\nFAILED {len(failures)} check(s).")
        return 1
    print("\nAll integrity acceptance + guardrail checks pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
