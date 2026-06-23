import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim.agents import tools  # noqa: E402


def test_pot_odds():
    assert tools.pot_odds(100, 0) == 0.0
    assert abs(tools.pot_odds(150, 50) - 0.25) < 1e-9


def test_equity_aces_dominate_preflop_heads_up():
    eq = tools.hand_equity(["Ah", "As"], [], n_opponents=1,
                           rng=random.Random(1), samples=400)
    assert eq > 0.80                    # AA vs one random ≈ 0.85


def test_equity_made_nuts_on_river_is_one():
    # Royal flush (Ah Kh + Qh Jh Th) — unbeatable.
    eq = tools.hand_equity(["Ah", "Kh"], ["Qh", "Jh", "Th", "2c", "3d"],
                           n_opponents=1, rng=random.Random(1), samples=200)
    assert eq == 1.0


def test_position_buckets():
    assert tools.position(seat=1, button=1, num_players=6) in {"late", "blind", "early", "middle"}


def test_preflop_strength_ranks_hands():
    assert tools.preflop_strength(["Ah", "As"]) == 20.0          # AA = top
    assert tools.preflop_strength(["Ah", "Kh"]) == 12.0          # AKs
    assert tools.preflop_strength(["7d", "2c"]) < 0              # 72o = worst
    assert tools.preflop_strength(["Ah", "As"]) > tools.preflop_strength(["9h", "9s"])
