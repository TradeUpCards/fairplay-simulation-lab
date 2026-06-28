"""Assemble the coach's structured input from a hand fixture.

The coach consumes a *hand summary* -- the board, the pot/odds and the student's
action + RAW equity at each decision, and the decisive opponent's style + leak.
This builds that summary from a golden fixture (and, later, from a real hand
record the same way). The opponent's label, leak, and tendency knobs are resolved
from ``leaks.py`` here -- the single source of truth -- so the fixture only has to
name the archetype and the two can never drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .leaks import read_for

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "golden" / "golden_set.json"


def build_summary(fixture: dict[str, Any]) -> dict[str, Any]:
    """Golden fixture -> the structured hand summary the coach is handed."""
    opp = fixture["decisive_opponent"]
    read = read_for(opp["archetype"])
    return {
        "hand_id": fixture["hand_id"],
        "table": fixture["table"],
        "hero": fixture["hero"],
        "board": fixture["board"],
        "pot_bb": fixture["pot_bb"],
        "decisive_opponent": {
            "seat": opp["seat"],
            "style_label": read.style_label,
            "leak": read.leak,
            "exploit": read.exploit,
            # tendencies transcribed from the archetype's knobs (grounding)
            "tendencies": {
                "plays_pct_of_hands": round(read.looseness * 100),
                "raise_first_pct": round(read.pf_aggression * 100),
                "postflop_aggression_0_1": read.postflop_aggression,
                "bluff_pct": round(read.bluff * 100),
                "skill_0_1": read.skill,
            },
        },
        # each decision carries hero_equity_pct = RAW equity vs that many opponents;
        # default opponents_in_hand to 1 (heads-up) when a fixture omits it.
        "decisions": [
            {**d, "opponents_in_hand": d.get("opponents_in_hand", 1)}
            for d in fixture["decisions"]
        ],
    }


def load_golden(path: Path = GOLDEN_PATH) -> list[dict[str, Any]]:
    """The frozen golden set (list of fixtures)."""
    return json.loads(path.read_text(encoding="utf-8"))["hands"]
