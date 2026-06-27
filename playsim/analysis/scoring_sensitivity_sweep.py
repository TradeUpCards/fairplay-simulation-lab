"""Experimental scoring sensitivity sweep for playsim large-room economics.

This is intentionally a playsim analysis harness, not a backend scoring change.
Each variant patches scorer constants in-process, runs deterministic room
simulations, then restores the canonical constants before the next variant.

Usage from ``playsim/``:

    .venv/bin/python analysis/scoring_sensitivity_sweep.py --quick
    .venv/bin/python analysis/scoring_sensitivity_sweep.py \
      --variants baseline,frag_soft,short_fit_neutral,loose_liveness \
      --seeds 42,7,99 --arrival-rates 20,40 --horizon 480

Outputs default to ``out/scoring-sensitivity-sweep.{json,md}`` and
``out/scoring-sensitivity-explorer.html``.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import json
import statistics as st
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from playsim.arrivals import build_arrival_intents
from playsim.behavior import make_behavior
from playsim.large_room_sweep import ensure_large_room_fixture, _metrics
from playsim.policies import FairPlayLivenessPolicy, FairPlayRoutePolicy, StandardPolicy
from playsim.room import RoomSim
from playsim.router_adapter import RouterAdapter, _ensure_backend_on_path


@dataclass(frozen=True)
class ScoringVariant:
    """One explicit sensitivity hypothesis."""

    variant_id: str
    label: str
    thesis: str
    router_weights: tuple[float, float, float] | None = None
    frag_w_occ: float | None = None
    forming_frag_discount: float | None = None
    short_active_frag_discount: float | None = None
    short_table_pref: dict[str, float] = field(default_factory=dict)
    dealable_health_floor: float = 80.0
    forming_health_floor: float = 70.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "label": self.label,
            "thesis": self.thesis,
            "router_weights": self.router_weights,
            "frag_w_occ": self.frag_w_occ,
            "forming_frag_discount": self.forming_frag_discount,
            "short_active_frag_discount": self.short_active_frag_discount,
            "short_table_pref": self.short_table_pref,
            "dealable_health_floor": self.dealable_health_floor,
            "forming_health_floor": self.forming_health_floor,
        }


VARIANTS: dict[str, ScoringVariant] = {
    "baseline": ScoringVariant(
        "baseline",
        "Current liveness scoring",
        "Current opt-in liveness-aware scorer and FairPlay-liveness thresholds.",
    ),
    "router_liveness_heavy": ScoringVariant(
        "router_liveness_heavy",
        "Router weights: health-heavy",
        "Test whether FairPlay needs more table-health/liveness weight in rank.",
        router_weights=(0.20, 0.55, 0.25),
    ),
    "router_fit_heavy": ScoringVariant(
        "router_fit_heavy",
        "Router weights: fit-heavy",
        "Test whether additional fit emphasis helps vulnerable retention or scatters liquidity.",
        router_weights=(0.45, 0.35, 0.20),
    ),
    "frag_soft": ScoringVariant(
        "frag_soft",
        "Fragility: softer occupancy penalty",
        "Reduce thin-table fragility pressure without removing it.",
        frag_w_occ=10.0,
    ),
    "frag_zero": ScoringVariant(
        "frag_zero",
        "Fragility: no occupancy penalty",
        "Extreme bound: health ignores occupancy fragility except trend and other terms.",
        frag_w_occ=0.0,
    ),
    "forming_partial_frag": ScoringVariant(
        "forming_partial_frag",
        "Forming tables pay half fragility",
        "Replace the binary forming-table fragility exemption with a partial discount.",
        forming_frag_discount=0.50,
    ),
    "short_active_grace": ScoringVariant(
        "short_active_grace",
        "Short active tables get fragility grace",
        "Do not punish 2-player active tables as harshly when liveness-aware scoring is on.",
        short_active_frag_discount=0.50,
    ),
    "short_fit_neutral": ScoringVariant(
        "short_fit_neutral",
        "Short-table fit: vulnerable neutral",
        "Remove the liveness-aware short-table fit penalty for new/recreational players.",
        short_table_pref={
            "new": 0.0,
            "recreational": 0.0,
            "promo_hunter": 0.0,
            "grinder": 6.0,
            "aggressive_predatory": 7.0,
            "solver_like": 5.0,
        },
    ),
    "loose_liveness": ScoringVariant(
        "loose_liveness",
        "FairPlay-liveness: lower health floors",
        "Let liveness-aware policy seed/grow forming tables at lower predicted health.",
        dealable_health_floor=70.0,
        forming_health_floor=60.0,
    ),
}


DEFAULT_VARIANTS = (
    "baseline",
    "router_liveness_heavy",
    "frag_soft",
    "short_active_grace",
    "short_fit_neutral",
    "loose_liveness",
)


def _mean(rows: Iterable[dict], key: str) -> float:
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    return round(st.mean(vals), 3) if vals else 0.0


def _tradeoff(vuln_delta: float, total_delta: float) -> dict[str, Any]:
    total_loss = -total_delta
    eps = 0.0001
    if vuln_delta > eps and total_loss > eps:
        return {
            "status": "tradeoff",
            "ratio": round(vuln_delta / total_loss, 4),
            "vulnerable_delta": round(vuln_delta, 4),
            "total_delta": round(total_delta, 4),
            "total_loss": round(total_loss, 4),
        }
    if vuln_delta > eps and total_loss <= eps:
        status = "clean_win"
    elif vuln_delta <= eps and total_loss > eps:
        status = "no_vulnerable_gain"
    else:
        status = "no_cost"
    return {
        "status": status,
        "ratio": None,
        "vulnerable_delta": round(vuln_delta, 4),
        "total_delta": round(total_delta, 4),
        "total_loss": round(max(0.0, total_loss), 4),
    }


def _ensure_scoring_modules(data_root: Path):
    _ensure_backend_on_path(data_root)
    import scoring.health as health
    import scoring.router as router
    import scoring.seating as seating

    return health, seating, router


def _discounted_frag_func(health_module, variant: ScoringVariant):
    def p_frag(
        seated: int,
        max_seats: int,
        trend: str,
        *,
        table_mode: str = "active",
        target_seats: int | None = None,
        liveness_aware: bool = False,
    ):
        denominator = target_seats if (liveness_aware and target_seats) else max_seats
        occ = min(1.0, seated / denominator) if denominator else 1.0
        trend_pen = health_module.FRAG_TREND_PEN.get(
            trend, health_module.FRAG_TREND_PEN["stable"]
        )
        base = max(
            0.0,
            min(health_module.FRAG_MAX, health_module.FRAG_W_OCC * (1 - occ) + trend_pen),
        )
        discount = 0.0
        formation_exempt = False
        if liveness_aware and table_mode == "forming":
            if variant.forming_frag_discount is None:
                discount = 1.0
                formation_exempt = True
            else:
                discount = variant.forming_frag_discount
        elif (
            liveness_aware
            and variant.short_active_frag_discount is not None
            and table_mode != "forming"
            and seated <= 2
        ):
            discount = variant.short_active_frag_discount
        val = max(0.0, min(health_module.FRAG_MAX, base * (1.0 - discount)))
        sig = {
            "occupancy": round(occ, 3),
            "trend": trend,
            "trend_penalty": trend_pen,
        }
        if liveness_aware:
            sig.update({
                "table_mode": table_mode,
                "target_seats": denominator,
                "frag_discount": round(discount, 3),
            })
        if formation_exempt:
            sig["formation_exempt"] = True
        return val, sig

    return p_frag


@contextlib.contextmanager
def scoring_variant_scope(data_root: Path, variant: ScoringVariant):
    """Apply one scoring variant, then restore all module constants/functions."""

    health, seating, router = _ensure_scoring_modules(data_root)
    saved = {
        "health_FRAG_W_OCC": health.FRAG_W_OCC,
        "health_p_frag": health.p_frag,
        "seating_p_frag": seating.p_frag,
        "seating_SHORT_TABLE_PREF": dict(seating.SHORT_TABLE_PREF),
        "seating_weights": (seating.W_FIT, seating.W_HEALTH, seating.W_DELTA),
        "router_weights": (router.W_FIT, router.W_HEALTH, router.W_DELTA),
    }
    try:
        if variant.frag_w_occ is not None:
            health.FRAG_W_OCC = variant.frag_w_occ
        if (
            variant.forming_frag_discount is not None
            or variant.short_active_frag_discount is not None
        ):
            patched = _discounted_frag_func(health, variant)
            health.p_frag = patched
            seating.p_frag = patched
        if variant.short_table_pref:
            seating.SHORT_TABLE_PREF.update(variant.short_table_pref)
        if variant.router_weights is not None:
            wf, wh, wd = variant.router_weights
            seating.W_FIT = router.W_FIT = wf
            seating.W_HEALTH = router.W_HEALTH = wh
            seating.W_DELTA = router.W_DELTA = wd
        yield
    finally:
        health.FRAG_W_OCC = saved["health_FRAG_W_OCC"]
        health.p_frag = saved["health_p_frag"]
        seating.p_frag = saved["seating_p_frag"]
        seating.SHORT_TABLE_PREF.clear()
        seating.SHORT_TABLE_PREF.update(saved["seating_SHORT_TABLE_PREF"])
        seating.W_FIT, seating.W_HEALTH, seating.W_DELTA = saved["seating_weights"]
        router.W_FIT, router.W_HEALTH, router.W_DELTA = saved["router_weights"]


def _policy_factory(name: str, adapter: RouterAdapter, live_adapter: RouterAdapter,
                    variant: ScoringVariant):
    if name == "standard":
        return StandardPolicy()
    if name == "fairplay":
        return FairPlayRoutePolicy(adapter)
    if name in {"fairplay_liveness", "fairplay-live"}:
        return FairPlayLivenessPolicy(
            live_adapter,
            dealable_health_floor=variant.dealable_health_floor,
            forming_health_floor=variant.forming_health_floor,
        )
    raise ValueError(f"unknown policy {name!r}")


def summarize_runs(runs: list[dict]) -> list[dict]:
    groups: dict[tuple[str, float, str], list[dict]] = {}
    for row in runs:
        groups.setdefault(
            (row["variant_id"], row["arrival_rate_per_hour"], row["policy"]),
            [],
        ).append(row)
    metric_keys = [
        "total_paid_seat_hours",
        "vulnerable_paid_seat_hours",
        "arrival_count",
        "arrival_seated_count",
        "arrival_balk_count",
        "break_count",
        "break_balk_count",
        "wait_balk_count",
        "no_good_existing_seat_count",
        "forming_seat_count",
        "formation_activation_count",
        "table_reactivation_count",
        "final_active_tables",
        "final_forming_tables",
        "final_empty_tables",
        "hands_total",
    ]
    out = []
    for (variant_id, rate, policy), rows in sorted(groups.items()):
        item = {
            "variant_id": variant_id,
            "arrival_rate_per_hour": rate,
            "policy": policy,
            "seeds": [r["seed"] for r in rows],
        }
        item.update({f"{key}_mean": _mean(rows, key) for key in metric_keys})
        out.append(item)
    return out


def compare_vs_standard(runs: list[dict]) -> list[dict]:
    by_cell: dict[tuple[str, float, int], dict[str, dict]] = {}
    for row in runs:
        by_cell.setdefault(
            (row["variant_id"], row["arrival_rate_per_hour"], row["seed"]), {}
        )[row["policy"]] = row

    rows = []
    for (variant_id, rate, seed), policies in sorted(by_cell.items()):
        std = policies.get("standard")
        if not std:
            continue
        for policy, cand in sorted(policies.items()):
            if policy == "standard":
                continue
            total_delta = cand["total_paid_seat_hours"] - std["total_paid_seat_hours"]
            vuln_delta = cand["vulnerable_paid_seat_hours"] - std["vulnerable_paid_seat_hours"]
            rows.append({
                "variant_id": variant_id,
                "arrival_rate_per_hour": rate,
                "seed": seed,
                "policy": policy,
                "total_delta": round(total_delta, 4),
                "vulnerable_delta": round(vuln_delta, 4),
                "no_good_existing_seat_delta": round(
                    cand["no_good_existing_seat_count"] - std["no_good_existing_seat_count"], 4
                ),
                "forming_seat_delta": round(cand["forming_seat_count"] - std["forming_seat_count"], 4),
                "formation_activation_delta": round(
                    cand["formation_activation_count"] - std["formation_activation_count"], 4
                ),
                "final_active_tables_delta": round(
                    cand["final_active_tables"] - std["final_active_tables"], 4
                ),
                **{f"tradeoff_{k}": v for k, v in _tradeoff(vuln_delta, total_delta).items()},
            })
    return rows


def summarize_comparisons(comparisons: list[dict]) -> list[dict]:
    groups: dict[tuple[str, float, str], list[dict]] = {}
    for row in comparisons:
        groups.setdefault(
            (row["variant_id"], row["arrival_rate_per_hour"], row["policy"]), []
        ).append(row)
    out = []
    for (variant_id, rate, policy), rows in sorted(groups.items()):
        total_delta = _mean(rows, "total_delta")
        vuln_delta = _mean(rows, "vulnerable_delta")
        trade = _tradeoff(vuln_delta, total_delta)
        out.append({
            "variant_id": variant_id,
            "arrival_rate_per_hour": rate,
            "policy": policy,
            "seed_count": len(rows),
            "total_delta_mean": total_delta,
            "total_wins": sum(1 for r in rows if r["total_delta"] > 0),
            "vulnerable_delta_mean": vuln_delta,
            "vulnerable_wins": sum(1 for r in rows if r["vulnerable_delta"] > 0),
            "no_good_existing_seat_delta_mean": _mean(rows, "no_good_existing_seat_delta"),
            "forming_seat_delta_mean": _mean(rows, "forming_seat_delta"),
            "formation_activation_delta_mean": _mean(rows, "formation_activation_delta"),
            "final_active_tables_delta_mean": _mean(rows, "final_active_tables_delta"),
            "tradeoff": trade,
        })
    return out


def run_scoring_sensitivity_sweep(
    *,
    data_root: Path,
    fixture_seed: int = 42,
    variants: list[str] | None = None,
    seeds: list[int] | None = None,
    arrival_rates_per_hour: list[float] | None = None,
    horizon_min: float = 480.0,
    equity_samples: int = 1,
    policies: tuple[str, ...] = ("standard", "fairplay", "fairplay_liveness"),
    behavior: str = "formation-aware",
    formation_mode: str = "forming",
    players: int = 1000,
    tables: int = 50,
    active_tables: int = 35,
    max_seats: int = 6,
    start_fill_min: int = 4,
    start_fill_max: int = 6,
    regenerate_fixture: bool = False,
    progress: bool = False,
) -> dict[str, Any]:
    seeds = seeds or [42, 7, 99]
    arrival_rates_per_hour = arrival_rates_per_hour or [20.0, 40.0]
    variant_ids = variants or list(DEFAULT_VARIANTS)
    unknown = [v for v in variant_ids if v not in VARIANTS]
    if unknown:
        raise ValueError(f"unknown scoring variants: {', '.join(unknown)}")

    ensure_large_room_fixture(
        data_root,
        seed=fixture_seed,
        players=players,
        tables=tables,
        active_tables=active_tables,
        max_seats=max_seats,
        start_fill_min=start_fill_min,
        start_fill_max=start_fill_max,
        regenerate=regenerate_fixture,
    )

    runs: list[dict] = []
    standard_cache: dict[tuple[float, int], dict[str, Any]] = {}
    if "standard" in policies:
        if progress:
            print("  precomputing Standard once per seed/rate", flush=True)
        for rate in arrival_rates_per_hour:
            for seed in seeds:
                intents = build_arrival_intents(
                    horizon_min,
                    seed=seed,
                    root=data_root,
                    mode="continuous",
                    arrival_rate_per_hour=rate,
                )
                result = RoomSim(
                    StandardPolicy(),
                    root=data_root,
                    master_seed=seed,
                    horizon_min=horizon_min,
                    equity_samples=equity_samples,
                    arrival_intents=intents,
                    arrival_mode="continuous",
                    arrival_rate_per_hour=rate,
                    formation_mode=formation_mode,
                    behavior=make_behavior(behavior, seed=seed),
                ).run()
                standard_cache[(float(rate), seed)] = _metrics(result, intents)

    candidate_policies = tuple(p for p in policies if p != "standard")
    for variant_id in variant_ids:
        variant = VARIANTS[variant_id]
        if progress:
            print(f"  variant {variant_id}", flush=True)
        with scoring_variant_scope(data_root, variant):
            adapter = RouterAdapter(data_root)
            live_adapter = RouterAdapter(data_root, liveness_aware=True)
            for rate in arrival_rates_per_hour:
                for seed in seeds:
                    if "standard" in policies:
                        runs.append({
                            "variant_id": variant_id,
                            "seed": seed,
                            "arrival_rate_per_hour": float(rate),
                            "policy": "standard",
                            **standard_cache[(float(rate), seed)],
                        })
                    intents = build_arrival_intents(
                        horizon_min,
                        seed=seed,
                        root=data_root,
                        mode="continuous",
                        arrival_rate_per_hour=rate,
                    )
                    for policy_name in candidate_policies:
                        if progress:
                            print(
                                f"    rate={float(rate):g}/hr seed={seed} policy={policy_name}",
                                flush=True,
                            )
                        policy = _policy_factory(policy_name, adapter, live_adapter, variant)
                        result = RoomSim(
                            policy,
                            root=data_root,
                            master_seed=seed,
                            horizon_min=horizon_min,
                            equity_samples=equity_samples,
                            arrival_intents=intents,
                            arrival_mode="continuous",
                            arrival_rate_per_hour=rate,
                            formation_mode=formation_mode,
                            behavior=make_behavior(behavior, seed=seed),
                        ).run()
                        runs.append({
                            "variant_id": variant_id,
                            "seed": seed,
                            "arrival_rate_per_hour": float(rate),
                            "policy": policy_name,
                            **_metrics(result, intents),
                        })

    comparisons = compare_vs_standard(runs)
    return {
        "meta": {
            "kind": "scoring-sensitivity-sweep",
            "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fixture": "playsim-large-room",
            "data_root": str(data_root),
            "fixture_seed": fixture_seed,
            "players": players,
            "tables": tables,
            "active_tables": active_tables,
            "horizon_min": horizon_min,
            "equity_samples": equity_samples,
            "arrival_mode": "continuous",
            "arrival_rates_per_hour": arrival_rates_per_hour,
            "formation_mode": formation_mode,
            "behavior": behavior,
            "policies": list(policies),
            "deterministic": True,
            "illustrative": True,
            "note": (
                "Experimental playsim-only scorer patches. Canonical backend "
                "scoring constants are restored after each variant."
            ),
        },
        "variants": [VARIANTS[v].as_dict() for v in variant_ids],
        "runs": runs,
        "summary": summarize_runs(runs),
        "comparisons": comparisons,
        "comparison_summary": summarize_comparisons(comparisons),
    }


def render_markdown_report(payload: dict[str, Any]) -> str:
    meta = payload["meta"]
    variants = {v["variant_id"]: v for v in payload["variants"]}
    lines = [
        "# Playsim scoring sensitivity sweep",
        "",
        (
            f"Generated {meta['generated_at']} with {meta['tables']} tables, "
            f"{meta['active_tables']} active at start, rates "
            f"{', '.join(str(r) for r in meta['arrival_rates_per_hour'])}/hr, "
            f"horizon {meta['horizon_min']} min."
        ),
        "",
        "> Experimental synthetic outputs. These runs patch scorer constants in-process "
        "for analysis only; they are not validated retention claims and do not change "
        "canonical backend scoring.",
        "",
        "## Variant theses",
        "",
    ]
    for v in payload["variants"]:
        lines.append(f"- **{v['variant_id']}**: {v['thesis']}")
    lines.extend([
        "",
        "## FairPlay-liveness vs Standard",
        "",
        "| variant | rate/hr | total Δ hrs | vuln Δ hrs | tradeoff | vuln wins | total wins | forming seats Δ | final active Δ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    rows = [
        r for r in payload["comparison_summary"]
        if r["policy"] == "fairplay_liveness"
    ]
    for r in rows:
        tr = r["tradeoff"]
        ratio = f"{tr['ratio']:.2f}x" if tr["ratio"] is not None else tr["status"]
        n = r["seed_count"]
        label = variants[r["variant_id"]]["label"]
        lines.append(
            f"| {label} | {r['arrival_rate_per_hour']:.1f} | "
            f"{r['total_delta_mean']:+.2f} | {r['vulnerable_delta_mean']:+.2f} | "
            f"{ratio} | {r['vulnerable_wins']}/{n} | {r['total_wins']}/{n} | "
            f"{r['forming_seat_delta_mean']:+.1f} | {r['final_active_tables_delta_mean']:+.1f} |"
        )
    lines.extend([
        "",
        "## Interpretation rule",
        "",
        "Prefer mechanism-first reads: a useful variant should improve vulnerable "
        "seat-hours with an explainable movement in liveness/formation metrics, "
        "not merely hide a total-throughput loss behind a cohort win.",
        "",
    ])
    return "\n".join(lines)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Playsim · Scoring Sensitivity Explorer</title>
<style>
:root{--bg:#f6f8fb;--ink:#18212f;--muted:#66758a;--faint:#94a1b4;--card:#fff;--line:#e2e8f0;--pos:#1f9d83;--neg:#d4495f;--accent:#4f46e5;--dark:#0f1726;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--sans:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:14px;line-height:1.45}.wrap{max-width:1320px;margin:0 auto;padding:0 28px 80px}
header{background:var(--dark);color:#e9edf4;border-bottom:1px solid #1d2740}.head{padding:18px 28px}.brand{font-weight:700;font-size:18px}.brand span{color:#aeb8ca;font-weight:500}.pill{display:inline-flex;margin-left:14px;border:1px solid rgba(212,73,95,.3);background:rgba(212,73,95,.16);color:#ffb3bf;border-radius:999px;padding:3px 9px;font-size:11.5px;font-weight:650}.cfg{display:flex;gap:8px 20px;flex-wrap:wrap;margin-top:12px;color:#9aa5b8;font-family:var(--mono);font-size:12px}.cfg b{color:#dfe6f1}
.story{display:grid;grid-template-columns:1.5fr repeat(4,1fr);gap:14px;margin:22px 0}.tile,.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:0 1px 2px rgba(20,30,50,.04),0 4px 16px rgba(20,30,50,.06)}.tile{padding:14px 16px}.tile .k{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);font-weight:700}.tile .v{font-size:25px;font-weight:800;margin-top:4px}.tile .note{font-size:12.5px;color:var(--muted)}.tile.lede .v{font-size:15px;line-height:1.4;font-weight:650}
.toolbar{position:sticky;top:0;z-index:10;background:var(--bg);display:flex;gap:16px;align-items:end;flex-wrap:wrap;border-bottom:1px solid var(--line);padding:14px 0}.field{display:flex;flex-direction:column;gap:4px}.field label{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--faint);font-weight:700}.field select{background:#fff;border:1px solid #d4dae3;border-radius:8px;padding:7px 10px;font:inherit;min-width:170px}.seg{display:inline-flex;background:#fff;border:1px solid var(--line);border-radius:9px;padding:3px}.seg button{border:0;background:transparent;padding:6px 14px;border-radius:7px;color:var(--muted);font:inherit;font-weight:650;cursor:pointer}.seg button.on{background:var(--accent);color:#fff}
.panel{padding:22px;margin-top:18px}.panel h2{font-size:16px;margin:0 0 3px}.desc{color:var(--muted);margin:0 0 16px}.legend{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px;color:var(--muted);font-size:12px}.bar{width:180px;height:12px;border-radius:4px;border:1px solid var(--line);background:linear-gradient(90deg,var(--neg),#eef1f5,var(--pos))}
.hm{display:grid;gap:6px}.hdr,.rowhdr{display:flex;align-items:center;justify-content:center;color:var(--muted);font-weight:700;font-size:12px}.rowhdr{justify-content:flex-end;padding-right:10px}.cell{border:1px solid rgba(0,0,0,.05);border-radius:9px;min-height:78px;padding:10px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer}.cell:hover{box-shadow:0 8px 32px rgba(20,30,50,.14);transform:translateY(-1px)}.big{font-size:22px;font-weight:850;font-variant-numeric:tabular-nums}.sub{font-size:11.5px;margin-top:4px;font-weight:650}.dots{display:flex;gap:3px;margin-top:6px}.dots i{width:7px;height:7px;border-radius:50%}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}tbody tr:hover{background:#fbfcfe}.pos{color:var(--pos);font-weight:750}.neg{color:var(--neg);font-weight:750}.mono{font-family:var(--mono)}
footer{color:var(--faint);font-size:12px;line-height:1.6;margin-top:30px}@media(max-width:1080px){.story{grid-template-columns:1fr 1fr}.wrap{padding-left:18px;padding-right:18px}}
</style>
</head>
<body>
<header><div class="wrap head"><div><span class="brand">Playsim <span>· Scoring Sensitivity Explorer</span></span><span class="pill">Experimental synthetic data — not a validated retention claim</span></div><div class="cfg" id="cfg"></div></div></header>
<div class="wrap">
  <div class="story" id="story"></div>
  <div class="toolbar"><div class="seg" id="viewSeg"><button data-v="heatmap" class="on">Heatmap</button><button data-v="table">Data table</button></div><div class="field"><label>Policy</label><select id="policy"></select></div><div class="field"><label>Metric</label><select id="metric"></select></div></div>
  <div id="main"></div>
  <footer>Each cell compares a candidate policy against Standard under the same seeded, policy-independent arrival stream. Tradeoff ratio = vulnerable paid seat-hours gained per total paid seat-hour lost. Scoring variants patch constants only inside this analysis run; canonical backend scoring is not changed.</footer>
</div>
<script>
const DATA=__DATA__;
const POS="#1f9d83",NEG="#d4495f",NEU="#eef1f5";
const S={view:"heatmap",policy:"fairplay_liveness",metric:"total_delta_mean"};
const metricDefs={
 total_delta_mean:["Total seat-hrs Δ","hrs",false],
 vulnerable_delta_mean:["Vulnerable seat-hrs Δ","hrs",false],
 tradeoff_ratio:["Tradeoff ratio","ratio",false],
 no_good_existing_seat_delta_mean:["No-good-seat Δ","n",true],
 forming_seat_delta_mean:["Forming seats Δ","n",false],
 formation_activation_delta_mean:["Formation activations Δ","n",false],
 final_active_tables_delta_mean:["Final active tables Δ","n",false],
};
const variants=Object.fromEntries(DATA.variants.map(v=>[v.variant_id,v]));
const policies=[...new Set(DATA.comparison_summary.map(r=>r.policy))];
const rates=[...new Set(DATA.comparison_summary.map(r=>r.arrival_rate_per_hour))].sort((a,b)=>a-b);
const variantIds=DATA.variants.map(v=>v.variant_id);
function rows(){return DATA.comparison_summary.filter(r=>r.policy===S.policy)}
function rowOf(v,r){return rows().find(x=>x.variant_id===v&&x.arrival_rate_per_hour===r)}
function valOf(r){
 if(!r)return null;
 if(S.metric==="tradeoff_ratio")return r.tradeoff.ratio;
 return r[S.metric];
}
function goodOf(r){
 const v=valOf(r); if(v===null||v===undefined)return null;
 const lower=metricDefs[S.metric][2];
 return lower?-v:v;
}
function fmt(v,kind){
 if(v===null||v===undefined||Number.isNaN(v))return "—";
 if(kind==="ratio")return v.toFixed(2)+"x";
 if(kind==="hrs")return (v>=0?"+":"")+v.toFixed(1);
 return (v>=0?"+":"")+v.toFixed(1);
}
function mix(a,b,t){const A=[parseInt(a.slice(1,3),16),parseInt(a.slice(3,5),16),parseInt(a.slice(5,7),16)],B=[parseInt(b.slice(1,3),16),parseInt(b.slice(3,5),16),parseInt(b.slice(5,7),16)];return`rgb(${A.map((x,i)=>Math.round(x+(B[i]-x)*t)).join(",")})`}
function color(g,maxAbs){if(g===null)return"#f5f7fa";const t=Math.max(-1,Math.min(1,g/maxAbs));return t>=0?mix(NEU,POS,t):mix(NEU,NEG,-t)}
function renderCfg(){const m=DATA.meta;document.getElementById("cfg").innerHTML=[["fixture",m.fixture],["tables",m.tables],["active",m.active_tables],["players",m.players],["horizon",m.horizon_min+" min"],["rates",m.arrival_rates_per_hour.join("/")+"/hr"],["seeds",[...new Set(DATA.runs.map(r=>r.seed))].join("/")],["built",m.generated_at]].map(([k,v])=>`<span>${k} <b>${v}</b></span>`).join("")}
function renderStory(){
 const rs=rows();
 const vulnWins=rs.filter(r=>r.vulnerable_delta_mean>0).length, totalWins=rs.filter(r=>r.total_delta_mean>0).length;
 const trade=rs.filter(r=>r.tradeoff.ratio!==null);
 const aggGain=trade.reduce((a,r)=>a+r.tradeoff.vulnerable_delta,0), aggLoss=trade.reduce((a,r)=>a+r.tradeoff.total_loss,0);
 const ratio=aggLoss>0?aggGain/aggLoss:null;
 const best=[...rs].sort((a,b)=>(b.tradeoff.ratio??-99)-(a.tradeoff.ratio??-99))[0];
 document.getElementById("story").innerHTML=`<div class="tile lede"><div class="k">Sensitivity read</div><div class="v">${best?variants[best.variant_id].label:"No variant"} has the strongest tradeoff ratio for ${labelPolicy(S.policy)}. Treat as hypothesis, not proof.</div></div><div class="tile"><div class="k">Variants</div><div class="v">${DATA.variants.length}</div><div class="note">${rates.length} arrival rates · ${policies.length} candidate policies</div></div><div class="tile"><div class="k">Vulnerable wins</div><div class="v">${vulnWins}<small>/${rs.length}</small></div><div class="note">positive mean Δ vs Standard</div></div><div class="tile"><div class="k">Throughput wins</div><div class="v">${totalWins}<small>/${rs.length}</small></div><div class="note">positive mean total seat-hrs Δ</div></div><div class="tile"><div class="k">Aggregate tradeoff</div><div class="v">${ratio===null?"—":ratio.toFixed(2)+"x"}</div><div class="note">vuln hrs gained per total hr lost</div></div>`;
}
function labelPolicy(p){return p==="fairplay_liveness"?"FairPlay-liveness":p==="fairplay"?"FairPlay":p}
function renderControls(){document.getElementById("policy").innerHTML=policies.map(p=>`<option value="${p}" ${p===S.policy?"selected":""}>${labelPolicy(p)}</option>`).join("");document.getElementById("metric").innerHTML=Object.entries(metricDefs).map(([k,d])=>`<option value="${k}" ${k===S.metric?"selected":""}>${d[0]}</option>`).join("")}
function heatmap(){
 const kind=metricDefs[S.metric][1], vals=rows().map(goodOf).filter(v=>v!==null), maxAbs=Math.max(1e-9,...vals.map(Math.abs));
 let html=`<div class="panel"><h2>Variant heatmap</h2><p class="desc">Rows are scoring variants; columns are arrival rates. Color is oriented so green is better for the candidate policy.</p><div class="legend"><span>${metricDefs[S.metric][0]}</span><span>-${maxAbs.toFixed(1)}</span><span class="bar"></span><span>+${maxAbs.toFixed(1)}</span></div><div class="hm" style="grid-template-columns:220px repeat(${rates.length},1fr)"><div></div>`;
 rates.forEach(r=>html+=`<div class="hdr">${r}/hr</div>`);
 variantIds.forEach(v=>{html+=`<div class="rowhdr">${variants[v].label}</div>`;rates.forEach(rate=>{const r=rowOf(v,rate),raw=valOf(r),g=goodOf(r),strong=g!==null&&Math.abs(g)/maxAbs>.55;html+=`<div class="cell" style="background:${color(g,maxAbs)};color:${strong?"#fff":"var(--ink)"}" title="${variants[v].thesis}"><div class="big">${fmt(raw,kind)}</div><div class="sub">${r?`${r.vulnerable_wins}/${r.seed_count} vuln wins · ${r.total_wins}/${r.seed_count} total`:""}</div><div class="dots">${r?Array.from({length:r.seed_count},(_,i)=>`<i style="background:${i<r.vulnerable_wins?POS:NEG}"></i>`).join(""):""}</div></div>`})});
 return html+`</div></div>`;
}
function table(){
 const rs=rows();
 let body=rs.map(r=>`<tr><td>${variants[r.variant_id].label}</td><td>${r.arrival_rate_per_hour}/hr</td><td class="${r.total_delta_mean>=0?"pos":"neg"}">${fmt(r.total_delta_mean,"hrs")}</td><td class="${r.vulnerable_delta_mean>=0?"pos":"neg"}">${fmt(r.vulnerable_delta_mean,"hrs")}</td><td>${r.tradeoff.ratio===null?r.tradeoff.status:r.tradeoff.ratio.toFixed(2)+"x"}</td><td>${r.vulnerable_wins}/${r.seed_count}</td><td>${r.total_wins}/${r.seed_count}</td><td>${fmt(r.no_good_existing_seat_delta_mean,"n")}</td><td>${fmt(r.forming_seat_delta_mean,"n")}</td><td>${fmt(r.final_active_tables_delta_mean,"n")}</td></tr>`).join("");
 return `<div class="panel"><h2>Comparison table · ${labelPolicy(S.policy)} vs Standard</h2><p class="desc">Mean deltas across seeds for every variant/rate cell.</p><div style="overflow:auto"><table><thead><tr><th>Variant</th><th>Rate</th><th>Total Δ</th><th>Vulnerable Δ</th><th>Tradeoff</th><th>Vuln wins</th><th>Total wins</th><th>No-good-seat Δ</th><th>Forming Δ</th><th>Final active Δ</th></tr></thead><tbody>${body}</tbody></table></div></div>`;
}
function renderMain(){document.getElementById("main").innerHTML=S.view==="heatmap"?heatmap():table()}
function render(){renderCfg();renderControls();renderStory();renderMain()}
document.getElementById("policy").onchange=e=>{S.policy=e.target.value;renderStory();renderMain()};
document.getElementById("metric").onchange=e=>{S.metric=e.target.value;renderMain()};
document.querySelectorAll("#viewSeg button").forEach(b=>b.onclick=()=>{S.view=b.dataset.v;document.querySelectorAll("#viewSeg button").forEach(x=>x.classList.toggle("on",x===b));renderMain()});
render();
</script>
</body>
</html>
"""


