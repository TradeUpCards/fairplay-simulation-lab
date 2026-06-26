"""Phase 1 — PlayerBehaviorPolicy seam.

DefaultBehaviorPolicy must reproduce the prior behavior exactly (the room loop
now calls the seam instead of inline rules), and a custom policy must be able to
change accept / leave / re-seek behavior through the same interface.
"""

from __future__ import annotations

from playsim.behavior import (
    DefaultBehaviorPolicy,
    FitAwareBehaviorPolicy,
    FormationAwareBehaviorPolicy,
    LeaveContext,
    ReasonAwareBehaviorPolicy,
    SeatOffer,
    make_behavior,
    style_fit,
    style_volatility,
    table_pressure,
)
from playsim.policies import StandardPolicy
from playsim.room import COHORT, run_room

TABLES = ["T-11", "T-8", "T-22"]


def _run(behavior=None):
    return run_room(StandardPolicy(), master_seed=42, horizon_min=40,
                    equity_samples=6, tables=TABLES, behavior=behavior)


def test_default_behavior_is_behavior_preserving():
    a = _run()                          # implicit DefaultBehaviorPolicy
    b = _run(DefaultBehaviorPolicy())   # explicit
    assert a.sessions == b.sessions
    assert a.net_bb == b.net_bb
    assert a.seat_minutes == b.seat_minutes
    assert a.left_at_minute == b.left_at_minute
    assert a.routing_decisions == b.routing_decisions


def test_default_policy_unit_rules():
    p = DefaultBehaviorPolicy()
    # non-cohort never voluntarily leaves, even deeply stuck
    assert p.should_leave(LeaveContext("grinder", 9999, -9999, 999, 0.05, 1.0)) == (False, "")
    # a cohort player past budget leaves, tagged 'tilt'
    leaving, reason = p.should_leave(LeaveContext("new", 9999, -9999, 999, 0.8, 1.0))
    assert leaving and reason == "tilt"
    # forced placement + re-seek once
    assert p.accept_seat(SeatOffer("new", "T-1", None)) is True
    assert p.accept_forming_seat(SeatOffer("new", "T-1", None, table_mode="forming")) is True
    assert p.reseek_on_break("new") is True


def test_custom_policy_can_suppress_leaving():
    class NeverLeave:
        name = "never-leave"
        def accept_seat(self, offer): return True
        def should_leave(self, ctx): return (False, "")
        def reseek_on_break(self, archetype): return True

    r = _run(NeverLeave())
    assert all(s["exit_reason"] != "tilt" for s in r.sessions)  # nobody tilted out


def test_custom_policy_can_decline_seats():
    class AlwaysDecline:
        name = "decline"
        def accept_seat(self, offer): return False
        def should_leave(self, ctx): return (False, "")
        def reseek_on_break(self, archetype): return True

    r = _run(AlwaysDecline())
    arrivals = [d for d in r.routing_decisions if d["origin"] == "arrival"]
    assert arrivals
    assert all(d["table_id"] is None and d["reason"] == "bad_fit_decline" for d in arrivals)


# --- Phase 2: fit-aware model --------------------------------------------

def test_fitaware_zero_weights_reduces_to_default():
    """R8: with pressure/fit weights 0 the leave *decisions* match Default exactly
    (only the exit-reason label may be finer-grained)."""
    base = _run(DefaultBehaviorPolicy())
    fa = _run(FitAwareBehaviorPolicy(w_pressure=0.0, w_fit=0.0))
    assert fa.seat_minutes == base.seat_minutes
    assert fa.left_at_minute == base.left_at_minute
    assert fa.net_bb == base.net_bb
    strip = lambda S: [{k: v for k, v in s.items() if k != "exit_reason"} for s in S]
    assert strip(fa.sessions) == strip(base.sessions)


def test_pressure_and_fit_helpers():
    assert style_volatility("High Volatility / Predatory-Mix") > \
        style_volatility("Low Stakes / Beginner-Friendly")
    # a 'new' player fits a friendly table better than a predatory one
    assert style_fit("new", "Low Stakes / Beginner-Friendly") > \
        style_fit("new", "High Volatility / Predatory-Mix")
    # predator-heavy table has higher composition pressure than a fishy one
    assert table_pressure(("aggressive_predatory", "grinder", "new"), 3, 6) > \
        table_pressure(("recreational", "recreational", "new"), 3, 6)
    assert style_fit("grinder", "anything") == 0.5   # non-cohort: neutral


