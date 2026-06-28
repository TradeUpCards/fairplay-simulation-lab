"""Archetype -> exploitable-tendency map: the coach's *grounded* opponent reads.

The training coach must cite the **specific** leak of the **specific** opponent
type the human was up against -- not generic advice ("you should have folded").
That leak is not invented by the LLM. It is a structured fact about the archetype,
read from here, and handed to the coach in the hand summary. Every claim the coach
makes about an opponent traces back to this table.

Each entry pairs the human-authored *teaching* read with the quantitative knob
values it derives from (``playsim/playsim/knobs.py`` -- the canonical source). The
knob numbers are transcribed here as grounding constants (and cross-checked in
``tests/test_leaks_grounding``) so the coach can say "calls ~38% of hands" without
the LLM guessing the number.

``style_label`` is the player-facing name the trainee guesses in the type-ID round;
``leak`` is the one-line exploitable tendency; ``exploit`` is how a studying player
attacks it. No archetype is "unbeatable" -- ``solver_like`` is a *label only*, never
a GTO/solved claim (PRD acceptance #6).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpponentRead:
    archetype: str
    style_label: str          # player-facing type name (the type-ID answer)
    leak: str                 # the specific exploitable tendency, one line
    exploit: str              # how a studying player attacks it
    # grounding constants, transcribed from knobs.ARCHETYPES (the source of truth)
    looseness: float          # ~ vpip: fraction of hands played
    pf_aggression: float      # ~ pfr: raise-first frequency
    postflop_aggression: float
    bluff: float
    skill: float


# Keyed by the engine archetype name (knobs.ARCHETYPES). The PRD's product-facing
# type names (rock, maniac, calling station, ...) map onto these archetypes.
READS: dict[str, OpponentRead] = {
    "recreational": OpponentRead(
        "recreational", "calling station",
        leak="Calls far too wide and too light, almost never raises, and pays off "
             "value down to small bets -- a steady leak rather than a big mistake.",
        exploit="Bet your strong hands relentlessly and size up for thin value; do "
                "NOT bluff -- a station catches bluffs by calling, so you beat it by "
                "betting real hands, not by representing them.",
        looseness=0.38, pf_aggression=0.12, postflop_aggression=0.30, bluff=0.04, skill=0.30,
    ),
    "new": OpponentRead(
        "new", "beginner / fish",
        leak="Plays too many hands passively, makes obvious sizing tells, and tilts "
             "or quits after a loss -- inconsistent and exploitable.",
        exploit="Value-bet patiently and let them make the mistakes; avoid fancy "
                "bluffs they won't read, and apply pressure when they look weak.",
        looseness=0.36, pf_aggression=0.08, postflop_aggression=0.18, bluff=0.02, skill=0.20,
    ),
    "promo_hunter": OpponentRead(
        "promo_hunter", "rock / nit",
        leak="Extremely risk-averse: folds marginal +EV spots, avoids variance, and "
             "only commits chips with a strong holding.",
        exploit="Attack their blinds and bet into them often -- they over-fold. When "
                "a nit finally raises or calls big, believe it and let your weak hands go.",
        looseness=0.30, pf_aggression=0.13, postflop_aggression=0.28, bluff=0.02, skill=0.40,
    ),
    "grinder": OpponentRead(
        "grinder", "grinder / TAG",
        leak="Tight and disciplined preflop (plays ~23% of hands); over-folds to "
             "early aggression and rarely defends light, so their range is readable.",
        exploit="Steal their blinds and 3-bet light in position; but respect a "
                "grinder's postflop barrels -- they bet strong ranges, so fold your "
                "marginal hands to sustained pressure.",
        looseness=0.23, pf_aggression=0.21, postflop_aggression=0.70, bluff=0.14, skill=0.85,
    ),
    "aggressive_predatory": OpponentRead(
        "aggressive_predatory", "maniac / LAG",
        leak="Plays a huge range (~59% of hands) and bluffs far too often (~30% of "
             "weak holdings), barreling streets it shouldn't.",
        exploit="Tighten up, let them bluff into your strong hands, and call down "
                "lighter than usual -- their betting is weighted toward air, so your "
                "medium-strength hands are good far more often than against a TAG.",
        looseness=0.59, pf_aggression=0.45, postflop_aggression=0.92, bluff=0.30, skill=0.80,
    ),
    "regular": OpponentRead(
        "regular", "solid regular",
        leak="Few exploitable leaks; balanced and positionally aware. The main edge "
             "is that they fold to credible aggression in marginal spots.",
        exploit="Don't spew -- pick clear spots, apply pressure in position, and "
                "avoid bluffing into their value range.",
        looseness=0.28, pf_aggression=0.22, postflop_aggression=0.55, bluff=0.10, skill=0.70,
    ),
    "healthy_anchor": OpponentRead(
        "healthy_anchor", "balanced regular",
        leak="Steady and few-leak, neither too loose nor too tight; a tough, "
             "low-variance opponent.",
        exploit="Realize equity, avoid marginal bluffs, and look for position rather "
                "than forcing the action.",
        looseness=0.28, pf_aggression=0.18, postflop_aggression=0.50, bluff=0.08, skill=0.65,
    ),
    "solver_like": OpponentRead(
        "solver_like", "solver-like",
        # NB: "solver-like" is a product LABEL, not a GTO/solved claim (acceptance #6).
        leak="Very strong and well-balanced -- few free chips. Because they bluff "
             "and value-bet at credible frequencies, you can't profitably bluff-catch "
             "or barrel without real equity.",
        exploit="Play tight and straightforward, take position, and don't try to "
                "out-level them -- bluff only with genuine equity and fold-out value, "
                "and pass up thin spots.",
        looseness=0.22, pf_aggression=0.19, postflop_aggression=0.80, bluff=0.18, skill=0.97,
    ),
    "bot_like": OpponentRead(
        "bot_like", "robotic / bot-like",
        leak="Strategically solid but mechanically regular -- balanced lines with "
             "near-constant timing. The tell is the rhythm, not the strategy.",
        exploit="Play solid poker; there is no big strategic leak to attack, so don't "
                "invent one. The read is the consistency itself.",
        looseness=0.24, pf_aggression=0.20, postflop_aggression=0.58, bluff=0.08, skill=0.70,
    ),
}


def read_for(archetype: str) -> OpponentRead:
    """The grounded opponent read for an archetype.

    Raises KeyError for an unknown archetype rather than inventing a read -- the
    coach must never coach against a type it has no structured fact for.
    """
    try:
        return READS[archetype]
    except KeyError:
        raise KeyError(
            f"no coach read for archetype {archetype!r}; known: {sorted(READS)}"
        ) from None
