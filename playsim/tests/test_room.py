"""U5 — room orchestrator (per-hand multi-table loop)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from playsim import room as room_module
from playsim.arrivals import build_arrival_intents
from playsim.policies import StandardPolicy, make_policy
from playsim.room import COHORT, run_room
from playsim.router_adapter import RouterAdapter

REPO = Path(__file__).resolve().parents[2]
TABLES = ["T-11", "T-8", "T-22"]


@pytest.fixture(scope="module")
def adapter() -> RouterAdapter:
    try:
        return RouterAdapter()
    except Exception:
        return RouterAdapter(REPO)


def _standard_run(seed=42, horizon=40):
    return run_room(StandardPolicy(), master_seed=seed, horizon_min=horizon,
                    equity_samples=6, tables=TABLES)


def test_room_run_is_deterministic():
    a = _standard_run()
    b = _standard_run()
    assert a.routing_decisions == b.routing_decisions
    assert a.seat_events == b.seat_events
    assert a.sessions == b.sessions
    assert a.net_bb == b.net_bb
    assert a.hands_total == b.hands_total
    assert a.left_at_minute == b.left_at_minute


def test_room_different_seed_differs():
    a = _standard_run(seed=42)
    b = _standard_run(seed=99)
    assert (a.routing_decisions, a.net_bb) != (b.routing_decisions, b.net_bb)


def test_fairplay_route_run_is_deterministic(adapter):
    a = run_room(make_policy("fairplay_route", adapter), master_seed=42,
                 horizon_min=40, equity_samples=6, tables=TABLES)
    b = run_room(make_policy("fairplay_route", adapter), master_seed=42,
                 horizon_min=40, equity_samples=6, tables=TABLES)
    assert a.routing_decisions == b.routing_decisions
    assert a.sessions == b.sessions
    assert a.net_bb == b.net_bb


def test_checkpoints_captured_and_consistent():
    r = run_room(StandardPolicy(), master_seed=42, horizon_min=30,
                 equity_samples=6, tables=TABLES, checkpoints_min=(10.0, 20.0, 30.0))
    assert set(r.checkpoints) == {"10min", "20min", "30min"}
    for snap in r.checkpoints.values():
        assert snap["active_players"] >= 0
        assert snap["cumulative_paid_seat_min"] >= 0
        assert snap["hands_total"] >= 0


def test_cohort_paid_seat_time_is_present_and_positive():
    r = _standard_run()
    cohort_min = sum(r.seat_minutes[p] for p in r.seat_minutes
                     if r.archetype_of.get(p) in COHORT)
    assert cohort_min > 0


def test_sessions_are_well_formed():
    r = _standard_run()
    assert r.sessions
    for s in r.sessions:
        assert {"player_id", "table_id", "start_min", "end_min",
                "duration_min", "hands", "net_bb", "exit_reason"} <= set(s)
        assert s["duration_min"] >= 0
        assert s["exit_reason"] in {
            "tilt", "break", "horizon", "tilt_bleed", "table_pressure",
            "mismatch", "time_budget_complete", "profit_taking",
            "table_thinning", "boredom_low_action",
        }


def test_shared_arrival_stream_across_arms(adapter):
    """Both arms must consume the identical injected arrival stream (only
    placement differs)."""
    intents = build_arrival_intents(40, seed=42)
    std = run_room(StandardPolicy(), master_seed=42, horizon_min=40,
                   equity_samples=6, tables=TABLES, arrival_intents=intents)
    fp = run_room(make_policy("fairplay_route", adapter), master_seed=42,
                  horizon_min=40, equity_samples=6, tables=TABLES,
                  arrival_intents=intents)
    assert std.arrival_intents == fp.arrival_intents == intents


def test_room_requires_minimum_population():
    """An empty/unmatched table set must fail loudly, not emit a silently-empty
    'successful' comparison."""
    from playsim.room import RoomSim
    with pytest.raises(ValueError):
        RoomSim(StandardPolicy(), master_seed=42, horizon_min=10,
                equity_samples=6, tables=["T-does-not-exist"])


def test_fairplay_decisions_carry_minimal_rationale(adapter):
    """A backend-routed seat records the chosen table's rank breakdown (default),
    so the trace answers 'why this table?' — without the full candidate list."""
    r = run_room(make_policy("fairplay_route", adapter), master_seed=42,
                 horizon_min=40, equity_samples=6, tables=TABLES)
    seated = [d for d in r.routing_decisions if d["table_id"] is not None]
    assert seated, "expected at least one seated FairPlay routing decision"
    d = seated[0]
    assert set(d["rationale"]) == {"rank", "health", "delta_health",
                                   "seating_risk", "badge", "integrity_gated"}
    assert "candidates" not in d        # full candidate list stays out of the default trace


def test_standard_decisions_have_no_rationale():
    r = _standard_run()
    assert all("rationale" not in d for d in r.routing_decisions)  # no backend = no rationale


def test_debug_trace_adds_full_candidate_list(adapter):
    r = run_room(make_policy("fairplay_route", adapter), master_seed=42,
                 horizon_min=40, equity_samples=6, tables=TABLES, debug_trace=True)
    seated = [d for d in r.routing_decisions if d["table_id"] is not None]
    assert any("candidates" in d and d["candidates"] for d in seated)


def test_routing_never_consults_realized_health():
    """Structural guardrail: the orchestrator must not import playsim/health.py —
    routing uses only backend predicted health via the policy/adapter."""
    src = inspect.getsource(room_module)
    assert "from .health" not in src
    assert "import health" not in src
    assert "playsim.health" not in src


def test_reasonaware_table_thinning_reseek_path():
    class ThinTableLeave:
        name = "thin-table-test"
        def accept_seat(self, offer): return True
        def should_leave(self, ctx):
            if ctx.archetype in COHORT and ctx.seat_minutes >= 0.75:
                return (True, "table_thinning")
            return (False, "")
        def reseek_on_break(self, archetype): return True
        def exit_action(self, reason, archetype):
            return "reseek" if reason == "table_thinning" else "terminal"
        def wait_tolerance_min(self, reason, archetype):
            return 3.0 if reason == "table_thinning" else 0.0

    r = run_room(StandardPolicy(), master_seed=42, horizon_min=6,
                 equity_samples=6, tables=["T-22"], behavior=ThinTableLeave())
    assert any(s["exit_reason"] == "table_thinning" for s in r.sessions)
    assert any(d["origin"] == "table_thinning" for d in r.routing_decisions)
    assert any(e["event"] == "seat" and e["origin"] == "table_thinning"
               for e in r.seat_events)
