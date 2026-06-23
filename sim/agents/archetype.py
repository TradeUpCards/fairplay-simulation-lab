"""Archetype = skill% + style knobs. The 7 behavioral archetypes (v1)."""
from __future__ import annotations

import random
from typing import NamedTuple

from sim.agents import policy, tools
from sim.engine.base import Action, DecisionContext


class Archetype(NamedTuple):
    name: str
    skill: float        # 0..1, probability of playing the strong line
    aggression: float   # 0..1, shifts calls/checks toward raises
    tightness: float    # 0..1, preflop range narrowness
    bluff_freq: float   # 0..1, raise frequency with low equity


ARCHETYPES: dict[str, Archetype] = {
    "new":                  Archetype("new", 0.10, 0.30, 0.30, 0.05),
    "recreational":         Archetype("recreational", 0.35, 0.25, 0.20, 0.05),
    "regular":              Archetype("regular", 0.60, 0.50, 0.55, 0.10),
    "grinder":              Archetype("grinder", 0.85, 0.65, 0.80, 0.12),
    "aggressive_predatory": Archetype("aggressive_predatory", 0.90, 0.90, 0.45, 0.30),
    "healthy_anchor":       Archetype("healthy_anchor", 0.75, 0.55, 0.65, 0.10),
    "promo_hunter":         Archetype("promo_hunter", 0.30, 0.20, 0.90, 0.03),
}


# Position widens/tightens the preflop range (late = wider, early = tighter).
_POS_ADJ = {"late": -1.0, "middle": 0.0, "blind": 0.5, "early": 1.0}


class Agent:
    def __init__(self, archetype: Archetype, equity_samples: int = 120):
        self.arch = archetype
        self.equity_samples = equity_samples

    def _preflop_threshold(self, ctx: DecisionContext) -> float:
        # tightness 0..1 -> Chen threshold ~1..9, then a position nudge.
        return 1.0 + self.arch.tightness * 8.0 + _POS_ADJ.get(ctx.position, 0.0)

    def decide(self, ctx: DecisionContext, rng: random.Random) -> Action:
        # Preflop range gate: play only hands strong enough by absolute strength.
        # Unplayable hands fold (or take a free check) without computing equity.
        if ctx.street == "preflop":
            if tools.preflop_strength(ctx.hole) < self._preflop_threshold(ctx):
                return Action("check_call" if ctx.to_call == 0 else "fold")

        equity = tools.hand_equity(ctx.hole, ctx.board, ctx.n_opponents,
                                   rng, samples=self.equity_samples)
        base = (policy.strong_policy(ctx, equity)
                if rng.random() < self.arch.skill
                else policy.beginner_policy(ctx, equity))
        styled = policy.apply_style(base, ctx, equity, self.arch, rng)
        # Attach the equity the agent acted on (for the log/audit); preserve any tag.
        return Action(styled.kind, styled.amount, tag=styled.tag, equity=round(equity, 3))
