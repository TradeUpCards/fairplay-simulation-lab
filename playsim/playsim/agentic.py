"""Agentic experiment loop for playsim room-economics sweeps.

The goal is not to let an agent edit simulator code. The loop is intentionally
bounded: it reads an experiment spec, runs deterministic Standard vs
FairPlay-liveness sweeps, evaluates guardrails, writes a findings ledger, and
either proposes a next spec or stops on an escalation gate.
"""

from __future__ import annotations

import copy
import hashlib
import json
import operator
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .large_room_sweep import run_large_room_sweep


DEFAULT_SPEC: dict[str, Any] = {
    "experiment": "standard_vs_fairplay_liveness_static_capacity",
    "hypothesis": (
        "FairPlay-liveness can beat Standard on room-wide paid seat-hours "
        "when enough visible capacity exists for healthy table formation."
    ),
    "objective": {
        "primary": "total_paid_seat_hours_delta",
        "secondary": [
            "vulnerable_paid_seat_hours_delta",
            "demand_drop_rate_delta",
            "departure_rate_per_hour_delta",
            "terminal_churn_rate_per_hour_delta",
            "reseek_departure_rate_per_hour_delta",
            "estimated_avg_user_session_min",
        ],
    },
    "autonomy_contract": {
        "allowed_knob_families": [
            "room_demand",
            "behavior",
            "policy",
            "scoring_named_variants",
        ],
        "max_experiments": 1,
        "max_sim_runs_per_experiment": 96,
        "escalate_if": {
            "estimated_avg_user_session_min": "> 150",
            "demand_drop_rate_delta": "> 0.10",
            "terminal_churn_rate_per_hour_delta": "> 2.0",
        },
        "forbidden_claims": [
            "validated retention improvement without real room data",
            "canonical backend scoring changed by an exploratory sweep",
        ],
    },
    "fixed": {
        "fixture_seed": 42,
        "horizon_min": 480,
        "seeds": [42, 7, 99],
        "behavior": "formation-aware",
        "formation_mode": "forming",
        "samples": 1,
        "players": 1000,
        "active_tables": 35,
        "max_seats": 6,
        "start_fill_min": 4,
        "start_fill_max": 6,
        "policies": ["standard", "fairplay_liveness"],
    },
    "sweep": {
        "tables": [40, 50, 60, 70],
        "arrival_rate_per_hour": [10, 20, 30, 40],
    },
}


TOP_LEVEL_KEYS = {
    "experiment",
    "hypothesis",
    "objective",
    "autonomy_contract",
    "fixed",
    "sweep",
}
FIXED_KEYS = {
    "fixture_seed",
    "horizon_min",
    "seeds",
    "behavior",
    "formation_mode",
    "samples",
    "players",
    "tables",
    "active_tables",
    "max_seats",
    "start_fill_min",
    "start_fill_max",
    "policies",
    "regenerate_fixture",
}
SWEEP_KEYS = {"tables", "active_tables", "arrival_rate_per_hour"}
BEHAVIOR_VALUES = {"default", "fit-aware", "reason-aware", "formation-aware"}
FORMATION_MODE_VALUES = {"none", "forming"}
CELL_METRICS = {
    "total_paid_seat_hours_delta",
    "vulnerable_paid_seat_hours_delta",
    "demand_drop_rate_delta",
    "departure_rate_per_hour_delta",
    "terminal_churn_rate_per_hour_delta",
    "reseek_departure_rate_per_hour_delta",
    "formation_activation_delta",
    "estimated_avg_user_session_min",
}


@dataclass(frozen=True)
class ExperimentPaths:
    out_dir: Path
    spec_path: Path
    result_path: Path
    evaluation_path: Path
    report_path: Path
    planner_path: Path
    next_spec_path: Path


OPS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


def default_spec() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_SPEC)


