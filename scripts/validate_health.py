"""Validate the table-health score (kickoff §2 ③–⑥ acceptance).

* Health(T-22) == 38  -> band beginner_unfriendly  (the hard calibration anchor)
* T-8  healthy        (band in healthy/fragile, clearly above T-22)
* T-11 elevated P_clus AND flagged integrity_candidate (CL-001 seated)
* T-14 good fit       (healthy/fragile, above T-22)
* Every term within its documented range; Health in [0,100].

Run:  python scripts/validate_health.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.integrity import score_integrity  # noqa: E402
from scoring.health import (  # noqa: E402
    build_cluster_band_index, score_all_tables,
    PRED_MAX, FRAG_MAX, CLUS_MAX, BLEED_MAX,
)


def main() -> int:
    rel = json.loads((ROOT / "data" / "relationships.json").read_text(encoding="utf-8"))
    praw = json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8"))
    players = praw["players"] if isinstance(praw, dict) else praw
    by = {p["player_id"]: p for p in players}
    roster = json.loads((ROOT / "data" / "table_roster.json").read_text(encoding="utf-8"))["tables"]
    sessions = [s for s in json.loads((ROOT / "data" / "sessions.json").read_text(encoding="utf-8"))["sessions"]
                if "session_id" in s]

    integ = score_integrity(rel, players)
    cbi = build_cluster_band_index(rel, integ)
    scores = {h.table_id: h for h in score_all_tables(roster, by, cbi, sessions=sessions)}

    failures = []

    print("=== All tables (health, band, terms) ===")
    print(f"  {'table':6} {'health':>6} {'band':20} "
          f"{'P_pred':>6} {'P_frag':>6} {'P_clus':>6} {'P_bleed':>7}  intg?")
    for tid, h in scores.items():
        t = h.terms
        print(f"  {tid:6} {h.health:6.1f} {h.band:20} "
              f"{t['P_pred']:6.1f} {t['P_frag']:6.1f} {t['P_clus']:6.1f} {t['P_bleed']:7.1f}  "
              f"{'YES' if h.integrity_candidate else ''}")

    print("\n=== Acceptance ===")

    def check(name, ok):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failures.append(name)

    t22 = scores["T-22"]
    check(f"Health(T-22) == 38 (got {t22.health:.1f})", round(t22.health) == 38)
    check(f"T-22 band == beginner_unfriendly (got {t22.band})",
          t22.band == "beginner_unfriendly")

    t8 = scores["T-8"]
    check(f"T-8 healthier than T-22 (got {t8.health:.1f} > {t22.health:.1f})",
          t8.health > t22.health)
    check(f"T-8 band healthy/fragile (got {t8.band})", t8.band in ("healthy", "fragile"))

    t11 = scores["T-11"]
    check(f"T-11 P_clus elevated (got {t11.terms['P_clus']:.1f} > 0)",
          t11.terms["P_clus"] > 0)
    check("T-11 flagged integrity_candidate (CL-001 seated)", t11.integrity_candidate)

    t14 = scores["T-14"]
    check(f"T-14 good fit, above T-22 (got {t14.health:.1f})", t14.health > t22.health)

    # Range + invariants for every table.
    rng_ok = True
    for tid, h in scores.items():
        t = h.terms
        if not (0 <= t["P_pred"] <= PRED_MAX and 0 <= t["P_frag"] <= FRAG_MAX
                and 0 <= t["P_clus"] <= CLUS_MAX and 0 <= t["P_bleed"] <= BLEED_MAX
                and 0 <= h.health <= 100):
            rng_ok = False
            print(f"    RANGE VIOLATION at {tid}: {t} health={h.health}")
    check("all terms within documented ranges; Health in [0,100]", rng_ok)

    # Integrity-candidate must ONLY fire where a high-band cluster is seated (T-11).
    flagged = {tid for tid, h in scores.items() if h.integrity_candidate}
    check(f"integrity_candidate fires only for T-11 (got {sorted(flagged)})",
          flagged == {"T-11"})

    if failures:
        print(f"\nFAILED {len(failures)} check(s).")
        return 1
    print("\nAll health acceptance checks pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
