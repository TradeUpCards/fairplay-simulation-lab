"""Phase 1 — PlayerBehaviorPolicy seam.

DefaultBehaviorPolicy must reproduce the prior behavior exactly (the room loop
now calls the seam instead of inline rules), and a custom policy must be able to
change accept / leave / re-seek behavior through the same interface.
"""

from __future__ import annotations

from playsim.behavior import DefaultBehaviorPolicy, LeaveContext, SeatOffer
from playsim.policies import StandardPolicy
from playsim.room import run_room

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
    assert all(d["table_id"] is None and d["reason"] == "declined" for d in arrivals)
