"""Pause-for-human-input driver over the playsim hand loop.

Wraps :func:`playsim.table.play_hand_steps` so one designated seat is a HUMAN whose
decision arrives externally (e.g. an HTTP action), while every other seat plays its
archetype policy. The bots stay deterministic (seeded rng); the human is the only
nondeterministic input -- exactly the lab's rule. This is the engine hook the PRD
calls "pause for human input, resume on action" -- and it is a hook, not a fork: the
hand loop, the deal, and the bots are the same code ``play_hand`` runs.

Usage::

    hand = InteractiveHand(human_seat=0, seat_agents=agents, ...)
    obs = hand.start()              # runs bots until the human must act (or hand ends)
    while obs is not None:
        obs = hand.submit(my_decision(obs))
    record = hand.record            # the finished HandRecord
"""

from __future__ import annotations

from typing import Optional

from .agent import ArchetypeAgent, Decision, Observation
from .table import HandRecord, play_hand_steps


class InteractiveHand:
    """Drive one hand, pausing whenever the human seat must act.

    ``seat_agents`` supplies the archetype policy for every *bot* seat; the entry at
    ``human_seat`` is never called (it may be ``None``). All bot decisions and the
    deck are driven by ``rng``; the human's decisions come in via :meth:`submit`.
    """

    def __init__(
        self,
        *,
        human_seat: int,
        seat_agents: list,
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
        self.human_seat = human_seat
        self.seat_agents = seat_agents
        self.rng = rng
        self._gen = play_hand_steps(
            seat_player_ids, seat_stacks, sb, bb, rng, hand_id,
            members_by_player, weak_player_ids, button_seat=button_seat,
        )
        self._pending: Optional[tuple[int, Observation]] = None
        self._record: Optional[HandRecord] = None
        self._view: Optional[dict] = None
        self._started = False

    @property
    def record(self) -> Optional[HandRecord]:
        """The finished HandRecord, or None while the hand is in progress."""
        return self._record

    @property
    def complete(self) -> bool:
        return self._record is not None

    @property
    def pending_observation(self) -> Optional[Observation]:
        """The human's current Observation (their turn to act), or None."""
        return self._pending[1] if self._pending else None

    @property
    def view(self) -> Optional[dict]:
        """The latest renderable table snapshot (per-seat stacks/bets/folded,
        blind+button seats, action log) — what to show the human."""
        return self._view

    def start(self) -> Optional[Observation]:
        """Begin the hand and run bots until the human must act or the hand ends.

        Returns the human's Observation, or None if the hand finished before the
        human ever had to act.
        """
        if self._started:
            raise RuntimeError("hand already started")
        self._started = True
        try:
            seat_obs = next(self._gen)
        except StopIteration as stop:
            self._record = stop.value
            return None
        return self._drive(seat_obs)

    def submit(self, decision: Decision) -> Optional[Observation]:
        """Apply the human's decision, then run bots to the next human turn or end."""
        if self._pending is None:
            raise RuntimeError("no human decision pending (start the hand first)")
        self._pending = None
        try:
            seat_obs = self._gen.send(decision)
        except StopIteration as stop:
            self._record = stop.value
            return None
        return self._drive(seat_obs)

    def _drive(self, seat_obs) -> Optional[Observation]:
        """Run bot seats until the human must act or the hand ends."""
        while True:
            seat, obs, view = seat_obs
            self._view = view
            if seat == self.human_seat:
                self._pending = (seat, obs)
                return obs
            d = self.seat_agents[seat].act(obs, self.rng)
            try:
                seat_obs = self._gen.send(d)
            except StopIteration as stop:
                self._record = stop.value
                self._pending = None
                return None