def load_spec(path: Path) -> dict[str, Any]:
    """Load a JSON spec, with optional PyYAML support for yaml files."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "YAML specs require PyYAML. Use JSON specs or install PyYAML."
            ) from exc
        return yaml.safe_load(text)
    raise ValueError(f"unsupported experiment spec type: {path.suffix}")


def write_spec(spec: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def spec_sha256(spec: dict[str, Any]) -> str:
    payload = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _initial_seated_count(data_root: Path) -> int:
    roster_path = data_root / "table_roster.json"
    if not roster_path.exists():
        return 0
    doc = json.loads(roster_path.read_text(encoding="utf-8"))
    return sum(int(t.get("seated_count", 0)) for t in doc.get("tables", []))


def _mean(rows: Iterable[dict[str, Any]], key: str) -> float:
    vals = [float(row.get(key, 0.0)) for row in rows]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def _condition_met(value: float, expr: str) -> bool:
    expr = expr.strip()
    for op_text in (">=", "<=", "==", "!=", ">", "<"):
        if expr.startswith(op_text):
            rhs = float(expr[len(op_text):].strip())
            return bool(OPS[op_text](value, rhs))
    raise ValueError(f"unsupported condition expression: {expr!r}")


def validate_spec(spec: dict[str, Any]) -> None:
    """Fail fast when a spec asks the v1 loop to do unsupported work."""
    if not isinstance(spec, dict):
        raise ValueError("experiment spec must be a JSON object")
    unknown_top = sorted(set(spec) - TOP_LEVEL_KEYS)
    if unknown_top:
        raise ValueError(f"unsupported top-level spec keys: {unknown_top}")

    fixed = spec.get("fixed", {})
    sweep = spec.get("sweep", {})
    contract = spec.get("autonomy_contract", {})
    objective = spec.get("objective", {})
    if not isinstance(fixed, dict) or not isinstance(sweep, dict):
        raise ValueError("spec.fixed and spec.sweep must be objects")

    unknown_fixed = sorted(set(fixed) - FIXED_KEYS)
    unknown_sweep = sorted(set(sweep) - SWEEP_KEYS)
    if unknown_fixed:
        raise ValueError(f"unsupported fixed spec keys: {unknown_fixed}")
    if unknown_sweep:
        raise ValueError(f"unsupported sweep spec keys: {unknown_sweep}")

    policies = tuple(fixed.get("policies", ["standard", "fairplay_liveness"]))
    if policies != ("standard", "fairplay_liveness"):
        raise ValueError("agentic v1 is scoped to standard vs fairplay_liveness only")
    behavior = str(fixed.get("behavior", "formation-aware"))
    if behavior not in BEHAVIOR_VALUES:
        raise ValueError(
            f"unsupported behavior {behavior!r}; expected one of {sorted(BEHAVIOR_VALUES)}"
        )
    formation_mode = str(fixed.get("formation_mode", "forming"))
    if formation_mode not in FORMATION_MODE_VALUES:
        raise ValueError(
            "unsupported formation_mode "
            f"{formation_mode!r}; expected one of {sorted(FORMATION_MODE_VALUES)}"
        )

    tables = _as_list(sweep.get("tables") or fixed.get("tables"))
    rates = _as_list(sweep.get("arrival_rate_per_hour") or fixed.get("arrival_rate_per_hour"))
    if not tables or not rates:
        raise ValueError("spec requires sweep.tables and sweep.arrival_rate_per_hour")

    max_experiments = int(contract.get("max_experiments", 1))
    if max_experiments < 0:
        raise ValueError("autonomy_contract.max_experiments must be >= 0")
    max_sim_runs = int(contract.get("max_sim_runs_per_experiment", 0) or 0)
    if max_sim_runs < 0:
        raise ValueError("autonomy_contract.max_sim_runs_per_experiment must be >= 0")

    escalation_rules = contract.get("escalate_if", {})
    if not isinstance(escalation_rules, dict):
        raise ValueError("autonomy_contract.escalate_if must be an object")
    for metric, expr in escalation_rules.items():
        if metric not in CELL_METRICS:
            raise ValueError(f"unknown guardrail metric: {metric}")
        _condition_met(0.0, str(expr))

    metrics = [objective.get("primary"), *_as_list(objective.get("secondary"))]
    unknown_metrics = sorted(m for m in metrics if m and m not in CELL_METRICS)
    if unknown_metrics:
        raise ValueError(f"unknown objective metric(s): {unknown_metrics}")

    if max_sim_runs:
        active_tables = _as_list(sweep.get("active_tables") or fixed.get("active_tables", 35))
        seeds = _as_list(fixed.get("seeds", [42, 7, 99]))
        sim_runs = len(tables) * len(active_tables) * len(rates) * len(seeds) * len(policies)
        if sim_runs > max_sim_runs:
            raise ValueError(
                "spec exceeds autonomy_contract.max_sim_runs_per_experiment: "
                f"{sim_runs} > {max_sim_runs}"
            )


def _group_rows(rows: list[dict[str, Any]]) -> dict[tuple[int, int, float], list[dict[str, Any]]]:
    groups: dict[tuple[int, int, float], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            int(row["tables"]),
            int(row["active_tables"]),
            float(row["arrival_rate_per_hour"]),
        )
        groups.setdefault(key, []).append(row)
    return groups


def _fixture_slug(*, table_count: int, active_tables: int, fixed: dict[str, Any]) -> str:
    fixture_config = {
        "fixture_seed": int(fixed.get("fixture_seed", 42)),
        "players": int(fixed.get("players", 1000)),
        "tables": table_count,
        "active_tables": active_tables,
        "max_seats": int(fixed.get("max_seats", 6)),
        "start_fill_min": int(fixed.get("start_fill_min", 4)),
        "start_fill_max": int(fixed.get("start_fill_max", 6)),
    }
    short_hash = hashlib.sha256(
        json.dumps(fixture_config, sort_keys=True).encode("utf-8")
    ).hexdigest()[:10]
    return f"large-room-t{table_count}-a{active_tables}-{short_hash}"


def _summarize_agentic_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metric_keys = [
        "total_paid_seat_hours",
        "vulnerable_paid_seat_hours",
        "arrival_count",
        "arrival_seated_count",
        "demand_drop_rate",
        "departure_rate_per_hour",
        "terminal_churn_rate_per_hour",
        "reseek_departure_rate_per_hour",
        "break_count",
        "wait_balk_count",
        "forming_seat_count",
        "formation_activation_count",
        "final_active_tables",
        "estimated_avg_user_session_min",
    ]
    out: list[dict[str, Any]] = []
    for (tables, active_tables, rate), rows in sorted(_group_rows(runs).items()):
        by_policy: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_policy.setdefault(str(row["policy"]), []).append(row)
        for policy, policy_rows in sorted(by_policy.items()):
            item = {
                "tables": tables,
                "active_tables": active_tables,
                "arrival_rate_per_hour": rate,
                "policy": policy,
                "seeds": [r["seed"] for r in policy_rows],
            }
            item.update({
                f"{key}_mean": _mean(policy_rows, key)
                for key in metric_keys
            })
            out.append(item)
    return out


def run_experiment(spec: dict[str, Any], *, out_dir: Path) -> dict[str, Any]:
    """Run the deterministic sweeps described by an experiment spec."""
    validate_spec(spec)
    fixed = spec.get("fixed", {})
    sweep = spec.get("sweep", {})
    policies = tuple(fixed.get("policies", ["standard", "fairplay_liveness"]))

    runs: list[dict[str, Any]] = []
    tables_values = [int(t) for t in _as_list(sweep.get("tables") or fixed.get("tables"))]
    active_tables_values = [
        int(t)
        for t in _as_list(sweep.get("active_tables") or fixed.get("active_tables", 35))
    ]
    rate_values = [
        float(r)
        for r in _as_list(sweep.get("arrival_rate_per_hour") or fixed.get("arrival_rate_per_hour"))
    ]

    fixture_seed = int(fixed.get("fixture_seed", 42))
    seeds = [int(s) for s in fixed.get("seeds", [42, 7, 99])]
    horizon_min = float(fixed.get("horizon_min", 480))
    samples = int(fixed.get("samples", 1))
    players = int(fixed.get("players", 1000))
    max_seats = int(fixed.get("max_seats", 6))
    start_fill_min = int(fixed.get("start_fill_min", 4))
    start_fill_max = int(fixed.get("start_fill_max", 6))

    for table_count in tables_values:
        for active_tables in active_tables_values:
            if active_tables > table_count:
                raise ValueError(
                    f"active_tables ({active_tables}) cannot exceed tables ({table_count})"
                )
            data_root = out_dir / "fixtures" / _fixture_slug(
                table_count=table_count,
                active_tables=active_tables,
                fixed=fixed,
            )
            payload = run_large_room_sweep(
                data_root=data_root,
                fixture_seed=fixture_seed,
                seeds=seeds,
                arrival_rates_per_hour=rate_values,
                horizon_min=horizon_min,
                equity_samples=samples,
                policies=policies,
                behavior=str(fixed.get("behavior", "formation-aware")),
                formation_mode=str(fixed.get("formation_mode", "forming")),
                players=players,
                tables=table_count,
                active_tables=active_tables,
                max_seats=max_seats,
                start_fill_min=start_fill_min,
                start_fill_max=start_fill_max,
                regenerate_fixture=bool(fixed.get("regenerate_fixture", False)),
            )
            initial_seated = _initial_seated_count(data_root)
            for row in payload["runs"]:
                users = initial_seated + int(row.get("arrival_seated_count", 0))
                avg_min = (
                    float(row["total_paid_seat_hours"]) * 60.0 / users
                    if users else 0.0
                )
                runs.append({
                    **row,
                    "tables": table_count,
                    "active_tables": active_tables,
                    "initial_seated_count": initial_seated,
                    "estimated_avg_user_session_min": round(avg_min, 3),
                })

    return {
        "meta": {
            "agentic": True,
            "experiment": spec.get("experiment"),
            "hypothesis": spec.get("hypothesis"),
            "deterministic": True,
            "provenance": {
                "git_commit": _git_commit(),
                "spec_sha256": spec_sha256(spec),
            },
            "policies": list(policies),
            "fixed": fixed,
            "sweep": sweep,
            "note": (
                "Agentic outputs are exploratory. They are reproducible playsim "
                "experiments, not validated product claims."
            ),
        },
        "runs": runs,
        "summary": _summarize_agentic_runs(runs),
    }


def evaluate_experiment(payload: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Evaluate FairPlay-liveness vs Standard by cell and guardrail."""
    validate_spec(spec)
    summary = payload.get("summary", [])
    cells: list[dict[str, Any]] = []
    guardrail_hits: list[dict[str, Any]] = []
    escalation_rules = (
        spec.get("autonomy_contract", {})
        .get("escalate_if", {})
    )

    grouped: dict[tuple[int, int, float], dict[str, dict[str, Any]]] = {}
    for row in summary:
        key = (
            int(row["tables"]),
            int(row["active_tables"]),
            float(row["arrival_rate_per_hour"]),
        )
        grouped.setdefault(key, {})[str(row["policy"])] = row

    for (tables, active_tables, rate), by_policy in sorted(grouped.items()):
        standard = by_policy.get("standard")
        fairplay = by_policy.get("fairplay_liveness")
        if not standard or not fairplay:
            missing = sorted({"standard", "fairplay_liveness"} - set(by_policy))
            raise ValueError(
                "missing required policy summary row(s) for "
                f"tables={tables}, active_tables={active_tables}, "
                f"arrival_rate_per_hour={rate}: {missing}"
            )
        cell = {
            "tables": tables,
            "active_tables": active_tables,
            "arrival_rate_per_hour": rate,
            "total_paid_seat_hours_delta": round(
                fairplay["total_paid_seat_hours_mean"]
                - standard["total_paid_seat_hours_mean"],
                4,
            ),
            "vulnerable_paid_seat_hours_delta": round(
                fairplay["vulnerable_paid_seat_hours_mean"]
                - standard["vulnerable_paid_seat_hours_mean"],
                4,
            ),
            "demand_drop_rate_delta": round(
                fairplay["demand_drop_rate_mean"]
                - standard["demand_drop_rate_mean"],
                4,
            ),
            "departure_rate_per_hour_delta": round(
                fairplay["departure_rate_per_hour_mean"]
                - standard["departure_rate_per_hour_mean"],
                4,
            ),
            "terminal_churn_rate_per_hour_delta": round(
                fairplay["terminal_churn_rate_per_hour_mean"]
                - standard["terminal_churn_rate_per_hour_mean"],
                4,
            ),
            "reseek_departure_rate_per_hour_delta": round(
                fairplay["reseek_departure_rate_per_hour_mean"]
                - standard["reseek_departure_rate_per_hour_mean"],
                4,
            ),
            "formation_activation_delta": round(
                fairplay["formation_activation_count_mean"]
                - standard["formation_activation_count_mean"],
                4,
            ),
            "estimated_avg_user_session_min": round(
                fairplay["estimated_avg_user_session_min_mean"],
                4,
            ),
        }
        cell["fairplay_wins_total_seat_hours"] = (
            cell["total_paid_seat_hours_delta"] > 0
        )
        cells.append(cell)

        for metric, expr in escalation_rules.items():
            if metric not in cell:
                raise ValueError(f"unknown guardrail metric: {metric}")
            value = float(cell[metric])
            if _condition_met(value, str(expr)):
                guardrail_hits.append({
                    "metric": metric,
                    "condition": expr,
                    "value": value,
                    "tables": tables,
                    "active_tables": active_tables,
                    "arrival_rate_per_hour": rate,
                })

    win_count = sum(1 for c in cells if c["fairplay_wins_total_seat_hours"])
    mean_delta = _mean(cells, "total_paid_seat_hours_delta")
    mean_vulnerable_delta = _mean(cells, "vulnerable_paid_seat_hours_delta")

    if guardrail_hits:
        verdict = "escalate"
        reason = "one or more autonomy-contract guardrails fired"
    elif cells and win_count == len(cells):
        verdict = "accept_for_holdout"
        reason = "FairPlay-liveness won total paid seat-hours in every explored cell"
    elif cells and win_count > 0:
        verdict = "needs_followup"
        reason = "FairPlay-liveness wins some cells, so mechanism or regime matters"
    else:
        verdict = "reject_or_rethink"
        reason = "FairPlay-liveness did not beat Standard on total paid seat-hours"

    return {
        "verdict": verdict,
        "reason": reason,
        "cell_count": len(cells),
        "fairplay_total_seat_hour_win_count": win_count,
        "mean_total_paid_seat_hours_delta": mean_delta,
        "mean_vulnerable_paid_seat_hours_delta": mean_vulnerable_delta,
        "guardrail_hits": guardrail_hits,
        "cells": cells,
        "next_recommendation": recommend_next(verdict, cells, guardrail_hits),
    }


