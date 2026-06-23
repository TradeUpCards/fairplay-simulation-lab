"""Engine seam — shared types + the Engine protocol. No PokerKit knowledge here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Action:
    kind: str            # "fold" | "check_call" | "raise_to"
    amount: int = 0      # total bet level for "raise_to"; ignored otherwise
    tag: str = ""        # "bluff" for a weak-equity raise; "" otherwise
    equity: float = 0.0  # the win-prob the agent acted on (for the log/audit)


@dataclass
class DecisionContext:
    seat: int
    hole: list[str]
    board: list[str]
    to_call: int
    pot: int
    stack: int
    big_blind: int
    position: str        # "early" | "middle" | "late" | "blind"
    n_opponents: int
    street: str          # "preflop" | "flop" | "turn" | "river"
    num_players: int


@dataclass
class HandResult:
    payoffs: list[int]           # net chips per seat (sums to 0)
    final_board: list[str]
    total_pot: int


class Engine(Protocol):
    def start_hand(self, *, deck: list[str], button: int,
                   blinds: tuple[int, int], starting_stacks: list[int]) -> None: ...
    def is_done(self) -> bool: ...
    def actor(self) -> int | None: ...
    def context(self) -> DecisionContext: ...
    def apply(self, action: Action) -> None: ...
    def result(self) -> HandResult: ...
