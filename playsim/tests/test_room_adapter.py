"""U2 — cross-package router adapter.

Exercises the only playsim<->backend seam: id conversion, scorer-input assembly,
composition-driven predicted health (P_bleed=0), the integrity gate (AE4), and
balk derivation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from playsim.population import format_player_id, parse_player_id
from playsim.router_adapter import RouterAdapter, make_table_dict

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def adapter() -> RouterAdapter:
    try:
        return RouterAdapter()
    except Exception:
        return RouterAdapter(REPO)


def _table(tid, seated, max_seats=6, style="moderate", trend="stable"):
    return make_table_dict(
        tid, seated, max_seats,
        style_volatility_label=style, paid_seat_time_trend=trend,
    )


def test_id_seam_roundtrips():
    for n in (1, 62, 104, 198, 200):
        assert parse_player_id(format_player_id(n)) == n
    assert format_player_id(104) == "P-104"


def test_make_table_dict_carries_scorer_fields():
    t = _table(None, [62, 70, 71], max_seats=6)
    assert t["style_volatility_label"] == "moderate"
    assert t["paid_seat_time_trend"] == "stable"
    assert t["seated_player_ids"] == ["P-62", "P-70", "P-71"]
    assert t["seated_count"] == 3
    assert t["open_seats"] == 3


def test_predicted_health_is_composition_only_pbleed_zero(adapter):
    t = _table("T-x", [62, 70, 71, 72], max_seats=6)
    health = adapter.predicted_health([t])
    assert "T-x" in health
    assert health["T-x"].terms["P_bleed"] == 0  # sessions=None -> no realized bleed


def test_trend_is_a_real_router_input(adapter):
    """Same seating, different paid_seat_time_trend -> different predicted health,
    proving the trend field actually reaches the scorer (guards the silent-default
    collapse)."""
    growing = _table("T-g", [62, 70, 71], max_seats=6, trend="growing")
    declining = _table("T-d", [62, 70, 71], max_seats=6, trend="declining")
    h = adapter.predicted_health([growing, declining])
    assert h["T-g"].health != h["T-d"].health


def test_recommend_never_routes_to_gated_cluster(adapter):
    """AE4: a table holding the high-band cluster CL-001 (P-198/199/200) is
    integrity-gated and must never be returned as a FairPlay placement."""
    gated = _table("T-gate", [198, 199, 200], max_seats=6)        # 3 open
    healthy = _table("T-safe", [62, 70], max_seats=6)             # 4 open
    placement = adapter.recommend(104, [gated, healthy])
    assert placement.table_id == "T-safe"
    assert placement.table_id != "T-gate"
    # and the gated table is present-but-marked in the operator trace
    gated_entry = next(e for e in placement.operator_view if e["table_id"] == "T-gate")
    assert gated_entry["integrity_gated"] is True


def test_recommend_balks_when_no_open_seat(adapter):
    full = _table("T-full", [62, 70, 71, 72, 73, 60], max_seats=6)  # 0 open
    placement = adapter.recommend(104, [full])
    assert placement.balked
    assert placement.table_id is None


def test_recommend_full_set_no_keyerror(adapter):
    tables = [
        _table("T-a", [62, 70], max_seats=6),
        _table("T-b", [71, 72, 73], max_seats=6),
        _table("T-c", [60, 61], max_seats=6),
    ]
    placement = adapter.recommend(104, tables)
    assert placement.table_id in {"T-a", "T-b", "T-c"}
    assert placement.health is not None


def test_cbi_computed_once_and_reused(adapter):
    cbi_before = adapter.cbi
    adapter.recommend(104, [_table("T-a", [62, 70], max_seats=6)])
    adapter.recommend(105, [_table("T-a", [62, 70], max_seats=6)])
    assert adapter.cbi is cbi_before  # not rebuilt per call
    # CL-001 members carry the high band in the index
    assert adapter.cbi.get("P-198", (None, None))[1] == "high"
