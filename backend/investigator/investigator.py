"""AI Investigator (P4) — evidence packet in → safe case summary out.

ONE guardrailed Claude call per case. The model receives only the structured
evidence packet (Contract 3) and the guardrail system prompt, and is constrained
to a fixed JSON shape via structured outputs. The output is then re-checked against
the hard rules (``guardrails.check_summary``) before it is allowed to be shown.

This is the project's third pillar — "the AI builds the case; the human judges it"
— and the only place an LLM appears. It is NOT the detector: structured scoring
(P3) found the risk; this only explains the packet.

Model: ``claude-opus-4-8`` (current default; adaptive thinking for the guardrail
reasoning). Requires ``ANTHROPIC_API_KEY`` in the environment.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .guardrails import check_summary
from .prompt import SUMMARY_SCHEMA, SYSTEM_PROMPT

MODEL = "claude-opus-4-8"

# The model occasionally emits a literal "\uXXXX" escape *as text* in a string
# value (e.g. "—" instead of an em-dash), which would render broken in the UI.
# Decode any such literal escape back to the real character.
_LITERAL_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def _unescape(obj: Any) -> Any:
    if isinstance(obj, str):
        return _LITERAL_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), obj)
    if isinstance(obj, list):
        return [_unescape(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _unescape(v) for k, v in obj.items()}
    return obj


def _render_packet(packet: dict[str, Any]) -> str:
    """The user turn: the evidence packet, verbatim, as the only input."""
    return (
        "Here is the structured evidence packet for one flagged case. It contains "
        "scores, top evidence, counter-evidence, uncertainties, and a recommended "
        "action — and nothing else (no raw player data). Write the case summary for "
        "the pit-boss, following every rule in your instructions.\n\n"
        "```json\n" + json.dumps(packet, indent=2) + "\n```"
    )


def _extract_json(resp: Any) -> dict[str, Any]:
    """Pull the structured-output JSON object from the response text blocks."""
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return json.loads(text)


def investigate(packet: dict[str, Any], *, client: Any = None,
                model: str = MODEL) -> dict[str, Any]:
    """Run the AI Investigator on one evidence packet.

    Returns a dict: ``case_id, case_type, model, summary, guardrail_violations,
    stop_reason``. ``summary`` is None and ``guardrail_violations`` explains why on
    a refusal. Raises only on a hard SDK/network error.
    """
    if client is None:
        import anthropic  # imported lazily so the module loads without a key
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the env

    resp = client.messages.create(
        model=model,
        max_tokens=8000,                         # headroom for adaptive thinking + JSON
        thinking={"type": "adaptive"},           # guardrail reasoning benefits from it
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": SUMMARY_SCHEMA},
        },
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _render_packet(packet)}],
    )

    result: dict[str, Any] = {
        "case_id": packet.get("case_id"),
        "case_type": packet.get("case_type"),
        "model": resp.model,
        "stop_reason": resp.stop_reason,
        "summary": None,
        "guardrail_violations": [],
    }

    if resp.stop_reason == "refusal":
        result["guardrail_violations"] = ["model refused (safety classifier)"]
        return result

    summary = _unescape(_extract_json(resp))
    result["summary"] = summary
    result["guardrail_violations"] = check_summary(summary)
    return result
