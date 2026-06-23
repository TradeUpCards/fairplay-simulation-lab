"""Hand-history event log. Captures what the stat rollup needs + an auditable trail."""
from __future__ import annotations

from sim.engine.base import Action, DecisionContext, HandResult


class EventLog:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.results: list[dict] = []

    def record_action(self, hand_id, table_id, player_id,
                      ctx: DecisionContext, action: Action) -> None:
        # Voluntary = chips committed beyond forced blinds: a raise, or a call of a
        # live bet. A check (check_call with nothing to call) commits nothing.
        voluntary = action.kind == "raise_to" or (
            action.kind == "check_call" and ctx.to_call > 0)
        self.events.append({
            "hand_id": hand_id, "table_id": table_id, "player_id": player_id,
            "street": ctx.street, "kind": action.kind,
            # Sizing context: a raise's target is `amount`; a call's size is `to_call`.
            "amount": action.amount if action.kind == "raise_to" else 0,
            "to_call": ctx.to_call, "pot": ctx.pot, "equity": action.equity,
            "voluntary": voluntary, "is_raise": action.kind == "raise_to",
            "is_bluff": action.tag == "bluff",
        })

    def record_result(self, hand_id, table_id, seats, result: HandResult,
                      big_blind: int) -> None:
        pot_bb = result.total_pot / big_blind if big_blind else 0.0
        for seat, player_id in enumerate(seats):
            self.results.append({
                "hand_id": hand_id, "table_id": table_id, "player_id": player_id,
                "net": result.payoffs[seat], "pot_bb": round(pot_bb, 2), "dealt_in": True,
            })
