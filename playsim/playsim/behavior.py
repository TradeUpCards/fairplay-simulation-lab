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
from typing import Literal, Protocol, runtime_checkable

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
    table_mode: str = "active"
    target_seats: int | None = None


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

    def accept_forming_seat(self, offer: SeatOffer) -> bool:
        """Return True to seed/join a forming or intentionally short table."""
        ...

    def should_leave(self, ctx: LeaveContext) -> tuple[bool, str]:
        """Return (leaving, reason). reason is "" when not leaving."""
        ...

    def reseek_on_break(self, archetype: str) -> bool:
        """Return True if a player displaced by a table break re-seeks a seat."""
        ...

    def exit_action(self, reason: str, archetype: str) -> Literal["terminal", "reseek"]:
        """Return whether an exit reason ends the player's day or means they
        still want a different seat."""
        ...

    def wait_tolerance_min(self, reason: str, archetype: str) -> float:
        """How long a re-seeking player will wait before finally balking."""
        ...


class DefaultBehaviorPolicy:
    """Behavior-preserving baseline — exactly today's rules."""

    name = "default"

    def accept_seat(self, offer: SeatOffer) -> bool:
        return True  # forced placement: a seeker always takes the offered seat

    def accept_forming_seat(self, offer: SeatOffer) -> bool:
        return self.accept_seat(offer)

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

    def exit_action(self, reason: str, archetype: str) -> Literal["terminal", "reseek"]:
        return "reseek" if reason == "table_break" else "terminal"

    def wait_tolerance_min(self, reason: str, archetype: str) -> float:
        return 0.0


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

    def accept_forming_seat(self, offer: SeatOffer) -> bool:
        return self.accept_seat(offer)

    def reseek_on_break(self, archetype: str) -> bool:
        return True

    def exit_action(self, reason: str, archetype: str) -> Literal["terminal", "reseek"]:
        return "reseek" if reason == "table_break" else "terminal"

    def wait_tolerance_min(self, reason: str, archetype: str) -> float:
        return 0.0


class ReasonAwareBehaviorPolicy(FitAwareBehaviorPolicy):
    """Reason-aware lifecycle model.

    Separates "done for the day" exits from "done with this table" exits:

    * tilt/bleed, profit-taking, and time-budget completion are terminal;
    * table-thinning, table-break displacement, bad-fit decline, and boredom are
      re-seek reasons with a finite wait tolerance.

    This is intentionally still parametric and seeded. It is a design/probing
    model, not calibrated real-world behavior.
    """

    name = "reason_aware"

    def __init__(
        self,
        *,
        w_pressure: float = 0.15,
        w_fit: float = 0.10,
        decline_enabled: bool = False,
        decline_strength: float = 0.6,
        seed: int = 0,
        profit_take_bb: float = 80.0,
        min_profit_take_min: float = 25.0,
        thinning_wait_min: float = 18.0,
        break_wait_min: float = 24.0,
        decline_wait_min: float = 10.0,
        boredom_wait_min: float = 12.0,
    ) -> None:
        super().__init__(
            w_pressure=w_pressure,
            w_fit=w_fit,
            decline_enabled=decline_enabled,
            decline_strength=decline_strength,
            seed=seed,
        )
        self.profit_take_bb = profit_take_bb
        self.min_profit_take_min = min_profit_take_min
        self.thinning_wait_min = thinning_wait_min
        self.break_wait_min = break_wait_min
        self.decline_wait_min = decline_wait_min
        self.boredom_wait_min = boredom_wait_min

    def should_leave(self, ctx: LeaveContext) -> tuple[bool, str]:
        if ctx.archetype not in _COHORT:
            return (False, "")

        if ctx.net_bb >= self.profit_take_bb and ctx.seat_minutes >= self.min_profit_take_min:
            return (True, "profit_taking")

        # A thin, still-dealing table is a "find a better table" reason, not a
        # player being done. This is evaluated before tilt so thin-table churn is
        # attributed separately from bleed.
        if (
            ctx.seated_count <= 2
            and ctx.max_seats >= 4
            and ctx.seat_minutes >= 5.0
        ):
            return (True, "table_thinning")

        hp = ctx.hands_played
        loss100 = (-ctx.net_bb) / (hp / 100.0) if hp >= 15 else 0.0
        pressure = table_pressure(ctx.table_archetypes, ctx.seated_count, ctx.max_seats)

        if (
            ctx.seated_count <= 3
            and ctx.seat_minutes >= 30.0
            and loss100 <= 0.0
            and pressure < 0.25
        ):
            return (True, "boredom_low_action")

        leaving, reason = super().should_leave(ctx)
        if not leaving:
            return (False, "")
        if reason == "session_complete":
            return (True, "time_budget_complete")
        if reason == "tilt":
            return (True, "tilt_bleed")
        return (True, reason)

    def exit_action(self, reason: str, archetype: str) -> Literal["terminal", "reseek"]:
        if reason in {"table_thinning", "table_break", "bad_fit_decline", "boredom_low_action"}:
            return "reseek"
        return "terminal"

    def wait_tolerance_min(self, reason: str, archetype: str) -> float:
        if reason == "table_break":
            return self.break_wait_min
        if reason == "table_thinning":
            return self.thinning_wait_min
        if reason == "bad_fit_decline":
            return self.decline_wait_min
        if reason == "boredom_low_action":
            return self.boredom_wait_min
        return 0.0


FORMATION_WILLINGNESS_DEFAULTS = {
    # Uncalibrated defaults: directional priors only. Stronger / high-volume
    # players tolerate short-handed tables; newer casual players prefer fuller
    # tables with more social/liquidity comfort.
    "new": 0.20,
    "recreational": 0.30,
    "promo_hunter": 0.35,
    "shared_device_household": 0.35,
    "regular": 0.55,
    "healthy_anchor": 0.55,
    "grinder": 0.72,
    "aggressive_predatory": 0.78,
    "solver_like": 0.70,
    "cluster_member": 0.60,
    "bot_like": 0.65,
}


class FormationAwareBehaviorPolicy(ReasonAwareBehaviorPolicy):
    """Reason-aware lifecycle plus short/forming-table acceptance propensity.

    This is opt-in and illustrative until calibrated. It is intentionally separate
    from the default/reason-aware policies so existing flags-off behavior remains
    byte-identical.
    """

    name = "formation_aware"

    def __init__(
        self,
        *,
        formation_willingness: dict[str, float] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.formation_willingness = dict(FORMATION_WILLINGNESS_DEFAULTS)
        if formation_willingness:
            self.formation_willingness.update(formation_willingness)

    def accept_forming_seat(self, offer: SeatOffer) -> bool:
        short_candidate = offer.table_mode == "forming" or offer.seated_count <= 2
        if not short_candidate:
            return self.accept_seat(offer)
        willingness = max(0.0, min(1.0, self.formation_willingness.get(offer.archetype, 0.5)))
        return self.rng.random() < willingness


def make_behavior(name: str = "default", *, seed: int = 0, **kwargs) -> PlayerBehaviorPolicy:
    """Config switch -> behavior policy instance."""
    if name == "default":
        return DefaultBehaviorPolicy()
    if name in ("fit_aware", "fit-aware"):
        return FitAwareBehaviorPolicy(seed=seed, **kwargs)
    if name in ("reason_aware", "reason-aware"):
        return ReasonAwareBehaviorPolicy(seed=seed, **kwargs)
    if name in ("formation_aware", "formation-aware"):
        return FormationAwareBehaviorPolicy(seed=seed, **kwargs)
    raise ValueError(f"unknown behavior {name!r}")
