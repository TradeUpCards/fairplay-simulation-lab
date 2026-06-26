"""Latency audit for the coach workflow -- where the time actually goes.

Breaks the post-hand coaching latency into its parts:
  * local equity (Monte-Carlo per decision) + summary assembly -- pure compute, no LLM.
  * the LLM call, which dominates: time-to-first-token (TTFT, where adaptive thinking
    hides) vs total generation, plus input/output token counts, swept across
    model / thinking / effort / structured-output.

TTFT is measured by streaming and timing the first text delta. With thinking on, the
model thinks before emitting text, so TTFT captures that delay.

Run:  python -m coach.bench            (needs ANTHROPIC_API_KEY)
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path
from typing import Any

from coach.coach import _render
from coach.prompt import COACH_SCHEMA, SYSTEM_PROMPT
from coach.summary import build_summary, load_golden


def _params(model: str, summary: dict, *, thinking: bool, effort: str | None,
            structured: bool = True) -> dict[str, Any]:
    p: dict[str, Any] = {
        "model": model, "max_tokens": 4000, "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": _render(summary)}],
    }
    oc: dict[str, Any] = {}
    if structured:
        oc["format"] = {"type": "json_schema", "schema": COACH_SCHEMA}
    if thinking:
        p["thinking"] = {"type": "adaptive"}
    if effort:
        oc["effort"] = effort
    if oc:
        p["output_config"] = oc
    return p


def time_llm(client: Any, summary: dict, **cfg: Any) -> dict[str, Any]:
    """One streamed call; returns TTFT, total, and token counts."""
    params = _params(summary=summary, **cfg)
    t0 = time.perf_counter()
    ttft = None
    with client.messages.stream(**params) as stream:
        for _ in stream.text_stream:
            if ttft is None:
                ttft = time.perf_counter() - t0
        msg = stream.get_final_message()
    total = time.perf_counter() - t0
    u = msg.usage
    return {"ttft": ttft or total, "total": total,
            "in": u.input_tokens, "out": u.output_tokens}


def time_local() -> float:
    """Average equity Monte-Carlo cost per decision -- the only non-trivial local work
    in assembling the coach summary."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "playsim"))
    from playsim.equity import equity_mc

    rng = random.Random(0)
    spots = [
        (("Ts", "Td"), ["Ah", "6c", "3d", "8s", "Kc"], 1),
        (("9h", "9c"), ["Kc", "Qd", "6s", "3h", "2c"], 1),
        (("Jh", "Th"), [], 4),
    ]
    t0 = time.perf_counter()
    for hole, board, n in spots:
        equity_mc(hole, board, n, rng, 2000)
    return (time.perf_counter() - t0) / len(spots)


def main() -> int:
    import anthropic

    client = anthropic.Anthropic()
    summary = build_summary({h["hand_id"]: h for h in load_golden()}["G5-grinder-fold"])

    print(f"\nLocal equity (Monte-Carlo, 2000 samples): "
          f"{time_local() * 1000:.0f} ms/decision  (a hand has ~1-4 decisions)\n")

    configs = [
        ("sonnet + adaptive thinking + effort=low (eval)", dict(model="claude-sonnet-4-6", thinking=True, effort="low")),
        ("sonnet + adaptive thinking (no effort)", dict(model="claude-sonnet-4-6", thinking=True, effort=None)),
        ("sonnet, NO thinking", dict(model="claude-sonnet-4-6", thinking=False, effort=None)),
        ("sonnet, NO thinking, NO structured out", dict(model="claude-sonnet-4-6", thinking=False, effort=None, structured=False)),
        ("haiku, NO thinking (live default? no)", dict(model="claude-haiku-4-5", thinking=False, effort=None)),
    ]
    print(f"{'config':50} {'TTFT':>6} {'total':>7} {'in':>6} {'out':>6}")
    print("-" * 80)
    for label, cfg in configs:
        try:
            time_llm(client, summary, **cfg)            # warm (schema compile + connection)
            r = time_llm(client, summary, **cfg)        # measured
            print(f"{label:50} {r['ttft']:5.1f}s {r['total']:6.1f}s {r['in']:6d} {r['out']:6d}")
        except Exception as e:  # noqa: BLE001
            print(f"{label:50} ERROR: {type(e).__name__}: {e}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