def test_fitaware_pressure_shortens_session_budget():
    """A 'new' player leaves at a lower seat-minutes threshold at a high-pressure
    table than a low-pressure one (deterministic, no losses)."""
    pol = FitAwareBehaviorPolicy(w_pressure=0.4, w_fit=0.0)

    def leave_threshold(archs):
        for sm in range(0, 300):
            leaving, _ = pol.should_leave(LeaveContext(
                "new", float(sm), 0.0, 5, 0.8, 1.0,
                table_archetypes=archs, table_style="", seated_count=3, max_seats=6))
            if leaving:
                return sm
        return 999

    predator = ("aggressive_predatory", "aggressive_predatory", "new")
    friendly = ("recreational", "recreational", "new")
    assert leave_threshold(predator) < leave_threshold(friendly)


def test_fitaware_attributes_pressure_reason():
    pol = FitAwareBehaviorPolicy(w_pressure=0.5, w_fit=0.0)
    leaving, reason = pol.should_leave(LeaveContext(
        "new", 9999, 0.0, 5, 0.8, 1.0,
        table_archetypes=("aggressive_predatory", "aggressive_predatory", "new"),
        table_style="", seated_count=3, max_seats=6))
    assert leaving and reason == "table_pressure"


def test_fitaware_decline_default_off_and_seeded_when_on():
    offer = SeatOffer("new", "T", None,
                      table_archetypes=("aggressive_predatory", "aggressive_predatory"),
                      table_style="High Volatility / Predatory-Mix", seated_count=2, max_seats=6)
    assert FitAwareBehaviorPolicy().accept_seat(offer) is True   # decline OFF by default
    # enabled: high pressure + strength -> some declines, and seeded -> reproducible
    seq1 = [FitAwareBehaviorPolicy(decline_enabled=True, decline_strength=1.0, seed=7)
            for _ in range(1)][0]
    a = [seq1.accept_seat(offer) for _ in range(20)]
    b_pol = FitAwareBehaviorPolicy(decline_enabled=True, decline_strength=1.0, seed=7)
    b = [b_pol.accept_seat(offer) for _ in range(20)]
    assert a == b and any(x is False for x in a)


def test_fitaware_cohort_only():
    pol = FitAwareBehaviorPolicy(w_pressure=0.5, w_fit=0.5)
    # a non-cohort player never voluntarily leaves
    assert pol.should_leave(LeaveContext("grinder", 9999, -9999, 999, 0.05, 1.0,
                                         table_archetypes=("aggressive_predatory",),
                                         seated_count=1, max_seats=6)) == (False, "")


def test_make_behavior_factory():
    assert isinstance(make_behavior("default"), DefaultBehaviorPolicy)
    assert isinstance(make_behavior("fit-aware", seed=3), FitAwareBehaviorPolicy)
    assert isinstance(make_behavior("reason-aware", seed=3), ReasonAwareBehaviorPolicy)
    assert isinstance(make_behavior("formation-aware", seed=3), FormationAwareBehaviorPolicy)


def test_formationaware_accepts_forming_seat_by_archetype_propensity():
    offer_new = SeatOffer("new", "T-empty", None, table_mode="forming", seated_count=0, max_seats=6)
    offer_grinder = SeatOffer("grinder", "T-empty", None, table_mode="forming",
                              seated_count=0, max_seats=6)
    pol = FormationAwareBehaviorPolicy(
        seed=7,
        formation_willingness={"new": 0.0, "grinder": 1.0},
    )
    assert pol.accept_forming_seat(offer_new) is False
    assert pol.accept_forming_seat(offer_grinder) is True


# --- Phase 3: reason-aware lifecycle --------------------------------------

def test_reasonaware_exit_taxonomy():
    pol = ReasonAwareBehaviorPolicy()

    leaving, reason = pol.should_leave(LeaveContext(
        "new", 30.0, 100.0, 40, 0.8, 1.0,
        table_archetypes=("new", "recreational", "healthy_anchor"),
        seated_count=3, max_seats=6,
    ))
    assert leaving and reason == "profit_taking"
    assert pol.exit_action(reason, "new") == "terminal"

    leaving, reason = pol.should_leave(LeaveContext(
        "new", 6.0, 0.0, 8, 0.8, 1.0,
        table_archetypes=("new", "healthy_anchor"),
        seated_count=2, max_seats=6,
    ))
    assert leaving and reason == "table_thinning"
    assert pol.exit_action(reason, "new") == "reseek"

    leaving, reason = pol.should_leave(LeaveContext(
        "new", 999.0, -999.0, 200, 0.8, 1.0,
        table_archetypes=("new", "aggressive_predatory", "grinder"),
        seated_count=3, max_seats=6,
    ))
    assert leaving and reason in {"tilt_bleed", "table_pressure", "mismatch"}


def test_reasonaware_wait_tolerances():
    pol = ReasonAwareBehaviorPolicy()
    assert pol.wait_tolerance_min("table_break", "new") > pol.wait_tolerance_min("bad_fit_decline", "new")
    assert pol.wait_tolerance_min("tilt_bleed", "new") == 0.0
