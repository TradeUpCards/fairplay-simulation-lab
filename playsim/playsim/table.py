"""Play one hand on the PokerKit engine.

PokerKit is the *environment / referee*: it owns legal moves, state, and chip
distribution, so an agent can never make an illegal move. We control the deck
ourselves from a seeded ``random.Random`` (cards dealt explicitly) so every hand
is reproducible — the determinism the lab's hard rules require.

The caller (``runner``) rotates the player→seat mapping each hand so positions
rotate; this module is purely "play these seats out and report what happened".
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

from pokerkit import Automation, NoLimitTexasHoldem

# We supply the deck ourselves (seeded), so PokerKit's "card not recommended to
# be dealt" hint is expected and harmless — silence it.
warnings.filterwarnings("ignore", message="A card being dealt")

from .agent import ArchetypeAgent, Observation
from .equity import FULL_DECK

# Everything automated except the dealing (we supply the deck) — that keeps the
# engine authoritative for legality/showdown while we stay deterministic.
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


@dataclass
class ActionRecord:
    player_id: int
    street: int
    action: str          # "fold" | "check" | "call" | "bet" | "raise"
    amount: int
    pot_before: int
    latency_ms: int
    voluntary: bool       # voluntary preflop money (for vpip)
    is_raise: bool        # bet/raise (aggression numerator)
    is_call: bool         # called a bet (aggression denominator)


@dataclass
class HandRecord:
    hand_id: int
    button_seat: int
    seat_player_ids: list[int]
    starting_stacks: dict[int, int]
    hole: dict[int, tuple[str, str]]
    board: list[str]
    actions: list[ActionRecord]
    payoffs: dict[int, int]     # net chips by player_id
    pot_bb: float
    big_blind: int
    showdown_player_ids: list[int] = field(default_factory=list)


def _pot_now(state) -> int:
    pots = sum(p.amount for p in state.pots) if state.pots else 0
    bets = sum(state.bets) if getattr(state, "bets", None) else 0
    return pots + bets


def play_hand(
    seat_agents: list[ArchetypeAgent],
    seat_player_ids: list[int],
    seat_stacks: list[int],
    sb: int,
    bb: int,
    rng,
    hand_id: int,
    members_by_player: dict[int, frozenset[int]],
    weak_player_ids: frozenset[int],
) -> HandRecord:
    n = len(seat_agents)
    deck = FULL_DECK[:]
    rng.shuffle(deck)
    it = iter(deck)

    state = NoLimitTexasHoldem.create_state(
        _AUTOMATIONS, True, 0, (sb, bb), bb, tuple(seat_stacks), n
    )

    hole: list[list[str]] = [[] for _ in range(n)]
    for _ in range(2):
        for seat in range(n):
            c = next(it)
            state.deal_hole(c)
            hole[seat].append(c)

    board: list[str] = []
    folded: set[int] = set()
    actions: list[ActionRecord] = []

    guard = 0
    while state.status and guard < 400:
        guard += 1
        if state.can_deal_board():
            for _ in range(state.board_dealing_count):
                c = next(it)
                state.deal_board(c)
                board.append(c)
            continue
        seat = state.actor_index
        if seat is None:
            break

        agent = seat_agents[seat]
        pid = seat_player_ids[seat]
        to_call = state.checking_or_calling_amount or 0
        pot = _pot_now(state)
        live_opp = [
            seat_player_ids[s]
            for s in range(n)
            if s not in folded and s != seat
        ]
        obs = Observation(
            street=state.street_index or 0,
            hole=(hole[seat][0], hole[seat][1]),
            board=list(board),
            to_call=to_call,
            pot=pot,
            min_raise_to=state.min_completion_betting_or_raising_to_amount or 0,
            max_raise_to=state.max_completion_betting_or_raising_to_amount or 0,
            my_stack=state.stacks[seat],
            big_blind=bb,
            n_active=len(live_opp),
            live_opponent_ids=tuple(live_opp),
            member_ids=members_by_player.get(pid, frozenset()),
            weak_opponent=any(o in weak_player_ids for o in live_opp),
        )
        d = agent.act(obs, rng)

        # Apply through the engine (it enforces legality).
        if d.kind == "fold" and state.can_fold():
            state.fold()
            folded.add(seat)
            action, amt, is_raise, is_call = "fold", 0, False, False
        elif d.kind == "raise" and state.can_complete_bet_or_raise_to(d.amount):
            state.complete_bet_or_raise_to(d.amount)
            action = "raise" if to_call > 0 else "bet"
            amt, is_raise, is_call = d.amount, True, False
        else:
            state.check_or_call()
            if to_call > 0:
                action, amt, is_raise, is_call = "call", to_call, False, True
            else:
                action, amt, is_raise, is_call = "check", 0, False, False

        actions.append(
            ActionRecord(
                player_id=pid, street=obs.street, action=action, amount=amt,
                pot_before=pot, latency_ms=d.latency_ms,
                voluntary=(obs.street == 0 and (d.voluntary or is_raise)),
                is_raise=is_raise, is_call=is_call,
            )
        )

    payoffs = {seat_player_ids[s]: int(state.payoffs[s]) for s in range(n)}
    final_pot = sum(abs(v) for v in payoffs.values()) / 2 or bb
    showdown = [seat_player_ids[s] for s in range(n) if s not in folded]
    return HandRecord(
        hand_id=hand_id,
        button_seat=0,
        seat_player_ids=list(seat_player_ids),
        starting_stacks={seat_player_ids[s]: seat_stacks[s] for s in range(n)},
        hole={seat_player_ids[s]: (hole[s][0], hole[s][1]) for s in range(n)},
        board=board,
        actions=actions,
        payoffs=payoffs,
        pot_bb=round(final_pot / bb, 2),
        big_blind=bb,
        showdown_player_ids=showdown if len(showdown) > 1 else [],
    )
