"""U6 — canonical room_sim builder + agent provenance (and U7 v1 adapter)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from playsim.policies import StandardPolicy, make_policy
from playsim.room import run_room
from playsim.room_export import build_canonical
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
