"""The post-hand coach -- ONE guardrailed Claude call. Mirrors ``investigator.investigate``.

Hand summary in -> structured per-decision coaching out, re-checked against the
coach guardrails before it is returned. The model receives only the structured
summary (Contract: the coach seam) and the guardrail system prompt, constrained to
a fixed JSON shape via structured outputs.

Default model is ``claude-sonnet-4-6`` -- the coach is a LIVE per-hand call, so a
cost-effective model fits; the eval sweeps Sonnet and ``claude-haiku-4-5`` to pick
the cheapest tier that passes the coaching-quality rubric. ``model`` is a parameter.
Requires ``ANTHROPIC_API_KEY`` in the environment.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .guardrails import check_coaching
from .prompt import COACH_SCHEMA, SYSTEM_PROMPT

MODEL = "claude-sonnet-4-6"

_LITERAL_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def _unescape(obj: Any) -> Any:
    if isinstance(obj, str):
        return _LITERAL_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), obj)
    if isinstance(obj, list):
        return [_unescape(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _unescape(v) for k, v in obj.items()}
    return obj


def _render(summary: dict[str, Any]) -> str:
    """The user turn: the hand summary, verbatim, as the only input."""
    return (
        "Here is the structured hand summary for one hand the student just played. "
        "It contains the board, the pot and amount-to-call at each of the student's "
        "decisions, the student's action and their RAW equity (vs a random hand) at "
        "that decision, and the decisive opponent's style and known leak -- and "
        "nothing else. Coach the student, following every rule in your instructions.\n\n"
        "```json\n" + json.dumps(summary, indent=2) + "\n```"
    )


def _params(model: str, summary: dict[str, Any]) -> dict[str, Any]:
    """Per-model request params. Haiku 4.5 rejects ``effort`` and we skip thinking
    there; Sonnet/Opus get adaptive thinking + low effort (this is a constrained,
    grounded task, so a light reasoning budget is plenty)."""
    output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": COACH_SCHEMA}}
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": 4000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": _render(summary)}],
        "output_config": output_config,
    }
    if "haiku" not in model:
        params["thinking"] = {"type": "adaptive"}
        output_config["effort"] = "low"
    return params


def _extract_json(resp: Any) -> dict[str, Any]:
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return json.loads(text)


def coach_hand(summary: dict[str, Any], *, client: Any = None,
               model: str = MODEL) -> dict[str, Any]:
    """Run the coach on one hand summary.

    Returns ``hand_id, model, stop_reason, coaching, guardrail_violations``.
    ``coaching`` is None and ``guardrail_violations`` explains why on a refusal.
    Raises only on a hard SDK/network error.
    """
    if client is None:
        import anthropic  # lazy so the module loads without a key
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    resp = client.messages.create(**_params(model, summary))

    result: dict[str, Any] = {
        "hand_id": summary.get("hand_id"),
        "model": resp.model,
        "stop_reason": resp.stop_reason,
        "coaching": None,
        "guardrail_violations": [],
    }
    if resp.stop_reason == "refusal":
        result["guardrail_violations"] = ["model refused (safety classifier)"]
        return result

    coaching = _unescape(_extract_json(resp))
    result["coaching"] = coaching
    result["guardrail_violations"] = check_coaching(coaching)
    return result
