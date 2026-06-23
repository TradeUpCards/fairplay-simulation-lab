"""Export hands to a PHH-shaped record (Poker Hand History, uoftcprg/phh-std).

PHH is the open TOML-based hand-history format from the same group as PokerKit.
We emit a PHH-compatible dict per hand (variant ``NT`` = No-limit Texas hold'em)
plus our richer action log, so the output interoperates with the PHH ecosystem
and stays Contract-1 friendly. See https://phh.readthedocs.io.
"""

from __future__ import annotations

from .table import HandRecord


def to_phh_dict(hand: HandRecord, currency: str = "BB") -> dict:
    """A PHH-shaped record for one hand (JSON-serializable)."""
    n = len(hand.seat_player_ids)
    return {
        "variant": "NT",
        "ante_trimming_status": True,
        "antes": [0] * n,
        "blinds_or_straddles": [1, 2] + [0] * (n - 2),
        "min_bet": hand.big_blind,
        "starting_stacks": [
            hand.starting_stacks[pid] for pid in hand.seat_player_ids
        ],
        "players": [f"P-{pid}" for pid in hand.seat_player_ids],
        "seats": list(range(1, n + 1)),
        "_hand_id": hand.hand_id,
        "_board": hand.board,
        "_hole": {f"P-{pid}": list(c) for pid, c in hand.hole.items()},
        "_payoffs_bb": {
            f"P-{pid}": round(v / hand.big_blind, 2)
            for pid, v in hand.payoffs.items()
        },
        "_pot_bb": hand.pot_bb,
        "_actions": [
            {
                "player": f"P-{a.player_id}", "street": a.street,
                "action": a.action, "amount": a.amount, "latency_ms": a.latency_ms,
            }
            for a in hand.actions
        ],
        "fixture_note": (
            "Synthetic PHH-shaped record from playsim (archetype agents + "
            "PokerKit). Sandbox integrity-lab data — not real play."
        ),
    }


def session_to_phh(hands: list[HandRecord]) -> dict:
    return {
        "schema_version": "0.1.0",
        "fixture_note": "playsim session — archetype agents on PokerKit, seeded.",
        "hands": [to_phh_dict(h) for h in hands],
    }