def recommend_next(
    verdict: str,
    cells: list[dict[str, Any]],
    guardrail_hits: list[dict[str, Any]],
) -> str:
    if guardrail_hits:
        metrics = sorted({hit["metric"] for hit in guardrail_hits})
        if "estimated_avg_user_session_min" in metrics:
            return (
                "Stop and implement/session-sweep user session distribution. "
                "The current room-day average user session is too long to trust "
                "seat-hour economics as a behavioral claim."
            )
        if "terminal_churn_rate_per_hour_delta" in metrics:
            return (
                "Stop and inspect non-reseat simulator exits before continuing. "
                "A seat-hour win that increases terminal exits may be a behavior "
                "model problem, not a routing improvement."
            )
        return (
            "Stop and inspect guardrail metrics before allowing the orchestrator "
            "to continue."
        )
    if verdict == "accept_for_holdout":
        return (
            "Run holdout seeds and a matched-saturation sweep to confirm the win "
            "does not depend only on spare visible capacity."
        )
    if verdict == "needs_followup":
        return (
            "Run a narrower mechanism sweep around the winning and losing cells, "
            "then inspect formation activations, wait balks, and demand drop."
        )
    return (
        "Prioritize model diagnosis before more policy sweeps: scoring fragility, "
        "session-duration assumptions, and churn/breakage weights."
    )