def write_outputs(payload: dict[str, Any], *, json_path: Path | None,
                  markdown_path: Path | None, html_path: Path | None) -> None:
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if markdown_path:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown_report(payload), encoding="utf-8")
    if html_path:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
        html_path.write_text(html, encoding="utf-8")


def _parse_csv_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_csv_floats(raw: str) -> list[float]:
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", help="existing/generated data root; defaults to --fixture-out")
    ap.add_argument("--fixture-out", default="out/scoring-sensitivity-data")
    ap.add_argument("--regenerate-fixture", action="store_true")
    ap.add_argument("--fixture-seed", type=int, default=42)
    ap.add_argument("--variants", default=",".join(DEFAULT_VARIANTS),
                    help=f"comma-separated variants. Known: {', '.join(VARIANTS)}")
    ap.add_argument("--seeds", default="42,7,99")
    ap.add_argument("--arrival-rates", default="20,40")
    ap.add_argument("--horizon", type=float, default=480.0)
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument("--policies", default="standard,fairplay,fairplay_liveness")
    ap.add_argument("--behavior", choices=["default", "fit-aware", "reason-aware", "formation-aware"],
                    default="formation-aware")
    ap.add_argument("--formation-mode", choices=["none", "forming"], default="forming")
    ap.add_argument("--players", type=int, default=1000)
    ap.add_argument("--tables", type=int, default=50)
    ap.add_argument("--active-tables", type=int, default=35)
    ap.add_argument("--max-seats", type=int, default=6)
    ap.add_argument("--start-fill-min", type=int, default=4)
    ap.add_argument("--start-fill-max", type=int, default=6)
    ap.add_argument("--out-json", default="out/scoring-sensitivity-sweep.json")
    ap.add_argument("--out-md", default="out/scoring-sensitivity-sweep.md")
    ap.add_argument("--out-html", default="out/scoring-sensitivity-explorer.html")
    ap.add_argument("--quick", action="store_true",
                    help="small deterministic smoke sweep for development")
    args = ap.parse_args(argv)

    if args.quick:
        args.variants = "baseline,frag_soft,short_fit_neutral,loose_liveness"
        args.seeds = "42"
        args.arrival_rates = "30"
        args.horizon = 90.0
        args.players = 220
        args.tables = 16
        args.active_tables = 10
        args.regenerate_fixture = True

    data_root = Path(args.data_root or args.fixture_out)
    payload = run_scoring_sensitivity_sweep(
        data_root=data_root,
        fixture_seed=args.fixture_seed,
        variants=[v.strip() for v in args.variants.split(",") if v.strip()],
        seeds=_parse_csv_ints(args.seeds),
        arrival_rates_per_hour=_parse_csv_floats(args.arrival_rates),
        horizon_min=args.horizon,
        equity_samples=args.samples,
        policies=tuple(p.strip() for p in args.policies.split(",") if p.strip()),
        behavior=args.behavior,
        formation_mode=args.formation_mode,
        players=args.players,
        tables=args.tables,
        active_tables=args.active_tables,
        max_seats=args.max_seats,
        start_fill_min=args.start_fill_min,
        start_fill_max=args.start_fill_max,
        regenerate_fixture=args.regenerate_fixture,
        progress=True,
    )
    write_outputs(
        payload,
        json_path=Path(args.out_json) if args.out_json else None,
        markdown_path=Path(args.out_md) if args.out_md else None,
        html_path=Path(args.out_html) if args.out_html else None,
    )

    print(
        f"\n  scoring sensitivity sweep   variants={len(payload['variants'])} "
        f"runs={len(payload['runs'])} comparisons={len(payload['comparisons'])}\n"
    )
    for row in payload["comparison_summary"]:
        if row["policy"] != "fairplay_liveness":
            continue
        tr = row["tradeoff"]
        ratio = f"{tr['ratio']:.2f}x" if tr["ratio"] is not None else tr["status"]
        print(
            f"  {row['variant_id']:24} rate={row['arrival_rate_per_hour']:>5.1f}/hr "
            f"total={row['total_delta_mean']:>+8.2f} "
            f"vuln={row['vulnerable_delta_mean']:>+7.2f} tradeoff={ratio}"
        )
    if args.out_json:
        print(f"\n  wrote {args.out_json}")
    if args.out_md:
        print(f"  wrote {args.out_md}")
    if args.out_html:
        print(f"  wrote {args.out_html}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
