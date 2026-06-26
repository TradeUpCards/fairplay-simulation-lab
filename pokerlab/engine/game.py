"""Steppable No-Limit Hold'em over PokerKit — the interactive core of pokerlab.

playsim.table.play_hand runs a whole hand in one synchronous loop, so it cannot
pause for a human. HandSession exposes the *same* PokerKit usage as a state
machine: advance bot turns, stop at the human's turn for a UI action, resume.

The Observation / Decision seam is reused verbatim from playsim, so heuristic
ArchetypeAgents, the RL bot, and the human are interchangeable agents. We do not
edit playsim — we depend on it.
"""
from __future__ import annotations

import random
import warnings
from dataclasses import dataclass

from pokerkit import Automation, NoLimitTexasHoldem

from playsim.agent import Decision, Observation
from playsim.equity import FULL_DECK

# We supply the deck ourselves (seeded), so PokerKit's hint is expected — silence it.
warnings.filterwarnings("ignore", message="A card being dealt")

# Everything automated except dealing (we deal a seeded deck) — keeps the engine
# authoritative for legality/showdown while staying deterministic. (Same set as
# playsim.table so behaviour matches.)
_AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.CARD_BURNING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)


def _pot_now(state) -> int:
    pots = sum(p.amount for p in state.pots) if state.pots else 0
    bets = sum(state.bets) if getattr(state, "bets", None) else 0
    return pots + bets


@dataclass
class ActionEvent:
    seat: int
    player_id: int
    street: int          # 0 preflop .. 3 river
    action: str          # "fold" | "check" | "call" | "bet" | "raise"
    amount: int
    pot_before: int
    to_call: int = 0     # what this actor faced before acting (for pot-odds coaching)


class HandSession:
    """One hand of NLHE, steppable. Mirrors playsim.table.play_hand's PokerKit calls."""

    def __init__(self, seat_player_ids, seat_stacks, sb, bb, rng: random.Random,
                 members_by_player=None, weak_player_ids=frozenset()):
        self.n = len(seat_player_ids)
        self.seat_player_ids = list(seat_player_ids)
        self.sb, self.bb = sb, bb
        self.rng = rng
        self.members_by_player = members_by_player or {}
        self.weak_player_ids = weak_player_ids

        deck = FULL_DECK[:]
        rng.shuffle(deck)
        self._it = iter(deck)
        self._state = NoLimitTexasHoldem.create_state(
            _AUTOMATIONS, True, 0, (sb, bb), bb, tuple(seat_stacks), self.n)

        self.hole: list[list[str]] = [[] for _ in range(self.n)]
        for _ in range(2):
            for seat in range(self.n):
                c = next(self._it)
                self._state.deal_hole(c)
                self.hole[seat].append(c)

        self.board: list[str] = []
        self.folded: set[int] = set()
        self.events: list[ActionEvent] = []
        self._advance()

    # -- state ------------------------------------------------------------
    @property
    def done(self) -> bool:
        return not self._state.status or self._state.actor_index is None

    def actor_seat(self):
        return None if self.done else self._state.actor_index

    def _advance(self):
        """Deal any pending board cards; stop when a player must act or the hand ends."""
        while self._state.status:
            if self._state.can_deal_board():
                for _ in range(self._state.board_dealing_count):
                    c = next(self._it)
                    self._state.deal_board(c)
                    self.board.append(c)
                continue
            break  # actor_index is now set (a decision) or None (hand over)

    def observation(self) -> Observation:
        seat = self._state.actor_index
        pid = self.seat_player_ids[seat]
        live_opp = [self.seat_player_ids[s] for s in range(self.n)
                    if s not in self.folded and s != seat]
        return Observation(
            street=self._state.street_index or 0,
            hole=(self.hole[seat][0], self.hole[seat][1]),
            board=list(self.board),
            to_call=self._state.checking_or_calling_amount or 0,
            pot=_pot_now(self._state),
            min_raise_to=self._state.min_completion_betting_or_raising_to_amount or 0,
            max_raise_to=self._state.max_completion_betting_or_raising_to_amount or 0,
            my_stack=self._state.stacks[seat],
            big_blind=self.bb,
            n_active=len(live_opp),
            live_opponent_ids=tuple(live_opp),
            member_ids=self.members_by_player.get(pid, frozenset()),
            weak_opponent=any(o in self.weak_player_ids for o in live_opp),
        )

    def legal(self) -> dict:
        """What the current actor may do — for the UI / a human."""
        st = self._state
        to_call = st.checking_or_calling_amount or 0
        return {
            "can_fold": bool(st.can_fold()) and to_call > 0,
            "can_check": to_call == 0,
            "to_call": to_call,
            "can_raise": bool(st.can_complete_bet_or_raise_to()),
            "min_raise_to": st.min_completion_betting_or_raising_to_amount or 0,
            "max_raise_to": st.max_completion_betting_or_raising_to_amount or 0,
        }

    # -- transition -------------------------------------------------------
    def apply(self, d: Decision) -> ActionEvent:
        st = self._state
        seat = st.actor_index
        pid = self.seat_player_ids[seat]
        to_call = st.checking_or_calling_amount or 0
        pot = _pot_now(st)
        street = st.street_index or 0

        if d.kind == "fold" and st.can_fold() and to_call > 0:
            st.fold()
            self.folded.add(seat)
            action, amt = "fold", 0
        elif d.kind == "raise" and st.can_complete_bet_or_raise_to(d.amount):
            st.complete_bet_or_raise_to(d.amount)
            action, amt = ("raise" if to_call > 0 else "bet"), int(d.amount)
        else:
            st.check_or_call()
            action, amt = (("call", to_call) if to_call > 0 else ("check", 0))

        ev = ActionEvent(seat, pid, street, action, amt, pot, to_call)
        self.events.append(ev)
        self._advance()
        return ev

    # -- results ----------------------------------------------------------
    def payoffs(self) -> dict:
        return {self.seat_player_ids[s]: int(self._state.payoffs[s]) for s in range(self.n)}

    def stacks(self) -> dict:
        return {self.seat_player_ids[s]: int(self._state.stacks[s]) for s in range(self.n)}

    def pot(self) -> int:
        return _pot_now(self._state)

    def showdown_seats(self) -> list[int]:
        return [s for s in range(self.n) if s not in self.folded]
