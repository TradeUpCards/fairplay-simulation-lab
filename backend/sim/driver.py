"""Drives hands at a table: seeded deck per hand, button rotation, reload-to-stack."""
from __future__ import annotations

import random

from sim import deck
from sim.log import EventLog


def run_table(*, table_id, engine, agents, player_ids, blinds,
              starting_stack, hands, table_seed, log: EventLog) -> None:
    n = len(agents)
    deal_rng = random.Random(deck.derive(table_seed, 1))
    decision_rng = random.Random(deck.derive(table_seed, 2))
    bb = blinds[1]

    for h in range(hands):
        button = h % n
        d = deck.shuffled(deal_rng)
        stacks = [starting_stack] * n          # cash game: reload each hand
        engine.start_hand(deck=d, button=button, blinds=blinds, starting_stacks=stacks)
        hand_id = f"{table_id}-H{h:04d}"

        guard = 0
        while not engine.is_done() and guard < 1000:
            guard += 1
            if engine.actor() is None:
                break
            ctx = engine.context()
            action = agents[ctx.seat].decide(ctx, decision_rng)
            log.record_action(hand_id, table_id, player_ids[ctx.seat], ctx, action)
            engine.apply(action)

        log.record_result(hand_id, table_id, player_ids, engine.result(), bb)
