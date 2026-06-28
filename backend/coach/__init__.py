"""Post-hand poker coach -- the AI Investigator pattern pointed at teaching.

Structured hand summary in -> one guardrailed Claude call -> grounded, per-decision
coaching out. The coach reuses the investigator's prompt + structured-output +
output-check scaffolding; it is NOT a detector.
"""

from .leaks import READS, OpponentRead, read_for
from .prompt import COACH_SCHEMA, SYSTEM_PROMPT
from .guardrails import check_coaching

__all__ = [
    "READS", "OpponentRead", "read_for",
    "COACH_SCHEMA", "SYSTEM_PROMPT", "check_coaching",
]
