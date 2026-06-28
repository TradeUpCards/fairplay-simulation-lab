"""Output guardrails -- verify the coach's response against its hard rules.

The system prompt asks the model to behave; this checks that it *did*. The coach is
not safety-critical the way the Investigator is, but two PRD acceptance rules are
hard gates -- no real-money language and no GTO/solved claims -- and the make-or-break
is that coaching is *grounded and specific*, not generic. So every response is scanned
before it is shown: it must cite equity, name the opponent's leak, and give a
type-specific better line.
"""

from __future__ import annotations

import re
from typing import Any

# Real-money language must never appear -- this is a play-chip training game (#6).
REAL_MONEY_WORDS = [
    "real money", "real cash", "deposit", "deposits", "withdraw", "withdrawal",
    "cash out", "cashout", "wager", "for cash", "buy-in with", "real funds",
]
# GTO / solved claims are banned ("solver-like" as a style label is allowed; a
# *claim* that the advice is optimal/solved is not) (#6).
GTO_CLAIM_WORDS = [
    "gto", "game theory optimal", "game-theory optimal", "nash equilibrium",
    "is solved", "solved solution", "perfectly optimal", "the optimal play",
    "theoretically optimal", "unexploitable",
]
# Accusatory / verdict language has no place in coaching either.
VERDICT_WORDS = ["cheater", "is cheating", "is a bot", "colluding", "collusion"]

REQUIRED_FIELDS = ["headline", "opponent_read", "decisions", "summary"]


def _find(text: str, phrases: list[str]) -> list[str]:
    low = (text or "").lower()
    return [p for p in phrases if re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", low)]


def _all_prose(summary: dict[str, Any]) -> str:
    """Every human-readable string in the response, flattened, for scanning."""
    parts = [str(summary.get(f, "")) for f in ("headline", "summary")]
    read = summary.get("opponent_read") or {}
    if isinstance(read, dict):
        parts += [str(read.get("style_label", "")), str(read.get("tell", ""))]
    for d in summary.get("decisions") or []:
        if isinstance(d, dict):
            parts += [str(d.get(k, "")) for k in
                      ("why_this_play", "better_line", "your_action")]
    return " ".join(parts)


def check_coaching(summary: dict[str, Any]) -> list[str]:
    """Return a list of guardrail violations (empty == clean)."""
    violations: list[str] = []

    for f in REQUIRED_FIELDS:
        v = summary.get(f)
        if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0):
            violations.append(f"missing/empty field: {f}")

    blob = _all_prose(summary)
    for w in _find(blob, REAL_MONEY_WORDS):
        violations.append(f"real-money language: {w!r}")
    for w in _find(blob, GTO_CLAIM_WORDS):
        violations.append(f"GTO/solved claim: {w!r}")
    for w in _find(blob, VERDICT_WORDS):
        violations.append(f"accusatory language: {w!r}")

    # The opponent read must actually name a leak (the make-or-break: specific, not generic).
    read = summary.get("opponent_read") or {}
    if not isinstance(read, dict) or len(str(read.get("tell", ""))) < 15:
        violations.append("opponent_read.tell too thin (must name the specific leak)")

    # Every assessed decision must cite a plausible equity number and a type-specific
    # rationale -- this is what separates grounded coaching from generic advice.
    decisions = summary.get("decisions") or []
    if not decisions:
        violations.append("no decisions assessed (coaching must be per-decision)")
    for i, d in enumerate(decisions):
        if not isinstance(d, dict):
            violations.append(f"decision[{i}] is not an object")
            continue
        eq = d.get("equity_pct")
        if not isinstance(eq, (int, float)) or not (0.0 <= float(eq) <= 100.0):
            violations.append(f"decision[{i}] equity_pct missing or out of 0-100")
        if len(str(d.get("why_this_play", ""))) < 15:
            violations.append(f"decision[{i}] why_this_play too thin (not type-specific)")

    return violations
