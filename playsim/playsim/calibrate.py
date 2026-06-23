"""The calibration loop — tune ``postflop_aggression`` until realized AF ≈ target.

Per the archetype spec (step 9), this closes play ↔ stats: run agents over many
seeded hands at realistic 6-max tables, measure each archetype's realized
aggression factor across all its appearances, and nudge its ``postflop_aggression``
knob toward the empirical target. A damped proportional controller converges in a
handful of rounds. Result is written to ``calibration.json``, which ``knobs.py``
overlays on the hand-authored defaults.

    python -m playsim.cli calibrate --rounds 6 --hands 500
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from . import knobs as K
from .runner import Player, run_session

# 6-max calibration field — every archetype appears at the table size the engine
# is actually used at (so AF calibrates under realistic multiway dilution). The
# hard one (predator, AF 4.3) appears twice for volume.
_CAL_TABLES: list[list[Player]] = [
    [Player(1, "new"), Player(2, "recreational"), Player(3, "regular"),
     Player(4, "grinder"), Player(5, "aggressive_predatory"), Player(6, "healthy_anchor")],
    [Player(7, "promo_hunter"), Player(8, "cluster_member", "C1"),
     Player(9, "cluster_member", "C1"), Player(10, "bot_like"),
     Player(11, "solver_like"), Player(12, "regular")],
    [Player(13, "recreational"), Player(14, "aggressive_predatory"),
     Player(15, "grinder"), Player(16, "healthy_anchor"),
     Player(17, "shared_device_household"), Player(18, "new")],
]


def _per_archetype_af(results) -> dict[str, float]:
    """Aggregate postflop (bets+raises)/calls per archetype across all hands."""
    bets: dict[str, int] = defaultdict(int)
    calls: dict[str, int] = defaultdict(int)
    for res in results:
        arch_of = {p.player_id: p.archetype for p in res.roster}
        for h in res.hands:
            for a in h.actions:
                if a.street > 0:
                    arch = arch_of[a.player_id]
                    if a.is_raise:
                        bets[arch] += 1
                    elif a.is_call:
                        calls[arch] += 1
    archs = set(bets) | set(calls)
    return {
        a: (bets[a] / calls[a]) if calls[a] else float(bets[a]) for a in archs
    }


def run_calibration(
    rounds: int = 6,
    hands: int = 500,
    seed: int = 1234,
    samples: int = 18,
    damp: float = 0.6,
    tol: float = 0.12,
    write: bool = True,
    verbose: bool = True,
) -> dict[str, float]:
    """Iteratively tune postflop_aggression; returns the converged overrides."""
    # ``applied`` = the knobs we run this round; the coupled multi-table system
    # can oscillate, so we keep the BEST round seen, not the last.
    applied = {a: K.ARCHETYPES[a].postflop_aggression for a in K.ARCHETYPES}
    best, best_afs, best_err = dict(applied), {}, float("inf")
    for r in range(rounds):
        for a, v in applied.items():
            K.ARCHETYPES[a] = replace(K.ARCHETYPES[a], postflop_aggression=v)
        results = [
            run_session(roster, hands, seed=seed + i, equity_samples=samples)
            for i, roster in enumerate(_CAL_TABLES)
        ]
        afs = _per_archetype_af(results)
        worst = 0.0
        for a in applied:
            tgt = K.ARCHETYPES[a].targets.get("aggression_factor")
            real = afs.get(a)
            if tgt and real and real > 0:
                worst = max(worst, abs(real - tgt) / tgt)
        if worst < best_err:
            best_err, best, best_afs = worst, dict(applied), dict(afs)
        if verbose:
            print(f"  round {r + 1}: worst AF error {worst * 100:4.1f}%"
                  f"  (best {best_err * 100:4.1f}%)")
        if worst < tol:
            break
        # proportional step toward target for the next round
        for a in applied:
            tgt = K.ARCHETYPES[a].targets.get("aggression_factor")
            real = afs.get(a)
            if tgt and real and real > 0:
                applied[a] = min(0.995, max(0.05, applied[a] * (tgt / real) ** damp))

    overrides, afs = best, best_afs
    # re-apply the best so the in-process module reflects what we write
    for a, v in overrides.items():
        K.ARCHETYPES[a] = replace(K.ARCHETYPES[a], postflop_aggression=v)

    if write:
        path = Path(__file__).with_name("calibration.json")
        payload = {
            "_note": "Tuned postflop_aggression per archetype (playsim.calibrate). "
                     "Overlaid on knobs.py defaults at import.",
            "rounds": rounds, "hands": hands, "seed": seed,
            "postflop_aggression": {a: round(v, 4) for a, v in overrides.items()},
            "realized_af": {a: round(afs.get(a, 0.0), 3) for a in overrides},
            "target_af": {a: K.ARCHETYPES[a].targets.get("aggression_factor")
                          for a in overrides},
        }
        path.write_text(json.dumps(payload, indent=2))
        if verbose:
            print(f"  wrote {path}")
    return overrides


def calibration_report() -> list[dict]:
    """Realized vs target AF from the last calibration.json (for the CLI)."""
    path = Path(__file__).with_name("calibration.json")
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    rows = []
    for a, real in data.get("realized_af", {}).items():
        rows.append({
            "archetype": a, "realized_af": real,
            "target_af": data.get("target_af", {}).get(a),
            "postflop_aggression": data.get("postflop_aggression", {}).get(a),
        })
    return rows
