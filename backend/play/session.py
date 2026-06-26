"""A single-human play session (2-6 handed).

Ties the three reused pieces together into one object a web surface can drive:
the pausable engine hook (``playsim.interactive``), per-decision equity
(``playsim.equity``), and the AI coach (``backend.coach``). Bots are seeded and
deterministic; the human is the only nondeterministic input.

Table size is ``len(bots) + 1`` -- pass 1-5 bots for heads-up through 6-max, so
empty seats just mean fewer players. ``reveal=False`` is "mystery" mode: the
opponents' styles are hidden from the client (the human reads them blind), though
the coach still names them in the post-hand review.

Flow: construct -> ``state()`` describes the table + whose turn + legal actions ->
``act(...)`` submits the human's move and advances the bots -> on completion the
session computes the human's equity at each decision, picks the decisive opponent,
and assembles the coach summary. ``coaching()`` makes the one live coach call.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# playsim is its own top-level package on disk; put it on the path.
_PLAYSIM = Path(__file__).resolve().parents[2] / "playsim"
if str(_PLAYSIM) not in sys.path:
    sys.path.insert(0, str(_PLAYSIM))

from playsim.agent import ArchetypeAgent, Decision, Observation  # noqa: E402
from playsim.equity import equity_mc  # noqa: E402
from playsim.interactive import InteractiveHand  # noqa: E402
from playsim.knobs import ARCHETYPES, knobs_for  # noqa: E402

from coach.coach import MODEL as COACH_MODEL, coach_hand  # noqa: E402
from coach.leaks import read_for  # noqa: E402
from coach.summary import build_summary  # noqa: E402

_STREETS = ("preflop", "flop", "turn", "river")
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
class SeatView:
    seat: int
    label: str                 # "You", the style label, or "Unknown" (mystery)
    archetype: Optional[str]   # None for the hero or in mystery mode
    role: str                  # "BTN" | "SB" | "BB" | ""
    stack_bb: float
    bet_bb: float
    folded: bool
    is_hero: bool
    to_act: bool


@dataclass
class LogEntry:
    seat: int
    street: str
    action: str
    amount_bb: float


@dataclass
class PlayState:
    hand_id: int
    complete: bool
    hero_seat: int
    max_seats: int
    mystery: bool
    hero_hole: Optional[tuple[str, str]]
    board: list[str]
    street: str
    pot: int
    big_blind: int
    to_call: int
    legal: Optional[LegalActions]
    seats: list[SeatView]
    log: list[LogEntry]
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
        reveal: bool = True,
        stack_bb: int = 100,
        sb: int = 1,
        bb: int = 2,
        seed: int = 0,
        hand_id: int = 1,
    ):
        # None => default mix; an explicit list has its empty/None seats dropped
        # (so all-empty is an error, not a silent fall-back to the default).
        bots = list(_DEFAULT_BOTS) if bots is None else [b for b in bots if b]
        if not (1 <= len(bots) <= 5):
            raise ValueError("need 1-5 bot archetypes (2-6 players including the human)")
        unknown = [b for b in bots if b not in ARCHETYPES]
        if unknown:
            raise ValueError(f"unknown archetype(s): {unknown}")

        n = len(bots) + 1
        self.max_seats = n
        self.hero_seat = max(0, min(hero_seat, n - 1))
        self.reveal = reveal
        self.bb = bb
        self.hand_id = hand_id
        self.seat_player_ids = list(range(1, n + 1))
        self.rng = random.Random(seed)
        self._equity_rng = random.Random((seed ^ 0x5151) & 0xFFFFFFFF)

        agents: list[Any] = []
        self.seat_archetype: dict[int, str] = {}
        bot_it = iter(bots)
        for seat, pid in enumerate(self.seat_player_ids):
            if seat == self.hero_seat:
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

        stacks = [stack_bb * bb] * n
        self.hand = InteractiveHand(
            human_seat=self.hero_seat, seat_agents=agents,
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
        # blind/button seats are fixed for the hand; capture them once.
        v = self.hand.view or {}
        self._roles = {
            "button_seat": v.get("button_seat", n - 1),
            "sb_seat": v.get("sb_seat", 0),
            "bb_seat": v.get("bb_seat", 1 % n),
        }

    # ------------------------------------------------------------ labels ---
    def _label(self, seat: int) -> str:
        if seat == self.hero_seat:
            return "You"
        if not self.reveal:
            return "Unknown"
        try:
            return read_for(self.seat_archetype[seat]).style_label
        except KeyError:
            return self.seat_archetype.get(seat, f"Seat {seat + 1}")

    def _client_archetype(self, seat: int) -> Optional[str]:
        if seat == self.hero_seat or not self.reveal:
            return None
        return self.seat_archetype.get(seat)

    def _role(self, seat: int) -> str:
        if seat == self._roles["button_seat"]:
            return "BTN"
        if seat == self._roles["sb_seat"]:
            return "SB"
        if seat == self._roles["bb_seat"]:
            return "BB"
        return ""

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

    def _seats_live(self, view: dict, to_act_seat: Optional[int]) -> list[SeatView]:
        out = []
        for sv in view["seats"]:
            s = sv["seat"]
            out.append(SeatView(
                seat=s, label=self._label(s), archetype=self._client_archetype(s),
                role=self._role(s), stack_bb=sv["stack_bb"], bet_bb=sv["bet_bb"],
                folded=sv["folded"], is_hero=(s == self.hero_seat),
                to_act=(s == to_act_seat),
            ))
        return out

    def _seats_complete(self) -> list[SeatView]:
        rec = self.hand.record
        out = []
        folded_seats = {
            self.seat_player_ids.index(a.player_id)
            for a in (rec.actions if rec else []) if a.action == "fold"
        }
        for s, pid in enumerate(self.seat_player_ids):
            final = (rec.starting_stacks.get(pid, 0) + rec.payoffs.get(pid, 0)) if rec else 0
            out.append(SeatView(
                seat=s, label=self._label(s), archetype=self._client_archetype(s),
                role=self._role(s), stack_bb=round(final / self.bb, 1), bet_bb=0.0,
                folded=s in folded_seats, is_hero=(s == self.hero_seat), to_act=False,
            ))
        return out

    def _log_live(self, view: dict) -> list[LogEntry]:
        return [
            LogEntry(seat=e["seat"], street=_STREETS[min(3, e["street"])],
                     action=e["action"], amount_bb=e["amount_bb"])
            for e in view["log"]
        ]

    def _log_complete(self) -> list[LogEntry]:
        rec = self.hand.record
        if not rec:
            return []
        pid_seat = {pid: i for i, pid in enumerate(self.seat_player_ids)}
        return [
            LogEntry(seat=pid_seat[a.player_id], street=_STREETS[min(3, a.street)],
                     action=a.action, amount_bb=round(a.amount / self.bb, 1))
            for a in rec.actions
        ]

    def state(self) -> PlayState:
        if self.hand.complete:
            rec = self.hand.record
            return PlayState(
                hand_id=self.hand_id, complete=True, hero_seat=self.hero_seat,
                max_seats=self.max_seats, mystery=not self.reveal,
                hero_hole=self._hero_hole, board=list(rec.board) if rec else [],
                street="river", pot=int(rec.pot_bb * self.bb) if rec else 0,
                big_blind=self.bb, to_call=0, legal=None,
                seats=self._seats_complete(), log=self._log_complete(),
                coaching=self._coaching,
            )
        obs = self._obs
        assert obs is not None
        view = self.hand.view or {"seats": [], "log": []}
        return PlayState(
            hand_id=self.hand_id, complete=False, hero_seat=self.hero_seat,
            max_seats=self.max_seats, mystery=not self.reveal,
            hero_hole=obs.hole, board=list(obs.board), street=_STREETS[obs.street],
            pot=obs.pot, big_blind=self.bb, to_call=obs.to_call,
            legal=self._legal(obs), seats=self._seats_live(view, self.hero_seat),
            log=self._log_live(view),
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
        else:
            decision = Decision("check_call", is_call=obs.to_call > 0,
                                voluntary=(obs.street == 0 and obs.to_call > 0))

        self._obs = self.hand.submit(decision)
        if self.hand.complete:
            self._build_summary()
        return self.state()

    # --------------------------------------------------- coach assembly ---
    def _decisive_opponent(self) -> tuple[int, str]:
        paid = [d for d in self._decisions if d.obs.to_call > 0] or self._decisions
        target = max(paid, key=lambda d: d.obs.to_call)
        live = list(target.obs.live_opponent_ids) or [
            pid for pid in self.seat_player_ids if self._pid_archetype[pid] != "human"
        ]
        dec_pid = max(live, key=lambda pid: knobs_for(self._pid_archetype[pid]).postflop_aggression)
        return self.seat_player_ids.index(dec_pid), self._pid_archetype[dec_pid]

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
            "table": {"max_seats": self.max_seats, "big_blind_chips": self.bb},
            "hero": {"hole": list(self._hero_hole), "position": self._role(self.hero_seat) or "—"},
            "decisive_opponent": {"seat": dec_seat + 1, "archetype": dec_arch},
            "board": list(rec.board) if rec else [],
            "pot_bb": rec.pot_bb if rec else 0.0,
            "decisions": decisions,
        }
        self._fixture = fixture
        self._summary = build_summary(fixture)

    @property
    def summary(self) -> Optional[dict[str, Any]]:
        return getattr(self, "_summary", None)

    def coaching(self, *, client: Any = None, model: str = COACH_MODEL) -> Optional[dict[str, Any]]:
        if not self.hand.complete:
            raise RuntimeError("hand is not complete yet")
        if self._coaching is not None:
            return self._coaching
        if self.summary is None:
            self._coaching = {"coaching": None, "note": "no decision to coach"}
            return self._coaching
        self._coaching = coach_hand(self.summary, client=client, model=model)
        return self._coaching
