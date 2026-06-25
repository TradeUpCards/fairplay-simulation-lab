"""Validate the frozen AI Investigator summaries against the hard rules.

Re-checks every summary in ``data/derived/case_summaries.json`` with
``investigator.guardrails.check_summary`` and asserts each carries the required
fields, no enforcement/verdict language, a human recommended action, and
substantive counter-evidence + uncertainty. Also verifies coverage of the
mandatory demo cases (A, C, E).

If the summaries file doesn't exist yet (no key at build time), it says so and
exits 0 — there is nothing to validate.

Run:  python backend/scripts/validate_summaries.py   (exit 0 = all pass)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from investigator.guardrails import check_summary  # noqa: E402

SUMMARIES = ROOT / "data" / "derived" / "case_summaries.json"
MANDATORY = {"CASE-A", "CASE-C", "CASE-E"}


def main() -> int:
    if not SUMMARIES.exists():
        print(f"{SUMMARIES.relative_to(ROOT)} not found — run build_summaries.py "
              "with ANTHROPIC_API_KEY set first. Nothing to validate.")
        return 0

    doc = json.loads(SUMMARIES.read_text(encoding="utf-8"))
    rows = doc["summaries"]
    errors: list[str] = []
    seen = set()

    for r in rows:
        cid = r.get("case_id", "<?>")
        seen.add(cid)
        if r.get("stop_reason") == "refusal" or r.get("summary") is None:
            errors.append(f"{cid}: no summary (stop_reason={r.get('stop_reason')})")
            continue
        for v in check_summary(r["summary"]):
            errors.append(f"{cid}: {v}")

    for c in MANDATORY - seen:
        errors.append(f"missing mandatory demo case: {c}")

    if errors:
        print(f"FAIL — {len(errors)} issue(s):")
        for e in errors:
            print("  -", e)
        return 1
    print(f"OK — {len(rows)} summaries pass all guardrail checks "
          f"(mandatory cases {sorted(MANDATORY)} covered).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
