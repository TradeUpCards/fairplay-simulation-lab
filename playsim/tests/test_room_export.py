"""U6 — canonical room_sim builder + agent provenance (and U7 v1 adapter)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from playsim.policies import StandardPolicy, make_policy
from playsim.room import run_room
from playsim.room_export import build_canonical, derive_room_metrics
from playsim.router_adapter import RouterAdapter

REPO = Path(__file__).resolve().parents[2]
TABLES = ["T-11", "T-8", "T-22"]


@pytest.fixture(scope="module")
def adapter() -> RouterAdapter:
    try:
        return RouterAdapter()
    except Exception:
        return RouterAdapter(REPO)


def _canonical(policy, horizon=120, **kw):
    r = run_room(policy, master_seed=42, horizon_min=horizon,
                 equity_samples=6, tables=TABLES, **kw)
    return build_canonical(r, data_root="<fixture>")


def test_canonical_carries_full_causal_trace():
    doc = _canonical(StandardPolicy())
    for key in ("meta", "run_config", "arrival_intents", "routing_decisions",
                "seat_events", "sessions", "hourly", "table_timelines", "summary"):
        assert key in doc
    assert doc["arrival_intents"]          # non-empty
    assert doc["routing_decisions"]
    assert doc["sessions"]
    assert doc["hourly"]                    # hourly rollup present for a 120-min run


def test_agent_provenance_stamped():
    doc = _canonical(StandardPolicy())
    assert doc["meta"]["agent_model"] == "archetype-knobs"
    assert doc["meta"]["agent_version"] == "v1"


def test_summary_has_primary_and_secondary_metrics():
    doc = _canonical(StandardPolicy())
    s = doc["summary"]
    assert s["vulnerable_paid_seat_hours"] >= 0          # primary R21
    for k in ("recreational_loss_velocity_bb_per_100", "beginner_bust_rate_per_100",
              "winnings_concentration", "realized_health_score", "table_breaks",
              "balk_count", "deferred_count"):
        assert k in s


def test_canonical_is_json_serializable():
    doc = _canonical(StandardPolicy())
    blob = json.dumps(doc)            # raises if any non-serializable object leaks
    assert json.loads(blob)["meta"]["engine"] == "playsim"


def test_canonical_is_deterministic():
    a = _canonical(StandardPolicy())
    b = _canonical(StandardPolicy())
    assert a == b


def test_protect_defer_surfaces_in_summary(adapter):
    """A vulnerable seeker sent into short-handed, low-health T-22 under enabled
    protect is deferred, and the canonical summary surfaces the count."""
    from playsim.arrivals import ArrivalIntent, build_arrival_intents

    vuln = next(a for a in build_arrival_intents(120, seed=42)
                if a.archetype in ("new", "recreational"))
    intents = [ArrivalIntent(vuln.player_id, vuln.archetype, 1.0)]

    policy = make_policy("fairplay_protect", adapter, enabled=True, safety_threshold=95.0)
    r = run_room(policy, master_seed=42, horizon_min=20, equity_samples=6,
                 tables=["T-22"], arrival_intents=intents)
    doc = build_canonical(r)

    assert r.deferred == [vuln.player_id]                 # the vulnerable seeker deferred
    assert doc["summary"]["deferred_count"] == len(r.deferred)        # plumbing
    assert doc["summary"]["balk_count"] == len(r.balked)
    assert doc["summary"]["prevented_bad_sessions"] == doc["summary"]["deferred_count"]


def test_summary_counts_track_room_result():
    """balk/defer counts in the summary always mirror the RoomResult."""
    doc_r = run_room(StandardPolicy(), master_seed=42, horizon_min=60,
                     equity_samples=6, tables=TABLES)
    doc = build_canonical(doc_r)
    assert doc["summary"]["balk_count"] == len(doc_r.balked)
    assert doc["summary"]["deferred_count"] == len(doc_r.deferred) == 0  # standard never defers
    assert doc["summary"]["wait_balk_count"] == len(doc_r.wait_balked)


# --- Phase 3: cohort acceptance funnel -----------------------------------

def test_funnel_present_and_sums():
    doc = _canonical(StandardPolicy())
    f = doc["summary"]["funnel"]
    assert set(f) == {"offered", "accepted", "declined", "balked", "deferred"}
    # every cohort arrival is exactly one outcome
    assert f["offered"] == f["accepted"] + f["declined"] + f["balked"] + f["deferred"]
    assert f["declined"] == 0  # default behavior never declines
    assert doc["summary"]["declined_count"] == 0


def test_exit_funnel_present():
    doc = _canonical(StandardPolicy())
    f = doc["summary"]["exit_funnel"]
    assert {"exits_by_reason", "terminal_exits", "reseek_exits",
            "reseek_attempts_by_reason", "reseek_success_by_reason",
            "wait_balks"} <= set(f)


def test_funnel_captures_declines_when_enabled(adapter):
    from playsim.behavior import FitAwareBehaviorPolicy
    from playsim.room import run_room
    r = run_room(make_policy("fairplay_route", adapter), master_seed=42, horizon_min=120,
                 equity_samples=6, tables=["T-11", "T-8", "T-22", "T-1", "T-3", "T-5"],
                 behavior=FitAwareBehaviorPolicy(decline_enabled=True, decline_strength=1.0, seed=42))
    doc = build_canonical(r)
    f = doc["summary"]["funnel"]
    assert f["offered"] == f["accepted"] + f["declined"] + f["balked"] + f["deferred"]
    assert f["declined"] >= 1                                   # decline channel active
    assert doc["summary"]["declined_count"] == len(r.declined)


# --- U7: derived v1 room_metrics adapter ---------------------------------

def test_v1_adapter_is_pure_function_of_canonical():
    doc = _canonical(StandardPolicy())
    a = derive_room_metrics(doc)
    b = derive_room_metrics(doc)
    assert a == b                       # same canonical in -> same v1 out, no I/O


def test_v1_adapter_schema_matches_existing_fixture():
    fixture = json.loads((REPO / "data/room_metrics_standard.json").read_text())
    v1 = derive_room_metrics(_canonical(StandardPolicy()))
    assert set(v1) == set(fixture)                       # {meta, hours}
    assert set(v1["hours"][0]) == set(fixture["hours"][0])  # per-hour field parity


def test_v1_adapter_value_and_unit_fidelity():
    doc = _canonical(StandardPolicy())
    v1 = derive_room_metrics(doc)
    last = v1["hours"][-1]
    # cumulative paid seat-time is an int in minutes, matching canonical's final hour
    assert isinstance(last["cumulative_paid_seat_time_minutes"], int)
    assert last["cumulative_paid_seat_time_minutes"] == int(round(
        doc["hourly"][-1]["cumulative_paid_seat_min"]))
    # retention is an int percentage in [0, 100]
    assert isinstance(last["new_player_retention_pct"], int)
    assert 0 <= last["new_player_retention_pct"] <= 100
    # active players a non-negative int
    assert isinstance(last["active_players"], int) and last["active_players"] >= 0


def test_v1_adapter_path_label_from_policy(adapter):
    std = derive_room_metrics(_canonical(StandardPolicy()))
    fp = derive_room_metrics(_canonical(make_policy("fairplay_route", adapter)))
    assert std["meta"]["path"] == "standard"
    assert fp["meta"]["path"] == "fairplay"
