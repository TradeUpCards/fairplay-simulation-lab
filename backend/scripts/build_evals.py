"""Build the eval results for the AI Investigator summaries (P4 evals).

Reads the frozen summaries (``case_summaries.json``), the evidence packets
(``evidence_packets.json``), and the seeded case labels, scores each summary on
the rubric (``evals.rubric.score``), and writes
``data/derived/case_evals.json`` — the per-case, per-criterion pass/fail the eval
panel renders. Deterministic; no LLM (the eval must not depend on the model it
grades). Exits non-zero if any case fails any criterion.

Run:  python backend/scripts/build_evals.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from evals import score  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "case_evals.json"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    summaries = _load(DERIVED / "case_summaries.json")["summaries"]
    packets = {p["case_id"]: p for p in _load(DERIVED / "evidence_packets.json")["packets"]}
    labels = {c["case_id"]: c for c in _load(ROOT / "data" / "seeded_case_labels.json")["cases"]}

    evals = []
    for s in summaries:
        cid = s["case_id"]
        if s.get("summary") is None or cid not in packets or cid not in labels:
            continue
        evals.append(score(cid, s["summary"], packets[cid], labels[cid]))

    by_crit: Counter = Counter()
    crit_total: Counter = Counter()
    for e in evals:
        for name, c in e["criteria"].items():
            crit_total[name] += 1
            if c["pass"]:
                by_crit[name] += 1
    passed = sum(1 for e in evals if e["passed"])

    out = {
        "meta": {
            "produced_by": "P4 / eval rubric",
            "grades": "the AI Investigator's case summaries (case_summaries.json)",
            "deterministic": True,
            "count": len(evals),
        },
        "eval_summary": {
            "total": len(evals),
            "passed": passed,
            "failed": len(evals) - passed,
            "by_criterion": {k: f"{by_crit[k]}/{crit_total[k]}" for k in crit_total},
        },
        "evals": evals,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {OUT.relative_to(ROOT)} — {passed}/{len(evals)} cases pass all criteria")
    for e in evals:
        fails = [k for k, c in e["criteria"].items() if not c["pass"]]
        mark = "PASS" if e["passed"] else "FAIL"
        print(f"  {e['case_id']:7s} {mark}" + ("" if e["passed"] else f"  ({', '.join(fails)})"))
    return 0 if passed == len(evals) else 1


if __name__ == "__main__":
    raise SystemExit(main())
