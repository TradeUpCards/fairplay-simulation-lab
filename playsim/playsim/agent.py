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
    raises_this_street: int = 0  # voluntary raises so far this street (0 = unraised;
    #                              1 = facing an open, 2 = facing a 3-bet, ...)


@dataclass
class Decision:
    kind: str                   # "fold" | "check_call" | "raise"
    amount: int = 0             # total raise-to amount (for "raise")
    latency_ms: int = 0
    voluntary: bool = False     # put chips in by choice (for vpip)
    is_raise: bool = False      # raised this street (for pfr / aggression)
    is_call: bool = False       # called a bet (for aggression factor)


class ArchetypeAgent:
    # Provenance — every corpus this brain produces is attributable to it.
    # RLCard/OpenSpiel/CFR brains are out of MVP scope; the seam + metadata exist
    # now so future brains are tracked.
    agent_model = "archetype-knobs"
    agent_version = "v1"

    def __init__(self, player_id: int, knobs: Knobs, equity_samples: int = 30,
                 pot_discipline: bool = False, aggression: float = 1.0):
        self.player_id = player_id
        self.k = knobs
        self.equity_samples = equity_samples
        # When True, postflop raises require genuine equity and the bar climbs with
        # each re-raise, so marginal hands call instead of starting a war. Opt-in for
        # the single-human training table (sane, readable pots); OFF by default so the
        # calibrated 8-hour population sim — tuned to its own AF targets — is unchanged.
        self.pot_discipline = pot_discipline
        # Table-aggression dial for the training-table difficulty presets: 1.0 = the
        # archetypes' own calibrated aggression; <1 a tighter/quieter table, >1 a
        # looser/splashier "action" table. Every use is a multiply that is an exact
        # no-op at 1.0, so the population sim (which never sets it) is byte-identical.
        self.aggression = aggression

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
        # looseness ≈ vpip target, pf_aggression ≈ pfr target (by construction).
        # Each prior raise demands a MUCH stronger hand to put in another raise, so a
        # hand good enough to open is not good enough to 3-bet/4-bet -- this keeps
        # re-raise wars rare and premium-weighted instead of every decent hand piling
        # in. Calling also tightens once the pot is 3-bet+ (don't peel junk to a 3-bet).
        # Table-aggression widens (or tightens) the entering / raising ranges. Clamped
        # so a splashy table doesn't literally play every hand. At aggression=1.0 the
        # multiply is exact, so the population path is unchanged.
        loosen = min(0.92, self.k.looseness * self.aggression)
        pf_agg = min(0.92, self.k.pf_aggression * self.aggression)
        level = obs.raises_this_street
        enter = 1.0 - loosen + max(0, level - 1) * 0.14
        raise_thr = 1.0 - pf_agg + min(level, 3) * 0.16
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
        ag = self.aggression  # table-aggression dial (1.0 = no-op)
        # value-heavy: keep aggression frequency (AF) but bluff sparingly, so a
        # competent table extracts from light-calling stations instead of spewing
        bluff = self.k.bluff * 0.5 * ag
        if obs.weak_opponent and self.k.target_weak:
            # exploit the fish: value-bet it relentlessly, DON'T bluff it (a
            # calling station catches bluffs — you beat it by betting value)
            aggr = min(1.0, aggr + 0.12)
            bluff *= 0.30

        can_raise = obs.max_raise_to > obs.min_raise_to
        if obs.to_call > 0:
            pot_odds = obs.to_call / (obs.pot + obs.to_call)
            # Commitment discipline keeps variance low so the skill edge shows:
            # the station calls LIGHT on small bets (pays off a little, every hand
            # = a steady leak) but folds to BIG bets without real equity (no light
            # stack-offs). High skill folds correctly throughout.
            big_bet = obs.to_call > obs.my_stack * 0.28
            margin = 0.05 if big_bet else -(1.0 - self.k.skill) * 0.14
            # level = bets/raises already in this street; >=2 means the pot is
            # already re-raised, so only a monster should put in another raise.
            level = obs.raises_this_street
            if eq >= pot_odds + margin:
                if self.pot_discipline:
                    # Raise only with a real edge, and the bar climbs each re-raise so
                    # marginal hands flat-call instead of escalating into all-ins. The
                    # aggression dial lowers the bar / lifts the frequency on splashy
                    # tables (and the reverse on quiet ones).
                    raise_bar = 0.52 + max(0, level - 1) * 0.12 - (ag - 1.0) * 0.12
                    raise_p = max(0.0, aggr * (eq - 0.30)) * ag
                    want_raise = eq >= raise_bar and self._roll(rng) < raise_p
                else:
                    # value: aggressive archetypes mostly raise rather than flat-call
                    # (calls are the AF denominator, so heavy callers read as passive)
                    want_raise = self._roll(rng) < min(1.0, aggr * 1.7 * (0.5 + eq))
                if want_raise and can_raise:
                    return Decision("raise", amount=self._size_raise(obs, rng), is_raise=True)
                return Decision("check_call", is_call=True)
            # behind: occasional bluff-raise (never into an already-raised pot under
            # discipline), else fold
            bluff_ok = not self.pot_discipline or level <= 1
            if bluff_ok and self._roll(rng) < bluff * aggr and can_raise:
                return Decision("raise", amount=self._size_raise(obs, rng), is_raise=True)
            return Decision("fold")

        # no bet to us — bet or check (scaled by the table-aggression dial)
        bet_p = aggr * ag * (0.55 + 0.65 * eq) + bluff * (1.0 - eq)
        if self._roll(rng) < bet_p and obs.max_raise_to > obs.min_raise_to:
            return Decision("raise", amount=self._size_raise(obs, rng), is_raise=True)
        return Decision("check_call")
