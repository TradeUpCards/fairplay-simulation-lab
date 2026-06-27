"""The bot roster for the training game — distinct *styles*, not just strengths.

Each style is a playsim ``Knobs`` vector driving the shared ``ArchetypeAgent``
brain, so the bot a human faces is the *same* engine the FairPlay sim uses (and
the same seam the RL bot will plug into). We reuse playsim's calibrated
archetypes where they fit and add a couple of classic table characters (Rock,
Calling Station) that the lab wants for teaching.
"""
from __future__ import annotations

from dataclasses import dataclass

from playsim.agent import ArchetypeAgent
from playsim.knobs import ARCHETYPES, Knobs


# Difficulty tiers — how hard the style is to beat (1 easiest .. 4 hardest).
DIFFICULTY_LABELS = {1: "Beginner", 2: "Intermediate", 3: "Advanced", 4: "Expert"}


@dataclass(frozen=True)
class BotStyle:
    key: str
    name: str
    blurb: str          # the teaching hook — what the player should learn to exploit
    knobs: Knobs
    difficulty: int = 2  # 1 Beginner .. 4 Expert


# Custom table characters not in the sim's archetype set (the sim has no pure
# "rock" or "station" — those are teaching personas for the game).
_ROCK = Knobs("rock", looseness=0.13, pf_aggression=0.10, postflop_aggression=0.40,
              sizing=0.50, skill=0.62, bluff=0.02, timing_jitter=0.5)
_STATION = Knobs("station", looseness=0.55, pf_aggression=0.05, postflop_aggression=0.12,
                 sizing=0.40, skill=0.25, bluff=0.0, timing_jitter=0.8)

BOT_STYLES: dict[str, BotStyle] = {
    "rock": BotStyle(
        "rock", "The Rock",
        "Tight and passive — folds far too much. Steal relentlessly; fold to its rare aggression.",
        _ROCK, difficulty=1),
    "station": BotStyle(
        "station", "The Calling Station",
        "Calls too wide and almost never bluffs. Stop bluffing; bet your value thin and often.",
        _STATION, difficulty=1),
    "maniac": BotStyle(
        "maniac", "The Maniac",
        "Loose, hyper-aggressive, high bluff. Tighten up and let it bet into your strong hands.",
        ARCHETYPES["aggressive_predatory"], difficulty=2),
    "grinder": BotStyle(
        "grinder", "The Grinder",
        "Selective, positional, value-heavy. Respect its raises; don't pay it off light.",
        ARCHETYPES["grinder"], difficulty=3),
    "solver": BotStyle(
        "solver", "The Solver-Like",
        "Balanced and hard to exploit — the benchmark. Tiny mistakes get punished.",
        ARCHETYPES["solver_like"], difficulty=4),
}


def build_bot(style_key: str, player_id: int, equity_samples: int = 30) -> ArchetypeAgent:
    """Instantiate the heuristic bot for a style behind the standard act() seam."""
    style = BOT_STYLES[style_key]
    return ArchetypeAgent(player_id, style.knobs, equity_samples=equity_samples)


def style_roster() -> list[dict]:
    """UI-facing roster (no engine objects leak out)."""
    return [{"key": s.key, "name": s.name, "blurb": s.blurb,
             "difficulty": s.difficulty, "tier": DIFFICULTY_LABELS[s.difficulty]}
            for s in BOT_STYLES.values()]
