"""Freeze the AI Investigator's case summaries to JSON (P4 output).

Reads ``data/derived/evidence_packets.json`` (Contract 3), runs the AI Investigator
once per packet, guardrail-checks each summary, and writes
``data/derived/case_summaries.json`` — the frozen, deterministic artifact the
pit-boss UI renders. Freezing is what makes the demo reproducible (the LLM itself
is not deterministic; the committed file is).

Requires ``ANTHROPIC_API_KEY`` in the environment (the LLM call). Without it, the
script prints how to set it and exits 0 without writing — it never fabricates a
summary.

Run:  ANTHROPIC_API_KEY=... python backend/scripts/build_summaries.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from investigator import MODEL, investigate  # noqa: E402

DERIVED = ROOT / "data" / "derived"
PACKETS = DERIVED / "evidence_packets.json"
OUT = DERIVED / "case_summaries.json"


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a repo-root .env into the environment (no deps).

    Does not override variables already set. `.env` is gitignored — the key is
    read at runtime and never committed.
    """
    env = ROOT / ".env"
    if not env.exists():
        return
    for raw in env.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def main() -> int:
    _load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set — the AI Investigator needs it to run.")
        print("Set it and re-run, e.g.:")
        print("  ANTHROPIC_API_KEY=sk-ant-... python backend/scripts/build_summaries.py")
        print("(No summaries were generated; nothing was written — the investigator "
              "never fabricates a summary.)")
        return 0

    packets = json.loads(PACKETS.read_text(encoding="utf-8"))["packets"]
    results = []
    any_violation = False
    for p in packets:
        print(f"  investigating {p['case_id']} ({p['case_type']}) ...", flush=True)
        r = investigate(p)
        v = r["guardrail_violations"]
        if v:
            any_violation = True
            print(f"    GUARDRAIL VIOLATIONS: {v}")
        results.append(r)

    out = {
        "meta": {
            "produced_by": "P4 / AI Investigator",
            "model": MODEL,
            "consumes": "Contract 3 — evidence_packets.json",
            "count": len(results),
            "note": "Frozen LLM case summaries. The model saw only the evidence "
                    "packet; every summary was guardrail-checked before freezing.",
            "any_guardrail_violation": any_violation,
        },
        "summaries": results,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} — {len(results)} summaries"
          + ("  ⚠ WITH VIOLATIONS" if any_violation else "  (all clean)"))
    # non-zero exit if any summary violated a hard rule — it must not ship
    return 1 if any_violation else 0


if __name__ == "__main__":
    raise SystemExit(main())
