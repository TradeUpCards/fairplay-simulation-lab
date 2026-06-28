from __future__ import annotations

import json
from pathlib import Path

from playsim.agentic import (
    default_spec,
    evaluate_experiment,
    load_spec,
    plan_next_experiment,
    run_agentic_loop,
)
from playsim.cli import main


def _summary_row(policy: str, *, total: float, vulnerable: float, demand: float,
                 departures: float, avg_min: float, terminal: float = 0.0,
                 reseek: float = 0.0) -> dict:
    return {
        "tables": 12,
        "active_tables": 8,
        "arrival_rate_per_hour": 18.0,
        "policy": policy,
        "total_paid_seat_hours_mean": total,
        "vulnerable_paid_seat_hours_mean": vulnerable,
        "demand_drop_rate_mean": demand,
        "departure_rate_per_hour_mean": departures,
        "terminal_churn_rate_per_hour_mean": terminal,
        "reseek_departure_rate_per_hour_mean": reseek,
        "formation_activation_count_mean": 1.0,
        "estimated_avg_user_session_min_mean": avg_min,
    }


def test_agentic_evaluator_escalates_on_long_user_sessions():
    spec = default_spec()
    spec["autonomy_contract"]["escalate_if"] = {
        "estimated_avg_user_session_min": "> 150"
    }
    payload = {
        "summary": [
            _summary_row(
                "standard",
                total=10.0,
                vulnerable=2.0,
                demand=0.01,
                departures=1.0,
                avg_min=130.0,
            ),
            _summary_row(
                "fairplay_liveness",
                total=12.0,
                vulnerable=3.0,
                demand=0.02,
                departures=1.1,
                avg_min=225.0,
            ),
        ]
    }

    evaluation = evaluate_experiment(payload, spec)

    assert evaluation["verdict"] == "escalate"
    assert evaluation["fairplay_total_seat_hour_win_count"] == 1
    assert evaluation["guardrail_hits"][0]["metric"] == "estimated_avg_user_session_min"
    assert "session" in evaluation["next_recommendation"]


def test_agentic_evaluator_scores_terminal_and_reseek_departure_deltas():
    spec = default_spec()
    spec["autonomy_contract"]["escalate_if"] = {
        "terminal_churn_rate_per_hour_delta": "> 2.0"
    }
    payload = {
        "summary": [
            _summary_row(
                "standard",
                total=10.0,
                vulnerable=2.0,
                demand=0.01,
                departures=1.0,
                terminal=0.8,
                reseek=0.2,
                avg_min=120.0,
            ),
            _summary_row(
                "fairplay_liveness",
                total=12.0,
                vulnerable=3.0,
                demand=0.02,
                departures=3.0,
                terminal=0.7,
                reseek=2.3,
                avg_min=130.0,
            ),
        ]
    }

    evaluation = evaluate_experiment(payload, spec)
    cell = evaluation["cells"][0]

    assert evaluation["verdict"] == "accept_for_holdout"
    assert cell["departure_rate_per_hour_delta"] == 2.0
    assert cell["terminal_churn_rate_per_hour_delta"] == -0.1
    assert cell["reseek_departure_rate_per_hour_delta"] == 2.1


def test_agentic_evaluator_rejects_unknown_guardrail_metric():
    spec = default_spec()
    spec["autonomy_contract"]["escalate_if"] = {
        "departue_rate_typo": "> 0"
    }

    try:
        evaluate_experiment({"summary": []}, spec)
    except ValueError as exc:
        assert "unknown guardrail metric" in str(exc)
    else:
        raise AssertionError("expected unknown guardrail metric to fail closed")


def test_llm_planner_accepts_only_valid_structured_specs(monkeypatch):
    spec = default_spec()
    next_spec = default_spec()
    next_spec["experiment"] = "llm_holdout"
    next_spec["fixed"]["seeds"] = [1042, 1007, 1099]
    evaluation = {
        "verdict": "needs_followup",
        "reason": "mixed cells need diagnosis",
        "cell_count": 1,
        "fairplay_total_seat_hour_win_count": 1,
        "mean_total_paid_seat_hours_delta": 1.0,
        "mean_vulnerable_paid_seat_hours_delta": 0.2,
        "guardrail_hits": [],
        "cells": [],
        "next_recommendation": "run a narrow mechanism sweep",
    }

    def fake_call_openai_planner(*, spec, evaluation, model, api_key=None):
        return {
            "decision": "propose_next_spec",
            "rationale": "mixed cells deserve a narrower diagnostic sweep",
            "mechanism_read": "formation may help only in specific capacity regimes",
            "risk_flags": ["illustrative_until_calibrated"],
            "proposed_spec_json": json.dumps(next_spec),
        }

    monkeypatch.setattr(
        "playsim.agentic.call_openai_planner",
        fake_call_openai_planner,
    )

    decision = plan_next_experiment(
        spec=spec,
        evaluation=evaluation,
        planner="llm",
        planner_model="test-model",
    )

    assert decision["planner"] == "llm"
    assert decision["model"] == "test-model"
    assert decision["validated"] is True
    assert decision["proposed_spec"]["experiment"] == "llm_holdout"


