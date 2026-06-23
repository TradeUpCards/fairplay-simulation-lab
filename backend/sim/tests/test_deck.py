import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import deck  # noqa: E402


def test_full_deck_is_52_unique():
    d = deck.full_deck()
    assert len(d) == 52 and len(set(d)) == 52


def test_shuffle_is_seed_deterministic():
    a = deck.shuffled(random.Random(7))
    b = deck.shuffled(random.Random(7))
    c = deck.shuffled(random.Random(8))
    assert a == b and a != c and sorted(a) == sorted(deck.full_deck())


def test_derive_is_stable_and_distinct():
    assert deck.derive(42, 1) == deck.derive(42, 1)
    assert deck.derive(42, 1) != deck.derive(42, 2)
