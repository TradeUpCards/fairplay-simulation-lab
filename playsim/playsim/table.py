"""Play one hand on the PokerKit engine.

PokerKit is the *environment / referee*: it owns legal moves, state, and chip
distribution, so an agent can never make an illegal move. We control the deck
ourselves from a seeded ``random.Random`` (cards dealt explicitly) so every hand
is reproducible — the determinism the lab's hard rules require.

The caller (``runner``) rotates the player→seat mapping each hand so positions
rotate; this module is purely "play these seats out and report what happened".

The hand loop lives in :func:`play_hand_steps`, a pausable generator that yields
``(seat, Observation)`` whenever a seat must act and receives that seat's
:class:`Decision` back. :func:`play_hand` drives it with the seat agents (every
seat a bot); the interactive driver (``playsim.interactive``) drives the same
generator but pauses for a human seat. One loop, two drivers — the engine is never
forked, and bot rng-consumption order is byte-identical either way.
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


def _table_view(
    state,
    seat_player_ids: list[int],
    actions: list[ActionRecord],
    folded: set[int],
    *,
    sb_seat: int,
    bb_seat: int,
    button_seat: int,
    bb: int,
) -> dict:
    """A renderable snapshot of the table mid-hand: per-seat stacks/bets/folded,
    the blind+button seats, and the action log so far. This is what lets a human
    see *who did what* before it's their turn."""
    n = len(seat_player_ids)
    pid_to_seat = {pid: i for i, pid in enumerate(seat_player_ids)}
    bets = state.bets if getattr(state, "bets", None) else [0] * n
    return {
        "button_seat": button_seat,
        "sb_seat": sb_seat,
        "bb_seat": bb_seat,
        "seats": [
            {
                "seat": s,
                "stack_bb": round(state.stacks[s] / bb, 1),
                "bet_bb": round((bets[s] if s < len(bets) else 0) / bb, 1),
                "folded": s in folded,
            }
            for s in range(n)
        ],
        "log": [
            {
                "seat": pid_to_seat[a.player_id],
                "street": a.street,
                "action": a.action,
                "amount_bb": round(a.amount / bb, 1),
            }
            for a in actions
        ],
    }


def play_hand_steps(
    seat_player_ids: list[int],
    seat_stacks: list[int],
    sb: int,
    bb: int,
    rng,
    hand_id: int,
    members_by_player: dict[int, frozenset[int]],
    weak_player_ids: frozenset[int],
    button_seat: int | None = None,
):
    """The hand loop as a pausable generator.

    Yields ``(seat, Observation)`` each time a seat must act and receives that
    seat's :class:`Decision` back via ``.send()``; ``return``s the finished
    :class:`HandRecord` (PEP 380 ``StopIteration.value``). The deck shuffle, the
    deals, and the board run inside here; only the per-seat *decision* is delegated
    to the driver, so swapping one seat for a human changes nothing about the engine
    or the bots' determinism.
    """
    n = len(seat_player_ids)
    deck = FULL_DECK[:]
    rng.shuffle(deck)
    it = iter(deck)

    # Place the blinds relative to a (rotating) button, so players keep their seats
    # and only the button/blinds move between hands. Default button = last seat,
    # which reproduces the original blinds-at-(0,1) behaviour exactly.
    if button_seat is None:
        button_seat = n - 1
    button_seat %= n
    if n == 2:
        sb_seat, bb_seat = button_seat, (button_seat + 1) % n
    else:
        sb_seat, bb_seat = (button_seat + 1) % n, (button_seat + 2) % n
    blind_tuple = [0] * n
    blind_tuple[sb_seat] = sb
    blind_tuple[bb_seat] = bb

    state = NoLimitTexasHoldem.create_state(
        _AUTOMATIONS, True, 0, tuple(blind_tuple), bb, tuple(seat_stacks), n
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
    street_raises = 0   # voluntary raises so far on the current street
    cur_street = 0

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

        st_idx = state.street_index or 0
        if st_idx != cur_street:        # new street -> reset the raise counter
            cur_street = st_idx
            street_raises = 0

        pid = seat_player_ids[seat]
        to_call = state.checking_or_calling_amount or 0
        pot = _pot_now(state)
        live_opp = [
            seat_player_ids[s]
            for s in range(n)
            if s not in folded and s != seat
        ]
        obs = Observation(
            street=st_idx,
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
            raises_this_street=street_raises,
        )
        d = yield (
            seat,
            obs,
            _table_view(state, seat_player_ids, actions, folded,
                        sb_seat=sb_seat, bb_seat=bb_seat,
                        button_seat=button_seat, bb=bb),
        )

        # Apply through the engine (it enforces legality).
        if d.kind == "fold" and state.can_fold():
            state.fold()
            folded.add(seat)
            action, amt, is_raise, is_call = "fold", 0, False, False
        elif d.kind == "raise" and state.can_complete_bet_or_raise_to(d.amount):
            state.complete_bet_or_raise_to(d.amount)
            action = "raise" if to_call > 0 else "bet"
            amt, is_raise, is_call = d.amount, True, False
            street_raises += 1
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
    """Play one full hand with every seat driven by its archetype agent.

    Thin driver over :func:`play_hand_steps`: each time the loop needs a seat's
    move, that seat's agent supplies it. rng consumption order is identical to the
    original single-function loop, so every existing fixture and stat is unchanged.
    """
    gen = play_hand_steps(
        seat_player_ids, seat_stacks, sb, bb, rng, hand_id,
        members_by_player, weak_player_ids,
    )
    try:
        seat, obs, _ = next(gen)
        while True:
            d = seat_agents[seat].act(obs, rng)
            seat, obs, _ = gen.send(d)
    except StopIteration as stop:
        return stop.value
