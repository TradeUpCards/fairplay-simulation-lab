"""The one parameterized decision policy — instantiated per archetype by knobs.

``ArchetypeAgent.act(obs, rng)`` returns a :class:`Decision`. The same engine
produces a grinder or a recreational depending only on its :class:`Knobs`, so
the differences are auditable (exactly the design in the archetype spec).

Integrity behaviors are layered on top of the base policy:
* ``soft_play_members`` — when every live opponent is a cluster teammate, the
  agent refuses to bet into them and folds marginal spots (gives up EV →
  negative ``soft_play_delta`` downstream).
* ``target_weak`` — extra aggression/bluff vs. flagged-weak opponents.
* ``deterministic`` (bot) — no mixed-strategy coin-flips; ``timing_jitter`` ~0.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .equity import equity_mc, preflop_percentile
from .knobs import Knobs


@dataclass
class Observation:
    street: int                 # 0 preflop, 1 flop, 2 turn, 3 river
    hole: tuple[str, str]
    board: list[str]
    to_call: int                # chips needed to call (0 = can check)
    pot: int
    min_raise_to: int           # min legal total to raise to
    max_raise_to: int           # max (all-in) total to raise to
    my_stack: int
    big_blind: int
    n_active: int               # opponents still live (excluding me)
    live_opponent_ids: tuple[int, ...]
    member_ids: frozenset[int]  # cluster teammates (for soft-play)
    weak_opponent: bool         # is the weakest live opponent flagged weak


@dataclass
class Decision:
    kind: str                   # "fold" | "check_call" | "raise"
    amount: int = 0             # total raise-to amount (for "raise")
    latency_ms: int = 0
    voluntary: bool = False     # put chips in by choice (for vpip)
    is_raise: bool = False      # raised this street (for pfr / aggression)
    is_call: bool = False       # called a bet (for aggression factor)


class ArchetypeAgent:
    def __init__(self, player_id: int, knobs: Knobs, equity_samples: int = 30):
        self.player_id = player_id
        self.k = knobs
        self.equity_samples = equity_samples

    # -- helpers -----------------------------------------------------------
    def _jitter(self, rng: random.Random, base_ms: int = 1600) -> int:
        """Action latency. Low ``timing_jitter`` ⇒ robotic, the bot tell."""
        spread = self.k.timing_jitter
        if spread <= 0.03:
            return base_ms  # flat, near-uniform => high timing_regularity
        return max(150, int(base_ms * (1.0 + rng.uniform(-spread, spread) * 1.5)))

    def _roll(self, rng: random.Random) -> float:
        """Mixed-strategy coin-flip (seeded). Even the bot mixes its *actions*
        (real GTO bots do) — its tell is robotic *timing* (``timing_jitter``≈0),
        not rigid decisions."""
        return rng.random()

    def _all_opponents_are_members(self, obs: Observation) -> bool:
        return bool(obs.live_opponent_ids) and all(
            o in obs.member_ids for o in obs.live_opponent_ids
        )

    def _size_raise(self, obs: Observation, rng: random.Random) -> int:
        # Bet a *fraction of the pot* (~0.35–0.55), NOT pot-sized+ — this keeps
        # aggression frequency (→ AF) high without ballooning pots into constant
        # all-ins, so stacks bleed gradually and play-time stays realistic.
        frac = 0.25 + self.k.sizing * 0.22
        if not self.k.deterministic:
            frac *= 1.0 + rng.uniform(-0.12, 0.12)
        raise_to = obs.to_call + (obs.pot + obs.to_call) * frac
        # cap a single raise at ~1/3 stack so pots stay small and per-hand
        # variance can't drown the skill edge
        cap = obs.to_call + obs.my_stack * 0.33
        target = min(raise_to, cap)
        amount = int(round(max(obs.min_raise_to, min(obs.max_raise_to, target))))
        return max(obs.min_raise_to, min(obs.max_raise_to, amount))

    # -- main --------------------------------------------------------------
    def act(self, obs: Observation, rng: random.Random) -> Decision:
        lat = self._jitter(rng)
        soft = self.k.soft_play_members and self._all_opponents_are_members(obs)
        if obs.street == 0:
            d = self._preflop(obs, rng, soft)
        else:
            d = self._postflop(obs, rng, soft)
        d.latency_ms = lat
        return d

    def _preflop(self, obs: Observation, rng: random.Random, soft: bool) -> Decision:
        pct = preflop_percentile(obs.hole)
        # looseness ≈ vpip target, pf_aggression ≈ pfr target (by construction)
        enter = 1.0 - self.k.looseness
        raise_thr = 1.0 - self.k.pf_aggression
        # small seeded wobble so the boundary isn't robotic (bots: none)
        wobble = 0.0 if self.k.deterministic else (rng.random() - 0.5) * 0.06
        pct_eff = pct + wobble

        if soft:  # never raise into a teammate; just see flops cheaply
            if obs.to_call == 0:
                return Decision("check_call", is_call=False)
            if pct_eff >= enter:
                return Decision("check_call", voluntary=True, is_call=True)
            return Decision("fold")

        if pct_eff >= raise_thr and obs.max_raise_to > obs.min_raise_to:
            return Decision(
                "raise", amount=self._size_raise(obs, rng),
                voluntary=True, is_raise=True,
            )
        if pct_eff >= enter:
            if obs.to_call == 0:
                # limp: voluntary money in only if there's a blind to match;
                # a free BB check is not vpip.
                return Decision("check_call", voluntary=False, is_call=False)
            return Decision("check_call", voluntary=True, is_call=True)
        if obs.to_call == 0:
            return Decision("check_call", voluntary=False)  # free check
        return Decision("fold")

    def _postflop(self, obs: Observation, rng: random.Random, soft: bool) -> Decision:
        eq = equity_mc(obs.hole, obs.board, obs.n_active, rng, self.equity_samples)
        # skill: low-skill agents misjudge equity (noisier, slightly optimistic)
        if not self.k.deterministic:
            eq += (rng.random() - 0.5) * (1.0 - self.k.skill) * 0.5
        eq = min(1.0, max(0.0, eq))

        if soft:  # check down, never barrel a teammate, fold to pressure
            if obs.to_call == 0:
                return Decision("check_call")
            return Decision("check_call", is_call=True) if eq > 0.80 else Decision("fold")

        aggr = self.k.postflop_aggression
        # value-heavy: keep aggression frequency (AF) but bluff sparingly, so a
        # competent table extracts from light-calling stations instead of spewing
        bluff = self.k.bluff * 0.5
        if obs.weak_opponent and self.k.target_weak:
            # exploit the fish: value-bet it relentlessly, DON'T bluff it (a
            # calling station catches bluffs — you beat it by betting value)
            aggr = min(1.0, aggr + 0.12)
            bluff *= 0.30

        if obs.to_call > 0:
            pot_odds = obs.to_call / (obs.pot + obs.to_call)
            # Commitment discipline keeps variance low so the skill edge shows:
            # the station calls LIGHT on small bets (pays off a little, every hand
            # = a steady leak) but folds to BIG bets without real equity (no light
            # stack-offs). High skill folds correctly throughout.
            big_bet = obs.to_call > obs.my_stack * 0.28
            margin = 0.05 if big_bet else -(1.0 - self.k.skill) * 0.14
            if eq >= pot_odds + margin:
                # value: aggressive archetypes mostly raise rather than flat-call
                # (calls are the AF denominator, so heavy callers read as passive)
                if self._roll(rng) < min(1.0, aggr * 1.7 * (0.5 + eq)) and obs.max_raise_to > obs.min_raise_to:
                    return Decision("raise", amount=self._size_raise(obs, rng), is_raise=True)
                return Decision("check_call", is_call=True)
            # behind: occasional bluff-raise, else fold
            if self._roll(rng) < bluff * aggr and obs.max_raise_to > obs.min_raise_to:
                return Decision("raise", amount=self._size_raise(obs, rng), is_raise=True)
            return Decision("fold")

        # no bet to us — bet or check
        bet_p = aggr * (0.55 + 0.65 * eq) + bluff * (1.0 - eq)
        if self._roll(rng) < bet_p and obs.max_raise_to > obs.min_raise_to:
            return Decision("raise", amount=self._size_raise(obs, rng), is_raise=True)
        return Decision("check_call")