LLM_PLANNER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "decision",
        "rationale",
        "mechanism_read",
        "risk_flags",
        "proposed_spec_json",
    ],
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["stop", "propose_next_spec"],
        },
        "rationale": {
            "type": "string",
            "description": "Short teammate-facing reason for the next move.",
        },
        "mechanism_read": {
            "type": "string",
            "description": "What the result suggests mechanistically.",
        },
        "risk_flags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "proposed_spec_json": {
            "type": "string",
            "description": (
                "A complete next experiment spec as JSON when decision is "
                "propose_next_spec, or an empty string when decision is stop."
            ),
        },
    },
}


def _planner_context(
    *,
    spec: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    cells = evaluation.get("cells", [])
    worst_drop = max(cells, key=lambda c: c.get("demand_drop_rate_delta", 0.0), default=None)
    best_total = max(cells, key=lambda c: c.get("total_paid_seat_hours_delta", 0.0), default=None)
    worst_terminal = max(
        cells,
        key=lambda c: c.get("terminal_churn_rate_per_hour_delta", 0.0),
        default=None,
    )
    return {
        "current_spec": spec,
        "evaluation_summary": {
            "verdict": evaluation.get("verdict"),
            "reason": evaluation.get("reason"),
            "cell_count": evaluation.get("cell_count"),
            "fairplay_total_seat_hour_win_count": evaluation.get(
                "fairplay_total_seat_hour_win_count"
            ),
            "mean_total_paid_seat_hours_delta": evaluation.get(
                "mean_total_paid_seat_hours_delta"
            ),
            "mean_vulnerable_paid_seat_hours_delta": evaluation.get(
                "mean_vulnerable_paid_seat_hours_delta"
            ),
            "guardrail_hits": evaluation.get("guardrail_hits", []),
            "next_recommendation": evaluation.get("next_recommendation"),
        },
        "notable_cells": {
            "best_total_paid_seat_hours_delta": best_total,
            "worst_demand_drop_delta": worst_drop,
            "worst_non_reseat_exit_delta": worst_terminal,
        },
        "allowed_spec_shape": {
            "top_level_keys": sorted(TOP_LEVEL_KEYS),
            "fixed_keys": sorted(FIXED_KEYS),
            "sweep_keys": sorted(SWEEP_KEYS),
            "cell_metrics": sorted(CELL_METRICS),
            "policies": ["standard", "fairplay_liveness"],
            "behavior_values": sorted(BEHAVIOR_VALUES),
            "formation_mode_values": sorted(FORMATION_MODE_VALUES),
        },
        "runtime_budget": {
            "max_experiments": spec.get("autonomy_contract", {}).get("max_experiments", 1),
            "max_sim_runs_per_experiment": spec.get(
                "autonomy_contract", {}
            ).get("max_sim_runs_per_experiment", 0),
        },
        "hard_rules": [
            "Do not claim validated retention or product churn without real room data.",
            "Do not propose code edits.",
            "Do not change canonical backend scoring.",
            "Only propose complete experiment specs that validate with the existing schema.",
            "Use only the listed behavior_values and formation_mode_values.",
            "Keep proposed specs within max_sim_runs_per_experiment.",
            "For demos, prefer one narrow diagnostic change over a large sweep.",
            "Stop on escalation unless the next spec directly diagnoses the guardrail.",
        ],
    }


def _extract_response_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    chunks: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


def call_openai_planner(
    *,
    spec: dict[str, Any],
    evaluation: dict[str, Any],
    model: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Ask an LLM for the next experiment spec, then return raw structured JSON."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "LLM planner requires OPENAI_API_KEY. Use --planner rule for offline runs."
        )
    context = _planner_context(spec=spec, evaluation=evaluation)
    body = {
        "model": model,
        "store": False,
        "reasoning": {"effort": "medium"},
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": "playsim_experiment_planner_decision",
                "strict": True,
                "schema": LLM_PLANNER_SCHEMA,
            },
        },
        "input": [
            {
                "role": "system",
                "content": (
                    "You are the bounded experiment planner for FairPlay playsim. "
                    "You propose the next simulation spec only when it helps diagnose "
                    "the current result. You never edit code, never change canonical "
                    "scoring, and never make validated business claims."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(context, sort_keys=True),
            },
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            response = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI planner request failed: {exc.code} {detail}") from exc
    text = _extract_response_text(response)
    if not text:
        raise RuntimeError("OpenAI planner returned no output_text")
    return json.loads(text)


def _rule_planner_decision(
    spec: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    next_spec = propose_next_spec(spec, evaluation)
    return {
        "planner": "rule",
        "decision": "propose_next_spec" if next_spec else "stop",
        "rationale": evaluation.get("next_recommendation", ""),
        "mechanism_read": evaluation.get("reason", ""),
        "risk_flags": [
            hit["metric"] for hit in evaluation.get("guardrail_hits", [])
        ],
        "proposed_spec": next_spec,
        "validated": next_spec is not None,
        "model": None,
    }


def plan_next_experiment(
    *,
    spec: dict[str, Any],
    evaluation: dict[str, Any],
    planner: str = "rule",
    planner_model: str = "gpt-5.5",
) -> dict[str, Any]:
    """Return a planner decision whose proposed spec is either valid or removed."""
    if planner == "rule":
        return _rule_planner_decision(spec, evaluation)
    if planner != "llm":
        raise ValueError("planner must be 'rule' or 'llm'")

    raw = call_openai_planner(
        spec=spec,
        evaluation=evaluation,
        model=planner_model,
    )
    decision = {
        "planner": "llm",
        "model": planner_model,
        "decision": raw.get("decision", "stop"),
        "rationale": raw.get("rationale", ""),
        "mechanism_read": raw.get("mechanism_read", ""),
        "risk_flags": raw.get("risk_flags", []),
        "proposed_spec_json": raw.get("proposed_spec_json", ""),
        "proposed_spec": None,
        "validated": False,
    }
    if decision["decision"] != "propose_next_spec":
        decision["proposed_spec_json"] = ""
        return decision
    proposed_text = str(decision.get("proposed_spec_json") or "").strip()
    if not proposed_text:
        decision["decision"] = "stop"
        decision["risk_flags"] = [
            *decision["risk_flags"],
            "llm proposed continuation without proposed_spec_json",
        ]
        return decision
    try:
        proposed = json.loads(proposed_text)
        validate_spec(proposed)
    except (json.JSONDecodeError, ValueError) as exc:
        decision["decision"] = "stop"
        decision["risk_flags"] = [
            *decision["risk_flags"],
            f"llm proposed invalid spec: {exc}",
        ]
        decision["validation_error"] = str(exc)
        decision["proposed_spec"] = None
        return decision
    decision["proposed_spec"] = proposed
    decision["validated"] = True
    return decision


def propose_next_spec(
    spec: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any] | None:
    """Create the next runnable spec when no escalation gate has fired."""
    if evaluation["verdict"] != "accept_for_holdout":
        return None
    next_spec = copy.deepcopy(spec)
    next_spec["experiment"] = f"{spec.get('experiment', 'experiment')}_holdout"
    next_spec["hypothesis"] = (
        "Holdout seeds confirm whether the prior Standard vs FairPlay-liveness "
        "finding survives unseen deterministic arrival streams."
    )
    fixed = next_spec.setdefault("fixed", {})
    current = [int(s) for s in fixed.get("seeds", [42, 7, 99])]
    fixed["seeds"] = [s + 1000 for s in current]
    next_spec.setdefault("autonomy_contract", {})["max_experiments"] = 1
    return next_spec


def render_evaluation_markdown(
    *,
    spec: dict[str, Any],
    evaluation: dict[str, Any],
    result_path: Path,
) -> str:
    lines = [
        "# Playsim agentic experiment report",
        "",
        f"Experiment: `{spec.get('experiment')}`",
        "",
        f"Hypothesis: {spec.get('hypothesis')}",
        "",
        f"Verdict: **{evaluation['verdict']}**",
        "",
        f"Reason: {evaluation['reason']}",
        "",
        f"Raw result: `{result_path}`",
        "",
        "## Provenance",
        "",
        f"- Git commit: `{_git_commit() or 'unknown'}`",
        f"- Spec SHA-256: `{spec_sha256(spec)}`",
        f"- Fixture seed: `{spec.get('fixed', {}).get('fixture_seed', 'unknown')}`",
        f"- Simulation seeds: `{spec.get('fixed', {}).get('seeds', [])}`",
        f"- Fixed config: `{json.dumps(spec.get('fixed', {}), sort_keys=True)}`",
        f"- Sweep config: `{json.dumps(spec.get('sweep', {}), sort_keys=True)}`",
        "",
        "## Summary",
        "",
        f"- Cells evaluated: {evaluation['cell_count']}",
        f"- FairPlay-liveness total seat-hour wins: "
        f"{evaluation['fairplay_total_seat_hour_win_count']}",
        f"- Mean total paid seat-hour delta: "
        f"{evaluation['mean_total_paid_seat_hours_delta']:.3f}",
        f"- Mean vulnerable paid seat-hour delta: "
        f"{evaluation['mean_vulnerable_paid_seat_hours_delta']:.3f}",
        "",
        "## Cell Results",
        "",
        "| tables | active | arrival/hr | total hrs delta | vulnerable hrs delta | demand drop delta | departures/hr delta | non-reseat exits/hr delta | re-seat departures/hr delta | avg user min |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in evaluation["cells"]:
        lines.append(
            f"| {cell['tables']} | {cell['active_tables']} | "
            f"{cell['arrival_rate_per_hour']:.1f} | "
            f"{cell['total_paid_seat_hours_delta']:.3f} | "
            f"{cell['vulnerable_paid_seat_hours_delta']:.3f} | "
            f"{cell['demand_drop_rate_delta']:.3f} | "
            f"{cell['departure_rate_per_hour_delta']:.3f} | "
            f"{cell['terminal_churn_rate_per_hour_delta']:.3f} | "
            f"{cell['reseek_departure_rate_per_hour_delta']:.3f} | "
            f"{cell['estimated_avg_user_session_min']:.1f} |"
        )
    lines.extend(["", "## Guardrails", ""])
    if evaluation["guardrail_hits"]:
        for hit in evaluation["guardrail_hits"]:
            lines.append(
                f"- `{hit['metric']}` {hit['condition']} fired at "
                f"tables={hit['tables']}, active={hit['active_tables']}, "
                f"arrival/hr={hit['arrival_rate_per_hour']}: "
                f"value={hit['value']:.3f}"
            )
    else:
        lines.append("- No escalation guardrails fired.")
    lines.extend([
        "",
        "## Next Recommendation",
        "",
        evaluation["next_recommendation"],
        "",
    ])
    return "\n".join(lines)


def _paths(out_dir: Path, iteration: int) -> ExperimentPaths:
    stem = f"experiment-{iteration:03d}"
    return ExperimentPaths(
        out_dir=out_dir,
        spec_path=out_dir / f"{stem}-spec.json",
        result_path=out_dir / f"{stem}-results.json",
        evaluation_path=out_dir / f"{stem}-evaluation.json",
        report_path=out_dir / f"{stem}-report.md",
        planner_path=out_dir / f"{stem}-planner.json",
        next_spec_path=out_dir / f"{stem}-next-spec.json",
    )


def run_agentic_loop(
    spec: dict[str, Any],
    *,
    out_dir: Path,
    max_iterations: int | None = None,
    planner: str = "rule",
    planner_model: str = "gpt-5.5",
) -> dict[str, Any]:
    """Run the bounded autonomous experiment loop."""
    out_dir.mkdir(parents=True, exist_ok=True)
    validate_spec(spec)
    contract = spec.get("autonomy_contract", {})
    contract_budget = int(contract.get("max_experiments", 1))
    requested_budget = contract_budget if max_iterations is None else int(max_iterations)
    if requested_budget < 0:
        raise ValueError("max_iterations must be >= 0")
    budget = min(requested_budget, contract_budget)
    current_spec = copy.deepcopy(spec)
    ledger: list[dict[str, Any]] = []

    for iteration in range(budget):
        paths = _paths(out_dir, iteration)
        write_spec(current_spec, paths.spec_path)
        payload = run_experiment(current_spec, out_dir=out_dir)
        paths.result_path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        evaluation = evaluate_experiment(payload, current_spec)
        paths.evaluation_path.write_text(
            json.dumps(evaluation, indent=2) + "\n",
            encoding="utf-8",
        )
        paths.report_path.write_text(
            render_evaluation_markdown(
                spec=current_spec,
                evaluation=evaluation,
                result_path=paths.result_path,
            ),
            encoding="utf-8",
        )
        planner_decision = plan_next_experiment(
            spec=current_spec,
            evaluation=evaluation,
            planner=planner,
            planner_model=planner_model,
        )
        write_json(planner_decision, paths.planner_path)
        next_spec = planner_decision.get("proposed_spec")
        if next_spec is not None:
            write_spec(next_spec, paths.next_spec_path)
        ledger.append({
            "iteration": iteration,
            "spec": str(paths.spec_path),
            "results": str(paths.result_path),
            "evaluation": str(paths.evaluation_path),
            "report": str(paths.report_path),
            "planner": str(paths.planner_path),
            "next_spec": str(paths.next_spec_path) if next_spec else None,
            "verdict": evaluation["verdict"],
            "planner_kind": planner_decision["planner"],
            "planner_decision": planner_decision["decision"],
            "spec_sha256": spec_sha256(current_spec),
        })
        if next_spec is None:
            break
        current_spec = next_spec

    ledger_doc = {
        "agentic_loop": True,
        "planner": planner,
        "planner_model": planner_model if planner == "llm" else None,
        "git_commit": _git_commit(),
        "requested_iterations": requested_budget,
        "contract_max_experiments": contract_budget,
        "effective_iterations": budget,
        "completed_iterations": len(ledger),
        "ledger": ledger,
    }
    (out_dir / "ledger.json").write_text(
        json.dumps(ledger_doc, indent=2) + "\n",
        encoding="utf-8",
    )
    return ledger_doc
