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
import time
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

from coach.coach import coach_hand  # noqa: E402

# The LLM coaching is non-blocking (the instant grounded review shows first), so the
# live game keeps the higher-quality Sonnet reference model rather than trading down.
LIVE_COACH_MODEL = "claude-sonnet-4-6"
from coach.leaks import read_for  # noqa: E402
from coach.summary import build_summary  # noqa: E402

_STREETS = ("preflop", "flop", "turn", "river")
_DEFAULT_BOTS = ["recreational", "aggressive_predatory", "promo_hunter",
                 "grinder", "regular"]
# Monte-Carlo equity for the coach summary. 2000 samples cost ~2.7s/decision (a
# hidden latency bottleneck found by coach/bench.py); 400 is ~5x faster with ~2-3%
# precision -- plenty for coaching, and it makes the instant review actually instant.
_EQUITY_SAMPLES = 400


def _middle_names(k: int) -> list[str]:
    """Position names for the non-blind, non-button seats, in preflop action order
    (UTG acts first, CO is last before the button)."""
    presets = {1: ["UTG"], 2: ["UTG", "CO"], 3: ["UTG", "HJ", "CO"],
               4: ["UTG", "UTG+1", "HJ", "CO"]}
    if k <= 0:
        return []
    if k in presets:
        return presets[k]
    return ["UTG"] + [f"UTG+{i}" for i in range(1, k - 2)] + ["HJ", "CO"]


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
    hole: Optional[list[str]] = None   # the hero always; opponents only at showdown
    won: bool = False                  # positive payoff at showdown


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
    review: Optional[dict[str, Any]] = None    # instant, LLM-free grounded feedback
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
        button_seat: Optional[int] = None,
        stack_bb: int = 100,
        sb: int = 1,
        bb: int = 2,
        seed: int = 0,
        hand_id: int = 1,
        aggression: float = 1.0,
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
                agents.append(ArchetypeAgent(
                    pid, knobs_for(arch), pot_discipline=True, aggression=aggression))
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
            button_seat=None if button_seat is None else button_seat % n,
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
        # a poker position for EVERY seat (BTN/SB/BB/UTG/HJ/CO/…) -- the anchor that
        # ties the action log to the table seats in action order.
        btn, sb_, bb_ = (self._roles["button_seat"], self._roles["sb_seat"],
                         self._roles["bb_seat"])
        positions = {btn: "BTN", sb_: "SB", bb_: "BB"}
        order = [(bb_ + 1 + i) % n for i in range(n)]
        middle = [s for s in order if s not in positions]
        for s, name in zip(middle, _middle_names(len(middle))):
            positions[s] = name
        self._positions = positions

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
        return self._positions.get(seat, "")

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
                hole=list(self._hero_hole) if (s == self.hero_seat and self._hero_hole) else None,
            ))
        return out

    def _seats_complete(self) -> list[SeatView]:
        rec = self.hand.record
        showdown = set(rec.showdown_player_ids) if rec else set()   # empty unless 2+ saw it
        folded_seats = {
            self.seat_player_ids.index(a.player_id)
            for a in (rec.actions if rec else []) if a.action == "fold"
        }
        out = []
        for s, pid in enumerate(self.seat_player_ids):
            final = (rec.starting_stacks.get(pid, 0) + rec.payoffs.get(pid, 0)) if rec else 0
            # reveal: the hero always; opponents only if they went to showdown
            if s == self.hero_seat:
                hole = list(self._hero_hole) if self._hero_hole else None
            elif rec and pid in showdown:
                shown = rec.hole.get(pid)
                hole = list(shown) if shown else None
            else:
                hole = None
            out.append(SeatView(
                seat=s, label=self._label(s), archetype=self._client_archetype(s),
                role=self._role(s), stack_bb=round(final / self.bb, 1), bet_bb=0.0,
                folded=s in folded_seats, is_hero=(s == self.hero_seat), to_act=False,
                hole=hole, won=bool(rec and rec.payoffs.get(pid, 0) > 0),
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
            # Instant, LLM-free review — but only if the equity build has ALREADY run
            # (fetched via /review). state() must not trigger it, or the hand result
            # would wait on the equity again.
            review = self._grounded_review()
            return PlayState(
                hand_id=self.hand_id, complete=True, hero_seat=self.hero_seat,
                max_seats=self.max_seats, mystery=not self.reveal,
                hero_hole=self._hero_hole, board=list(rec.board) if rec else [],
                street="river", pot=int(rec.pot_bb * self.bb) if rec else 0,
                big_blind=self.bb, to_call=0, legal=None,
                seats=self._seats_complete(), log=self._log_complete(),
                review=review, coaching=self._coaching,
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
        # NB: do NOT build the summary here — its Monte-Carlo equity (every decision)
        # would block the action response, so the hand RESULT would wait on the REVIEW.
        # The summary is built lazily when the review/coach is fetched (off this path).
        return self.state()

    # --------------------------------------------------- coach assembly ---
    def _decisive_opponent(self) -> tuple[int, str]:
        """The opponent who actually applied the pressure on the hero's biggest
        decision -- the last player to RAISE into it -- not merely the loosest
        archetype at the table (a maniac who only called is not the villain)."""
        paid = [d for d in self._decisions if d.obs.to_call > 0] or self._decisions
        target = max(paid, key=lambda d: d.obs.to_call)
        hero_pid = self.seat_player_ids[self.hero_seat]
        rec = self.hand.record

        aggressor = None
        if rec:
            # the last non-hero raise on the decisive street, up to the hero's spot
            for a in rec.actions:
                if (a.street == target.obs.street and a.player_id != hero_pid
                        and a.is_raise and a.pot_before <= target.obs.pot + 1):
                    aggressor = a.player_id
            if aggressor is None:  # no raise on that street -> last raiser in the hand
                raisers = [a.player_id for a in rec.actions
                           if a.is_raise and a.player_id != hero_pid]
                aggressor = raisers[-1] if raisers else None
        if aggressor is None:  # truly unraised -> fall back to the most aggressive live opp
            live = list(target.obs.live_opponent_ids) or [
                pid for pid in self.seat_player_ids if self._pid_archetype[pid] != "human"
            ]
            aggressor = max(live, key=lambda pid: knobs_for(self._pid_archetype[pid]).postflop_aggression)
        return self.seat_player_ids.index(aggressor), self._pid_archetype[aggressor]

    def _build_summary(self) -> None:
        if not self._decisions:
            self._summary = None
            self._summary_ms = 0
            return
        t0 = time.perf_counter()
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
                "opponents_in_hand": o.n_active,   # multiway context (equity is vs this many)
                "context": "",
            })
        # the instant review shows EVERY decision (cheap); the coach focuses on the few
        # that mattered -- the ones the hero PAID for, biggest first -- capped so the
        # LLM output (and latency) stays bounded on long call-down hands.
        self._review_decisions = [
            {"street": x["street"], "action": x["hero_action"], "equity_pct": x["hero_equity_pct"]}
            for x in decisions
        ]
        paid = [i for i, x in enumerate(decisions) if x["to_call_bb"] > 0]
        ranked = paid or list(range(len(decisions)))
        top = sorted(ranked, key=lambda i: decisions[i]["to_call_bb"], reverse=True)[:3]
        key_decisions = [decisions[i] for i in sorted(top)]

        rec = self.hand.record
        fixture = {
            "hand_id": f"live-{self.hand_id}",
            "table": {"max_seats": self.max_seats, "big_blind_chips": self.bb},
            "hero": {"hole": list(self._hero_hole), "position": self._role(self.hero_seat) or "—"},
            "decisive_opponent": {"seat": dec_seat + 1, "archetype": dec_arch},
            "board": list(rec.board) if rec else [],
            "pot_bb": rec.pot_bb if rec else 0.0,
            "decisions": key_decisions,
        }
        self._fixture = fixture
        self._summary = build_summary(fixture)
        self._summary_ms = round((time.perf_counter() - t0) * 1000)  # equity + assembly

    @property
    def summary(self) -> Optional[dict[str, Any]]:
        # Lazy: the (slow) equity build runs on first access — i.e. when the review or
        # coach is fetched, never on the action response. ``_summary`` is set (possibly
        # to None for a no-decision hand) once the build has run.
        if not hasattr(self, "_summary"):
            self._build_summary()
        return self._summary

    def _grounded_review(self) -> Optional[dict[str, Any]]:
        """The instant LLM-free review dict, from an ALREADY-built summary. Returns None
        if the equity hasn't been computed yet (so ``state`` never triggers the build)."""
        s = getattr(self, "_summary", None)
        if not s:
            return None
        return {
            "opponent": {"label": s["decisive_opponent"]["style_label"],
                         "leak": s["decisive_opponent"]["leak"]},
            "decisions": getattr(self, "_review_decisions", []),
        }

    def review(self) -> Optional[dict[str, Any]]:
        """Public: ensure the (lazy) equity build has run, then return the review."""
        if not self.hand.complete:
            raise RuntimeError("hand is not complete yet")
        _ = self.summary  # triggers the build if needed
        return self._grounded_review()

    def coaching(self, *, client: Any = None, model: str = LIVE_COACH_MODEL) -> Optional[dict[str, Any]]:
        if not self.hand.complete:
            raise RuntimeError("hand is not complete yet")
        if self._coaching is not None:
            return self._coaching
        if self.summary is None:
            self._coaching = {"coaching": None, "note": "no decision to coach",
                              "elapsed_ms": 0, "summary_ms": getattr(self, "_summary_ms", 0)}
            return self._coaching
        t0 = time.perf_counter()
        result = coach_hand(self.summary, client=client, model=model)
        result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)   # the LLM call
        result["summary_ms"] = getattr(self, "_summary_ms", 0)            # equity + assembly
        self._coaching = result
        return self._coaching
