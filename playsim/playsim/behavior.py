"""PlayerBehaviorPolicy — the swappable seam for *player* decisions.

Parallel to `SeatingPolicy` (the operator/routing side, in `policies.py`), this
owns the PLAYER side: whether to **accept** an offered seat, when to **leave**
(churn), and whether to **re-seek** after a table break. The room loop calls this
seam instead of embedding the rules, so player behavior is one swappable, testable
component — and the future fit-aware / agentic models are just other
implementations behind the same interface.

`DefaultBehaviorPolicy` reproduces the current behavior exactly (Phase 1):
- accept: always (forced placement);
- leave: the cohort tilt-leave decision (`runner.cohort_should_leave`);
- re-seek on break: always once.

So swapping it in is behavior-preserving and guarded by the existing determinism
tests. The fit-aware parametric model (Phase 2) implements the same Protocol with
multi-factor leave, table-pressure, fit, and accept/decline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .runner import _COHORT, cohort_should_leave


@dataclass
class SeatOffer:
    """A seat the room is offering a seeker. ``rationale`` is the chosen table's
    rank/health breakdown for backend-routed offers, else ``None``."""
    archetype: str
    table_id: str
    rationale: dict | None = None


@dataclass
class LeaveContext:
    """Everything a leave decision may consider. The default policy uses only the
    chip-loss / session fields; the fit-aware policy (Phase 2) will also consume
    table-pressure and fit, which is why they are carried here."""
    archetype: str
    seat_minutes: float
    net_bb: float
    hands_played: int
    tilt_quit: float
    spread: float
    # reserved for Phase 2 (ignored by DefaultBehaviorPolicy):
    table_pressure: float | None = None
    fit: float | None = None


@runtime_checkable
class PlayerBehaviorPolicy(Protocol):
    name: str

    def accept_seat(self, offer: SeatOffer) -> bool:
        """Return True to take the offered seat, False to decline it."""
        ...

    def should_leave(self, ctx: LeaveContext) -> tuple[bool, str]:
        """Return (leaving, reason). reason is "" when not leaving."""
        ...

    def reseek_on_break(self, archetype: str) -> bool:
        """Return True if a player displaced by a table break re-seeks a seat."""
        ...


class DefaultBehaviorPolicy:
    """Behavior-preserving baseline — exactly today's rules."""

    name = "default"

    def accept_seat(self, offer: SeatOffer) -> bool:
        return True  # forced placement: a seeker always takes the offered seat

    def should_leave(self, ctx: LeaveContext) -> tuple[bool, str]:
        if ctx.archetype not in _COHORT:
            return False, ""  # only the vulnerable cohort voluntarily leaves
        leaving = cohort_should_leave(
            ctx.seat_minutes, ctx.net_bb, ctx.hands_played,
            ctx.archetype, ctx.tilt_quit, ctx.spread,
        )
        return (leaving, "tilt" if leaving else "")

    def reseek_on_break(self, archetype: str) -> bool:
        return True  # displaced players re-seek once (current behavior)
