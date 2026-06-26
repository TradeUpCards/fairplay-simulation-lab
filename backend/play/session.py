"""A single-human 6-max play session.

Ties the three reused pieces together into one object a web surface can drive:
the pausable engine hook (``playsim.interactive``), per-decision equity
(``playsim.equity``), and the AI coach (``backend.coach``). Bots are seeded and
deterministic; the human is the only nondeterministic input.

Flow: construct -> ``state()`` describes whose turn it is and the legal actions ->
``act(...)`` submits the human's move and advances the bots -> when the hand
completes, the session computes the human's equity at each of their decisions,
picks the decisive opponent, and assembles the coach summary (the SAME shape as the
golden fixtures, so the exact coach proven in Phase 1 runs unchanged). ``coaching()``
makes the one live coach call.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# playsim is its own top-level package on disk; put it on the path so the engine,
# equity, and the interactive hook import cleanly alongside the backend packages.
_PLAYSIM = Path(__file__).resolve().parents[2] / "playsim"
if str(_PLAYSIM) not in sys.path:
    sys.path.insert(0, str(_PLAYSIM))

from playsim.agent import ArchetypeAgent, Decision, Observation  # noqa: E402
from playsim.equity import equity_mc  # noqa: E402
from playsim.interactive import InteractiveHand  # noqa: E402
from playsim.knobs import knobs_for  # noqa: E402

from coach.coach import MODEL as COACH_MODEL, coach_hand  # noqa: E402
from coach.summary import build_summary  # noqa: E402

_STREETS = ("preflop", "flop", "turn", "river")
# Static seat ring (fixed button) -- positions are cosmetic for v1.
_POSITIONS = ("BTN", "SB", "BB", "UTG", "MP", "CO")
_DEFAULT_BOTS = ["recreational", "aggressive_predatory", "promo_hunter",
                 "grinder", "regular"]
_EQUITY_SAMPLES = 2000


@dataclass
class LegalActions:
    can_fold: bool
    can_check: bool
    can_call: bool
    call_chips: int
    can_raise: bool
    min_raise_to: int
    max_raise_to: int


@dataclass
class PlayState:
    hand_id: int
    complete: bool
    hero_seat: int
    hero_hole: Optional[tuple[str, str]]
    board: list[str]
    street: str
    pot: int
    big_blind: int
    to_call: int
    legal: Optional[LegalActions]
    opponents: list[dict[str, Any]]   # [{seat, archetype, style_label}]
    coaching: Optional[dict[str, Any]] = None


@dataclass
class _HeroDecision:
    obs: Observation
    action_str: str


class PlaySession:
    def __init__(
        self,
        *,
        hero_seat: int = 2,
        bots: Optional[list[str]] = None,
        stack_bb: int = 100,
        sb: int = 1,
        bb: int = 2,
        seed: int = 0,
        hand_id: int = 1,
    ):
        bots = list(bots or _DEFAULT_BOTS)
        if len(bots) != 5:
            raise ValueError("a 6-max session needs exactly 5 bot archetypes")
        self.hero_seat = hero_seat
        self.bb = bb
        self.hand_id = hand_id
        self.seat_player_ids = list(range(1, 7))
        self.rng = random.Random(seed)
        self._equity_rng = random.Random((seed ^ 0x5151) & 0xFFFFFFFF)

        agents: list[Any] = []
        self.seat_archetype: dict[int, str] = {}
        bot_it = iter(bots)
        for seat, pid in enumerate(self.seat_player_ids):
            if seat == hero_seat:
                agents.append(None)
                self.seat_archetype[seat] = "human"
            else:
                arch = next(bot_it)
                agents.append(ArchetypeAgent(pid, knobs_for(arch)))
                self.seat_archetype[seat] = arch
        self._pid_archetype = {
            pid: self.seat_archetype[seat]
            for seat, pid in enumerate(self.seat_player_ids)
        }

        stacks = [stack_bb * bb] * 6
        self.hand = InteractiveHand(
            human_seat=hero_seat, seat_agents=agents,
            seat_player_ids=self.seat_player_ids, seat_stacks=stacks,
            sb=sb, bb=bb, rng=self.rng, hand_id=hand_id,
            members_by_player={}, weak_player_ids=frozenset(),
        )
        self._decisions: list[_HeroDecision] = []
        self._hero_hole: Optional[tuple[str, str]] = None
        self._coaching: Optional[dict[str, Any]] = None

        self._obs: Optional[Observation] = self.hand.start()
        if self._obs is not None:
            self._hero_hole = self._obs.hole

    # ------------------------------------------------------------- state ---
    def _legal(self, obs: Observation) -> LegalActions:
        return LegalActions(
            can_fold=obs.to_call > 0,
            can_check=obs.to_call == 0,
            can_call=obs.to_call > 0,
            call_chips=obs.to_call,
            can_raise=obs.max_raise_to > obs.min_raise_to,
            min_raise_to=obs.min_raise_to,
            max_raise_to=obs.max_raise_to,
        )

    def _opponents(self) -> list[dict[str, Any]]:
        from coach.leaks import read_for
        out = []
        for seat, arch in self.seat_archetype.items():
            if seat == self.hero_seat:
                continue
            try:
                label = read_for(arch).style_label
            except KeyError:
                label = arch
            out.append({"seat": seat + 1, "archetype": arch, "style_label": label})
        return out

    def state(self) -> PlayState:
        if self.hand.complete:
            rec = self.hand.record
            return PlayState(
                hand_id=self.hand_id, complete=True, hero_seat=self.hero_seat,
                hero_hole=self._hero_hole, board=list(rec.board) if rec else [],
                street=_STREETS[min(3, (len(rec.board) - 2) if rec and rec.board else 0)]
                if rec and rec.board else "preflop",
                pot=int(rec.pot_bb * self.bb) if rec else 0, big_blind=self.bb,
                to_call=0, legal=None, opponents=self._opponents(),
                coaching=self._coaching,
            )
        obs = self._obs
        assert obs is not None
        return PlayState(
            hand_id=self.hand_id, complete=False, hero_seat=self.hero_seat,
            hero_hole=obs.hole, board=list(obs.board), street=_STREETS[obs.street],
            pot=obs.pot, big_blind=self.bb, to_call=obs.to_call,
            legal=self._legal(obs), opponents=self._opponents(),
        )

    # -------------------------------------------------------------- act ---
    def _action_str(self, kind: str, to_call: int, amount: int) -> str:
        if kind == "fold":
            return "fold"
        if kind == "raise":
            return f"raise to {round(amount / self.bb, 1)}bb"
        if to_call > 0:
            return f"call {round(to_call / self.bb, 1)}bb"
        return "check"

    def act(self, kind: str, amount: int = 0) -> PlayState:
        """Submit the human's move (kind: fold|check|call|raise; amount = raise-to chips)."""
        if self.hand.complete:
            raise RuntimeError("hand is already complete")
        obs = self._obs
        assert obs is not None
        self._decisions.append(_HeroDecision(obs, self._action_str(kind, obs.to_call, amount)))

        if kind == "fold":
            decision = Decision("fold")
        elif kind == "raise":
            decision = Decision("raise", amount=amount, is_raise=True,
                                voluntary=(obs.street == 0))
        else:  # check / call
            decision = Decision("check_call", is_call=obs.to_call > 0,
                                voluntary=(obs.street == 0 and obs.to_call > 0))

        self._obs = self.hand.submit(decision)
        if self.hand.complete:
            self._build_summary()
        return self.state()

    # --------------------------------------------------- coach assembly ---
    def _decisive_opponent(self) -> tuple[int, str]:
        """The opponent the human's biggest decision was against: the live opponent at
        the most expensive call, broken toward the most aggressive archetype."""
        paid = [d for d in self._decisions if d.obs.to_call > 0] or self._decisions
        target = max(paid, key=lambda d: d.obs.to_call)
        live = list(target.obs.live_opponent_ids) or [
            pid for pid in self.seat_player_ids
            if self._pid_archetype[pid] != "human"
        ]
        # most aggressive live opponent = likeliest bettor / the decisive read
        dec_pid = max(live, key=lambda pid: knobs_for(self._pid_archetype[pid]).postflop_aggression)
        seat = self.seat_player_ids.index(dec_pid)
        return seat, self._pid_archetype[dec_pid]

    def _build_summary(self) -> None:
        if not self._decisions:
            self._summary = None
            return
        dec_seat, dec_arch = self._decisive_opponent()
        decisions = []
        for d in self._decisions:
            o = d.obs
            eq = equity_mc(o.hole, list(o.board), max(1, o.n_active),
                           self._equity_rng, _EQUITY_SAMPLES)
            decisions.append({
                "street": _STREETS[o.street],
                "board": list(o.board),
                "pot_bb": round(o.pot / self.bb, 1),
                "to_call_bb": round(o.to_call / self.bb, 1),
                "hero_action": d.action_str,
                "hero_equity_pct": round(eq * 100, 1),
                "context": "",
            })
        rec = self.hand.record
        fixture = {
            "hand_id": f"live-{self.hand_id}",
            "table": {"max_seats": 6, "big_blind_chips": self.bb},
            "hero": {"hole": list(self._hero_hole), "position": _POSITIONS[self.hero_seat]},
            "decisive_opponent": {"seat": dec_seat + 1, "archetype": dec_arch},
            "board": list(rec.board) if rec else [],
            "pot_bb": rec.pot_bb if rec else 0.0,
            "decisions": decisions,
        }
        self._fixture = fixture
        self._summary = build_summary(fixture)

    @property
    def summary(self) -> Optional[dict[str, Any]]:
        """The assembled coach input for the completed hand (None if no human decision)."""
        return getattr(self, "_summary", None)

    def coaching(self, *, client: Any = None, model: str = COACH_MODEL) -> Optional[dict[str, Any]]:
        """Run the coach on the completed hand (one live call). Cached."""
        if not self.hand.complete:
            raise RuntimeError("hand is not complete yet")
        if self._coaching is not None:
            return self._coaching
        if self.summary is None:
            self._coaching = {"coaching": None, "note": "no decision to coach"}
            return self._coaching
        self._coaching = coach_hand(self.summary, client=client, model=model)
        return self._coaching