def test_llm_planner_rejects_invalid_structured_specs(monkeypatch):
    spec = default_spec()
    invalid_spec = default_spec()
    invalid_spec["fixed"]["policies"] = ["standard", "fairplay"]

    def fake_call_openai_planner(*, spec, evaluation, model, api_key=None):
        return {
            "decision": "propose_next_spec",
            "rationale": "bad proposal",
            "mechanism_read": "bad proposal",
            "risk_flags": [],
            "proposed_spec_json": json.dumps(invalid_spec),
        }

    monkeypatch.setattr(
        "playsim.agentic.call_openai_planner",
        fake_call_openai_planner,
    )

    decision = plan_next_experiment(
        spec=spec,
        evaluation={"verdict": "needs_followup", "cells": []},
        planner="llm",
        planner_model="test-model",
    )

    assert decision["decision"] == "stop"
    assert decision["validated"] is False
    assert "standard vs fairplay_liveness" in decision["validation_error"]


def test_spec_rejects_llm_sweep_that_exceeds_run_budget():
    spec = default_spec()
    spec["autonomy_contract"]["max_sim_runs_per_experiment"] = 4

    try:
        run_agentic_loop(spec, out_dir=Path("/tmp/not-used"), max_iterations=0)
    except ValueError as exc:
        assert "max_sim_runs_per_experiment" in str(exc)
    else:
        raise AssertionError("expected over-budget spec to fail validation")


def test_spec_rejects_unsupported_behavior_value():
    spec = default_spec()
    spec["fixed"]["behavior"] = "baseline"

    try:
        run_agentic_loop(spec, out_dir=Path("/tmp/not-used"), max_iterations=0)
    except ValueError as exc:
        assert "unsupported behavior" in str(exc)
    else:
        raise AssertionError("expected unsupported behavior to fail validation")


def test_agentic_cli_writes_default_spec(tmp_path):
    out = tmp_path / "spec.json"

    rc = main(["agentic", "--write-default-spec", str(out)])

    assert rc == 0
    spec = load_spec(out)
    assert spec["fixed"]["policies"] == ["standard", "fairplay_liveness"]
    assert spec["sweep"]["tables"]


def test_agentic_loop_tiny_smoke(tmp_path):
    spec = default_spec()
    spec["fixed"].update({
        "horizon_min": 12,
        "seeds": [5],
        "samples": 1,
        "players": 80,
        "active_tables": 4,
        "start_fill_min": 2,
        "start_fill_max": 4,
    })
    spec["sweep"] = {"tables": [6], "arrival_rate_per_hour": [12]}
    spec["autonomy_contract"]["max_experiments"] = 1
    spec["autonomy_contract"]["escalate_if"] = {
        "estimated_avg_user_session_min": "> 1000"
    }

    ledger = run_agentic_loop(spec, out_dir=tmp_path / "agentic")

    assert ledger["completed_iterations"] == 1
    assert (tmp_path / "agentic" / "ledger.json").is_file()
    assert (tmp_path / "agentic" / "experiment-000-planner.json").is_file()
    report = (tmp_path / "agentic" / "experiment-000-report.md").read_text(
        encoding="utf-8"
    )
    assert "Playsim agentic experiment report" in report
    result = json.loads(
        (tmp_path / "agentic" / "experiment-000-results.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["meta"]["policies"] == ["standard", "fairplay_liveness"]
    assert result["meta"]["provenance"]["spec_sha256"]


def test_agentic_loop_caps_requested_iterations_to_contract(tmp_path):
    spec = default_spec()
    spec["fixed"].update({
        "horizon_min": 12,
        "seeds": [5],
        "samples": 1,
        "players": 80,
        "active_tables": 4,
        "start_fill_min": 2,
        "start_fill_max": 4,
    })
    spec["sweep"] = {"tables": [6], "arrival_rate_per_hour": [12]}
    spec["autonomy_contract"]["max_experiments"] = 1
    spec["autonomy_contract"]["escalate_if"] = {
        "estimated_avg_user_session_min": "> 1000"
    }

    ledger = run_agentic_loop(
        spec,
        out_dir=tmp_path / "agentic-capped",
        max_iterations=5,
    )

    assert ledger["requested_iterations"] == 5
    assert ledger["contract_max_experiments"] == 1
    assert ledger["effective_iterations"] == 1
    assert ledger["completed_iterations"] == 1


def test_agentic_loop_allows_zero_iteration_load_check(tmp_path):
    ledger = run_agentic_loop(
        default_spec(),
        out_dir=tmp_path / "agentic-load-check",
        max_iterations=0,
    )

    assert ledger["completed_iterations"] == 0
    assert (tmp_path / "agentic-load-check" / "ledger.json").is_file()
