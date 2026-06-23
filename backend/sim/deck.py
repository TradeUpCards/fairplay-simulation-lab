"""Seeded deck — the determinism owner. Cards are 2-char strings 'Ah','Td', etc."""
from __future__ import annotations

import random

RANKS = "23456789TJQKA"
SUITS = "shdc"


def full_deck() -> list[str]:
    return [r + s for r in RANKS for s in SUITS]


def shuffled(rng: random.Random) -> list[str]:
    d = full_deck()
    rng.shuffle(d)
    return d


def derive(master: int, *parts: int) -> int:
    """Stable child seed from a master seed + integer parts (no global RNG)."""
    h = master
    for p in parts:
        h = (h * 1_000_003 + p + 1) & 0x7FFF_FFFF_FFFF_FFFF
    return h
