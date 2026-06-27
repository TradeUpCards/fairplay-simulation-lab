from __future__ import annotations

import copy

from analysis.scoring_sensitivity_sweep import (
    VARIANTS,
    run_scoring_sensitivity_sweep,
    scoring_variant_scope,
)
from playsim.router_adapter import _ensure_backend_on_path


def test_scoring_variant_scope_restores_backend_constants(tmp_path):
    _ensure_backend_on_path(tmp_path)
    import scoring.health as health
    import scoring.router as router
    import scoring.seating as seating

    original_frag_w = health.FRAG_W_OCC
    original_health_p_frag = health.p_frag
    original_seating_p_frag = seating.p_frag
    original_router_weights = (router.W_FIT, router.W_HEALTH, router.W_DELTA)
    original_short_pref = dict(seating.SHORT_TABLE_PREF)

    with scoring_variant_scope(tmp_path, VARIANTS["router_liveness_heavy"]):
        assert (router.W_FIT, router.W_HEALTH, router.W_DELTA) == (0.20, 0.55, 0.25)

    with scoring_variant_scope(tmp_path, VARIANTS["short_active_grace"]):
        assert seating.p_frag is not original_seating_p_frag

    assert health.FRAG_W_OCC == original_frag_w
    assert health.p_frag is original_health_p_frag
    assert seating.p_frag is original_seating_p_frag
    assert (router.W_FIT, router.W_HEALTH, router.W_DELTA) == original_router_weights
    assert seating.SHORT_TABLE_PREF == original_short_pref


def test_scoring_sensitivity_sweep_smoke_is_deterministic(tmp_path):
    kwargs = dict(
        data_root=tmp_path / "fixture",
        fixture_seed=13,
        variants=["baseline", "frag_soft"],
        seeds=[5],
        arrival_rates_per_hour=[18.0],
        horizon_min=20.0,
        equity_samples=3,
        policies=("standard", "fairplay_liveness"),
        players=140,
        tables=12,
        active_tables=8,
        regenerate_fixture=True,
    )
    first = run_scoring_sensitivity_sweep(**kwargs)
    second = run_scoring_sensitivity_sweep(**kwargs)

    comparable_first = copy.deepcopy(first)
    comparable_second = copy.deepcopy(second)
    comparable_first["meta"].pop("generated_at", None)
    comparable_second["meta"].pop("generated_at", None)
    assert comparable_first == comparable_second
    assert first["meta"]["deterministic"] is True
    assert len(first["variants"]) == 2
    assert len(first["runs"]) == 4
    assert len(first["comparison_summary"]) == 2
    assert {
        row["policy"] for row in first["comparison_summary"]
    } == {"fairplay_liveness"}
    for row in first["comparison_summary"]:
        assert "tradeoff" in row
        assert row["tradeoff"]["status"] in {
            "tradeoff",
            "clean_win",
            "no_vulnerable_gain",
            "no_cost",
        }
