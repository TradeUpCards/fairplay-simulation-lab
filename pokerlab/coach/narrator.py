"""Optional LLM narrator (Option C) — a plain-English "coach's take" layered *over*
the deterministic EV/equity numbers.

This never replaces the math: it is *fed* the exact per-decision equity, pot-odds,
and EV that ``coach.py`` computed and asked to explain them in 2-3 sentences. It is
fully gated — if the ``anthropic`` SDK isn't installed or ``ANTHROPIC_API_KEY`` isn't
set, ``available()`` is False and the game shows the deterministic coach alone.

    pip install anthropic
    $env:ANTHROPIC_API_KEY = "sk-ant-..."
    $env:POKERLAB_NARRATOR_MODEL = "claude-haiku-4-5-20251001"   # optional; this is the default
"""
from __future__ import annotations

import os

DEFAULT_MODEL = "claude-haiku-4-5-20251001"   # fast + cheap; override via POKERLAB_NARRATOR_MODEL

_SYSTEM = (
    "You are a sharp, encouraging heads-up poker coach. You are given the exact "
    "equity, pot-odds, and EV numbers for one hand your student just played, already "
    "computed for you. Write 2-3 short sentences of plain-English feedback that "
    "reference those numbers. Lead with the biggest EV leak if there is one; otherwise "
    "praise the strongest decision. Never invent facts, cards, or numbers beyond what "
    "you are given. Be concrete and concise — no hedging, no preamble."
)


def available() -> bool:
    """True only if a key is set and the SDK is importable — otherwise the game runs
    the deterministic coach alone."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def _prompt(coaching: dict, bot_name: str) -> str:
    c = coaching
    lines = [f"Opponent: {bot_name or 'the bot'}.",
             f"Your hole cards: {' '.join(c['hole'])}.",
             f"Board: {' '.join(c['board']) or '(folded preflop)'}.",
             f"Villain's actual cards (hindsight, do not scold for these): {' '.join(c['opp_hole'])}.",
             "", "Your decisions (equity = vs a random hand at that moment):"]
    for d in c["decisions"]:
        bits = [f"{d['street_name']} {d['action']}", f"equity {round(d['equity']*100)}%"]
        if d["pot_odds"] is not None:
            bits.append(f"needed {round(d['pot_odds']*100)}%")
        if d["ev_bb"] is not None:
            bits.append(f"EV {d['ev_bb']:+.1f}bb")
        bits.append(f"[{d['verdict']}]")
        lines.append("- " + ", ".join(bits))
    s = c["summary"]
    lines += ["", f"Net result: {c['net_bb']:+.1f}bb. EV left on the table: {s['ev_lost_bb']:.1f}bb.",
              f"Auto-summary: {s['headline']}"]
    return "\n".join(lines)


def narrate(coaching: dict, bot_name: str = "") -> str | None:
    """Return a short natural-language coaching note, or None if unavailable / on error.
    Errors degrade silently — the deterministic coach is always the source of truth."""
    if not available():
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        model = os.environ.get("POKERLAB_NARRATOR_MODEL", DEFAULT_MODEL)
        msg = client.messages.create(
            model=model, max_tokens=200, system=_SYSTEM,
            messages=[{"role": "user", "content": _prompt(coaching, bot_name)}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return text.strip() or None
    except Exception:
        return None
