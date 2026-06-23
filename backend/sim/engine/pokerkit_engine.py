"""The ONLY module that imports pokerkit. Adapts it to the Engine seam.

API facts pinned by the Task 1 spike: hole/board dealing and card burning are
NOT automated (we control the deck); a board street requires a card burn
(`burn_card("??")` — unknown card, not drawn from our seeded deck) before the
board can be dealt (`can_deal_board()` / `deal_board(...)`).
"""
from __future__ import annotations

from pokerkit import Automation, NoLimitTexasHoldem

from sim.engine.base import Action, DecisionContext, HandResult

_AUTO = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.RUNOUT_COUNT_SELECTION,        # all-ins → single runout, no pause
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)  # manual (for determinism): hole dealing, board dealing, card burning
_STREET = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}


def _cs(card) -> str:
    """PokerKit Card -> our 2-char 'Ah' string (str(card) is verbose)."""
    return card.rank + card.suit


class PokerKitEngine:
    def __init__(self) -> None:
        self._s = None
        self._deck: list[str] = []
        self._i = 0
        self._n = 0
        self._button = 0
        self._bb = 0
        self._peak_pot = 0      # captured before CHIPS_PUSHING empties the pot

    def start_hand(self, *, deck, button, blinds, starting_stacks) -> None:
        self._deck, self._i = list(deck), 0
        self._peak_pot = 0
        self._n = len(starting_stacks)
        self._button, self._bb = button, blinds[1]
        self._s = NoLimitTexasHoldem.create_state(
            _AUTO, True, 0, blinds, blinds[1], tuple(starting_stacks), self._n)
        for _ in range(self._n):                       # 2 hole cards per seat
            self._s.deal_hole("".join(self._draw(2)))
        self._track_pot()
        self._advance()

    def _draw(self, k: int) -> list[str]:
        cards = self._deck[self._i:self._i + k]
        self._i += k
        return cards

    def _track_pot(self) -> None:
        """Record the live pot (collected + outstanding bets) before it's pushed."""
        s = self._s
        self._peak_pot = max(self._peak_pot, s.total_pot_amount + sum(s.bets))

    def _board(self) -> list[str]:
        """Flatten PokerKit's per-deal board groups into a flat 'Ah' list."""
        out: list[str] = []
        for x in self._s.board_cards:
            if isinstance(x, (list, tuple)):
                out.extend(_cs(c) for c in x)
            else:
                out.append(_cs(x))
        return out

    def _advance(self) -> None:
        """Settle non-betting steps: burn + deal board from our deck."""
        s = self._s
        while s.status and s.actor_index is None:
            if s.card_burning_status:
                s.burn_card("??")                      # unknown card; not from our deck
            elif s.can_deal_board():
                need = 3 if len(self._board()) == 0 else 1
                s.deal_board("".join(self._draw(need)))
            else:
                break

    def is_done(self) -> bool:
        return not self._s.status

    def actor(self) -> int | None:
        self._advance()
        return self._s.actor_index

    def context(self) -> DecisionContext:
        s = self._s
        a = s.actor_index
        to_call = max(s.bets) - s.bets[a]
        board = self._board()
        return DecisionContext(
            seat=a, hole=[_cs(c) for c in s.hole_cards[a]],
            board=board,
            to_call=to_call, pot=s.total_pot_amount, stack=s.stacks[a],
            big_blind=self._bb, num_players=self._n,
            n_opponents=sum(1 for st in s.statuses if st) - 1,
            position=self._position(a),
            street=_STREET.get(len(board), "river"))

    def _position(self, seat: int) -> str:
        rel = (seat - self._button) % self._n
        if rel in (1, 2):
            return "blind"
        if rel <= self._n // 3:
            return "early"
        if rel <= 2 * self._n // 3:
            return "middle"
        return "late"

    def apply(self, action: Action) -> None:
        s = self._s
        if action.kind == "fold":
            s.fold()
        elif action.kind == "check_call":
            s.check_or_call()
        else:  # raise_to, clamped into the legal range
            amt = action.amount
            if s.can_complete_bet_or_raise_to(amt):
                s.complete_bet_or_raise_to(amt)
            else:
                lo = getattr(s, "min_completion_betting_or_raising_to_amount", None)
                if lo is not None and s.can_complete_bet_or_raise_to(lo):
                    s.complete_bet_or_raise_to(lo)
                else:
                    s.check_or_call()
        self._track_pot()
        self._advance()

    def result(self) -> HandResult:
        s = self._s
        return HandResult(payoffs=list(s.payoffs),
                          final_board=self._board(),
                          total_pot=self._peak_pot)
