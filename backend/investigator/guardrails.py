"""Output guardrails — verify the AI Investigator's summary against the hard rules.

The system prompt asks the model to behave; this checks that it *did*. Trusting the
prompt alone is not enough for a safety-critical surface — every summary is scanned
before it can be shown. A summary with any violation is flagged (the build refuses
to freeze a violating summary).
"""

from __future__ import annotations

import re
from typing import Any

# Enforcement / verdict language that must never appear in a summary.
ENFORCEMENT_WORDS = [
    "ban", "banned", "freeze", "frozen", "suspend", "suspended", "restrict",
    "restricted", "lock", "locked", "close the account", "terminate", "confiscate",
    "seize", "blacklist",
]
VERDICT_WORDS = [
    "guilty", "is a cheater", "are cheaters", "definitely cheat", "proven",
    "confirmed collusion", "is cheating", "are cheating", "caught cheating",
]

REQUIRED_FIELDS = ["headline", "assessment", "key_signals", "counter_evidence",
                   "uncertainty", "recommended_action", "reviewer_note"]


def _find(text: str, phrases: list[str]) -> list[str]:
    low = (text or "").lower()
    hits = []
    for p in phrases:
        # whole-word-ish match so "urban" doesn't trip "ban"
        if re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", low):
            hits.append(p)
    return hits


def check_summary(summary: dict[str, Any]) -> list[str]:
    """Return a list of guardrail violations (empty == clean)."""
    violations: list[str] = []

    for f in REQUIRED_FIELDS:
        v = summary.get(f)
        if v is None or (isinstance(v, (str, list)) and len(v) == 0):
            violations.append(f"missing/empty field: {f}")

    # scan all prose for enforcement + verdict language
    blob = " ".join(str(summary.get(f, "")) for f in REQUIRED_FIELDS
                    if f != "key_signals")
    blob += " " + " ".join(summary.get("key_signals", []) or [])
    for w in _find(blob, ENFORCEMENT_WORDS):
        violations.append(f"enforcement language: {w!r}")
    for w in _find(blob, VERDICT_WORDS):
        violations.append(f"verdict/accusation language: {w!r}")

    # recommended_action specifically must be a non-enforcement human action
    rec = str(summary.get("recommended_action", ""))
    if _find(rec, ENFORCEMENT_WORDS):
        violations.append("recommended_action is an enforcement action")

    # counter-evidence and uncertainty must be substantive, not a token gesture
    if len(str(summary.get("counter_evidence", ""))) < 15:
        violations.append("counter_evidence too thin (must be surfaced honestly)")
    if len(str(summary.get("uncertainty", ""))) < 15:
        violations.append("uncertainty too thin (must carry the synthetic-data caveat)")

    return violations
