"""Validate the classification champion (kickoff §8 acceptance).

Runs ``scoring.classify`` over ``data/players.json`` and checks:

1. **Acceptance (hard gate):** the kickoff §8 case players land on their pinned
   archetypes. Exit non-zero if any miss.
2. **Full-population accuracy:** champion vs the documented ID-range ground
   truth, with a per-archetype confusion breakdown — so the fuzzy behavioral
   tiers are visible and the ML challenger has a baseline to beat.

Run:  python scripts/validate_classify.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ — for `scoring`
from scoring.classify import classify  # noqa: E402

DATA = Path(__file__).resolve().parents[2] / "data" / "players.json"  # repo root

# Kickoff §8 acceptance — the case players that MUST classify correctly.
ACCEPTANCE = {
    "P-104": "new",
    "P-176": "aggressive_predatory",
    "P-177": "aggressive_predatory",
    "P-164": "grinder",
    "P-184": "promo_hunter",
    "P-221": "bot_like",
    "P-198": "cluster_member",
    "P-199": "cluster_member",
    "P-200": "cluster_member",
    "P-192": "shared_device_household",
    "P-193": "shared_device_household",
}


def ground_truth(pid: str) -> str:
    """Documented ID-range labels (players.json inference note / OvR notebook)."""
    n = int(pid.split("-")[1])
    if 100 <= n <= 107: return "new"
    if 108 <= n <= 141: return "recreational"
    if 142 <= n <= 163: return "regular"
    if 164 <= n <= 175: return "grinder"
    if 176 <= n <= 183: return "aggressive_predatory"
    if 184 <= n <= 191: return "promo_hunter"
    if 192 <= n <= 197: return "shared_device_household"
    if 198 <= n <= 202: return "cluster_member"
    if 203 <= n <= 220: return "healthy_anchor"
    return "bot_like"


def main() -> int:
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    players = raw["players"] if isinstance(raw, dict) else raw
    results = {p["player_id"]: classify(p) for p in players}

    # 1. Acceptance gate
    print("=== Kickoff §8 acceptance ===")
    failures = []
    for pid, expected in ACCEPTANCE.items():
        got = results[pid].archetype if pid in results else "<missing>"
        ok = got == expected
        if not ok:
            failures.append((pid, expected, got))
        print(f"  {'PASS' if ok else 'FAIL'}  {pid:6} expected {expected:24} got {got}")

    # 2. Full-population accuracy vs ID-range ground truth
    print("\n=== Full-population accuracy (vs documented ID-range truth) ===")
    correct = 0
    confusion: dict[str, Counter] = defaultdict(Counter)
    for pid, res in results.items():
        truth = ground_truth(pid)
        pred = res.archetype
        confusion[truth][pred] += 1
        if pred == truth:
            correct += 1
    total = len(results)
    print(f"  overall: {correct}/{total} = {correct / total:.1%}\n")
    print(f"  {'truth':24} {'n':>3} {'hit':>4}  misclassified-as")
    for truth in sorted(confusion):
        c = confusion[truth]
        n = sum(c.values())
        hit = c.get(truth, 0)
        misses = ", ".join(f"{k}×{v}" for k, v in c.items() if k != truth) or "—"
        print(f"  {truth:24} {n:>3} {hit:>4}  {misses}")

    if failures:
        print(f"\nFAILED {len(failures)} acceptance case(s).")
        return 1
    print("\nAll acceptance cases pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
