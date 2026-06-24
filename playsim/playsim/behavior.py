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

import math
import random
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .knobs import session_min_for
from .runner import _COHORT, cohort_should_leave


@dataclass
class SeatOffer:
    """A seat the room is offering a seeker. ``rationale`` is the chosen table's
    rank/health breakdown for backend-routed offers, else ``None``. The raw table
    facts let a fit-aware policy assess the offer; DefaultBehaviorPolicy ignores them."""
    archetype: str
    table_id: str
    rationale: dict | None = None
    table_archetypes: tuple[str, ...] = ()
    table_style: str = ""
    seated_count: int = 0
    max_seats: int = 0


@dataclass
class LeaveContext:
    """Everything a leave decision may consider. The default policy uses only the
    chip-loss / session fields; the fit-aware policy (Phase 2) also computes table
    pressure and style fit from the raw table facts below."""
    archetype: str
    seat_minutes: float
    net_bb: float
    hands_played: int
    tilt_quit: float
    spread: float
    # raw table facts (fit-aware policies compute pressure/fit from these):
    table_archetypes: tuple[str, ...] = ()
    table_style: str = ""
    seated_count: int = 0
    max_seats: int = 0


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


# --- Phase 2: fit-aware parametric model ---------------------------------------

# Composition-derived "table pressure" inputs (no chip flow). Mirrors the backend
# health penalties in spirit; see the predicted-vs-predicted circularity guard in
# the spec — pressure overlaps the router's health, so its weight is modest and
# meant to be swept/calibrated, not trusted at face value.
_AGGRESSOR_WEIGHT = {
    "aggressive_predatory": 1.0, "grinder": 0.35, "cluster_member": 0.35, "solver_like": 0.5,
}
_VULNERABLE = frozenset({"new", "recreational"})
_PRESSURE_K = 1.0

# Archetype-specific preferred table volatility (0 = passive/friendly .. 1 = high/
# predatory). Only the cohort is fit-leave-scoped in Phase 2.
_PREF_VOLATILITY = {"new": 0.15, "recreational": 0.25, "promo_hunter": 0.30}


def style_volatility(label: str) -> float:
    """Map a table's descriptive style_volatility_label to a [0,1] volatility.
    Keyword-based so it tolerates the fixture's free-text labels. Approximates the
    backend style axis; exact reconciliation is a calibration (Phase 3) concern."""
    s = (label or "").lower()
    if any(k in s for k in ("predatory", "high volatility", "grinder", "high stakes")):
        return 0.9
    if any(k in s for k in ("beginner", "friendly", "healthy", "low")):
        return 0.2
    return 0.5


def table_pressure(archetypes, seated_count: int, max_seats: int) -> float:
    """Composition-derived danger in [0,1] — aggressor load vs the vulnerable pool
    (saturating) plus short-handed fragility. No realized chip flow."""
    agg = sum(_AGGRESSOR_WEIGHT.get(a, 0.0) for a in archetypes)
    vuln = sum(1 for a in archetypes if a in _VULNERABLE)
    predation = agg / (vuln + 1.0)
    pred_term = 1.0 - math.exp(-_PRESSURE_K * predation)
    frag = (1.0 - seated_count / max_seats) if max_seats else 0.0
    return max(0.0, min(1.0, 0.6 * pred_term + 0.4 * frag))


def style_fit(archetype: str, table_style: str) -> float:
    """Style match in [0,1] — table volatility vs the archetype's preferred level.
    A table *attribute*, distinct from table_pressure (who is seated)."""
    pref = _PREF_VOLATILITY.get(archetype)
    if pref is None:
        return 0.5  # non-cohort: neutral (Phase 2 scopes fit-leave to the cohort)
    return max(0.0, 1.0 - abs(style_volatility(table_style) - pref))


class FitAwareBehaviorPolicy:
    """Parametric fit-aware behavior (Phase 2), behind the same seam.

    Leave is a multi-factor session-budget shrink: loss/tilt (as today) + table
    pressure + style mismatch, each weighted. Optional fit-aware decline (default
    OFF, so the retention channel is measured before the acceptance channel).

    Ships on documented DEFAULT weights — **illustrative until calibrated**
    (Phase 3). At ``w_pressure == w_fit == 0`` and decline disabled, the leave
    *decision* reduces EXACTLY to DefaultBehaviorPolicy (only the exit-reason label
    is more granular). Weights are deliberately modest to avoid manufacturing a
    routing win by construction; sweep them in Phase 3.
    """

    name = "fit_aware"

    def __init__(self, *, w_pressure: float = 0.15, w_fit: float = 0.10,
                 decline_enabled: bool = False, decline_strength: float = 0.6,
                 seed: int = 0) -> None:
        self.w_pressure = w_pressure
        self.w_fit = w_fit
        self.decline_enabled = decline_enabled
        self.decline_strength = decline_strength
        self.rng = random.Random(seed)

    def should_leave(self, ctx: LeaveContext) -> tuple[bool, str]:
        if ctx.archetype not in _COHORT:
            return (False, "")
        hp = ctx.hands_played
        loss100 = (-ctx.net_bb) / (hp / 100.0) if hp >= 15 else 0.0
        loss_tilt = max(0.0, loss100) / 130.0 * (0.5 + ctx.tilt_quit)
        pressure = table_pressure(ctx.table_archetypes, ctx.seated_count, ctx.max_seats)
        mismatch = 1.0 - style_fit(ctx.archetype, ctx.table_style)
        p_term = self.w_pressure * pressure
        m_term = self.w_fit * mismatch
        shrink = max(0.12, min(1.25, 1.0 - (loss_tilt + p_term + m_term)))
        budget = session_min_for(ctx.archetype) * ctx.spread * shrink
        if ctx.seat_minutes < budget:
            return (False, "")
        contribs = {"tilt": loss_tilt, "table_pressure": p_term, "mismatch": m_term}
        dominant = max(contribs, key=contribs.get)
        reason = dominant if contribs[dominant] > 0.01 else "session_complete"
        return (True, reason)

    def accept_seat(self, offer: SeatOffer) -> bool:
        if not self.decline_enabled or offer.archetype not in _COHORT:
            return True
        f = style_fit(offer.archetype, offer.table_style)
        pressure = table_pressure(offer.table_archetypes, offer.seated_count, offer.max_seats)
        decline_prob = self.decline_strength * max(0.0, 0.5 * (1.0 - f) + 0.5 * pressure)
        return self.rng.random() >= decline_prob

    def reseek_on_break(self, archetype: str) -> bool:
        return True


def make_behavior(name: str = "default", *, seed: int = 0, **kwargs) -> PlayerBehaviorPolicy:
    """Config switch -> behavior policy instance."""
    if name == "default":
        return DefaultBehaviorPolicy()
    if name in ("fit_aware", "fit-aware"):
        return FitAwareBehaviorPolicy(seed=seed, **kwargs)
    raise ValueError(f"unknown behavior {name!r}")
