"""U4 — seating policy seam (Standard, FairPlay-route, FairPlay-protect)."""

from __future__ import annotations

from pathlib import Path

import pytest

from playsim.policies import (
    FairPlayProtectPolicy,
    FairPlayRoutePolicy,
    Seeker,
    StandardPolicy,
    make_policy,
)
from playsim.router_adapter import RouterAdapter, make_table_dict

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def adapter() -> RouterAdapter:
    try:
        return RouterAdapter()
    except Exception:
        return RouterAdapter(REPO)


def _table(tid, seated, max_seats=6, style="moderate", trend="stable"):
    return make_table_dict(tid, seated, max_seats,
                           style_volatility_label=style, paid_seat_time_trend=trend)


# --- Standard -------------------------------------------------------------

def test_standard_picks_most_full_open_table():
    pol = StandardPolicy()
    tables = [
        _table("T-1", [62], max_seats=6),            # 1 seated
        _table("T-2", [70, 71, 72], max_seats=6),    # 3 seated (fullest)
        _table("T-3", [60, 61], max_seats=6),        # 2 seated
    ]
    d = pol.choose(Seeker(104, "new"), tables)
    assert d.table_id == "T-2"


def test_standard_tie_break_lowest_table_id():
    pol = StandardPolicy()
    tables = [
        _table("T-9", [70, 71, 72], max_seats=6),
        _table("T-2", [60, 61, 62], max_seats=6),    # same count, lower id wins
    ]
    d = pol.choose(Seeker(104, "new"), tables)
    assert d.table_id == "T-2"


def test_standard_balks_only_when_room_full():
    pol = StandardPolicy()
    full = _table("T-1", [62, 70, 71, 72, 73, 60], max_seats=6)  # 0 open
    d = pol.choose(Seeker(104, "new"), [full])
    assert not d.seated and not d.deferred and d.reason == "no_open_seat"


# --- FairPlay-route (AE2) -------------------------------------------------

def test_route_seats_best_available_when_healthy_tables_full(adapter):
    """AE2: a vulnerable seeker is seated at the best available non-gated table
    even when the only open table is unhealthy — route never balks while a
    non-gated seat exists."""
    healthy_full = _table("T-healthy", [62, 70, 71, 72, 73, 60], max_seats=6)  # 0 open
    unhealthy_open = _table("T-rough", [176, 177], max_seats=6, trend="declining")  # open
    pol = FairPlayRoutePolicy(adapter)
    d = pol.choose(Seeker(104, "new"), [healthy_full, unhealthy_open])
    assert d.table_id == "T-rough"
    assert d.seated


def test_route_never_selects_gated_table(adapter):
    gated = _table("T-gate", [198, 199, 200], max_seats=6)
    ok = _table("T-ok", [62, 70], max_seats=6)
    pol = FairPlayRoutePolicy(adapter)
    d = pol.choose(Seeker(104, "new"), [gated, ok])
    assert d.table_id == "T-ok"


# --- FairPlay-protect (AE3) ----------------------------------------------

def test_protect_defers_below_threshold_else_seats(adapter):
    """AE3: with protect enabled, a vulnerable seeker is deferred when the best
    available predicted health is below the safety threshold; raising the bar
    above the table's health defers, lowering it seats."""
    seeker = Seeker(104, "new")  # vulnerable (new)
    table = _table("T-low", [176, 177], max_seats=6, trend="declining")
    h = adapter.predicted_health([table])["T-low"].health

    strict = FairPlayProtectPolicy(adapter, enabled=True, safety_threshold=h + 10)
    d_defer = strict.choose(seeker, [table])
    assert d_defer.deferred and d_defer.table_id is None
    assert d_defer.reason == "protect_deferred"

    lax = FairPlayProtectPolicy(adapter, enabled=True, safety_threshold=h - 10)
    assert lax.choose(seeker, [table]).table_id == "T-low"


def test_protect_disabled_behaves_like_route(adapter):
    seeker = Seeker(104, "new")
    table = _table("T-low", [176, 177], max_seats=6, trend="declining")
    h = adapter.predicted_health([table])["T-low"].health
    off = FairPlayProtectPolicy(adapter, enabled=False, safety_threshold=h + 10)
    assert off.choose(seeker, [table]).table_id == "T-low"   # would defer if enabled


def test_protect_does_not_defer_non_vulnerable(adapter):
    grinder = Seeker(50, "grinder")  # not in VULNERABLE_ARCHETYPES
    table = _table("T-low", [176, 177], max_seats=6, trend="declining")
    h = adapter.predicted_health([table])["T-low"].health
    strict = FairPlayProtectPolicy(adapter, enabled=True, safety_threshold=h + 10)
    assert strict.choose(grinder, [table]).table_id == "T-low"  # seated, not deferred


# --- config switch --------------------------------------------------------

def test_make_policy_switch(adapter):
    assert isinstance(make_policy("standard"), StandardPolicy)
    assert isinstance(make_policy("fairplay_route", adapter), FairPlayRoutePolicy)
    assert isinstance(make_policy("fairplay_protect", adapter, enabled=True),
                      FairPlayProtectPolicy)
    with pytest.raises(ValueError):
        make_policy("fairplay_route")  # adapter required
