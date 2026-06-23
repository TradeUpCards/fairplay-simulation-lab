"""Validate the seating scores (kickoff §2 ⑦ acceptance).

Pinned acceptance:
* **Seating-risk(P-104, T-22) == HIGH** (the §2 ⑦ acceptance).
* P-104 seating-risk LOW at the healthy alternatives T-8 / T-14 (CASE-A: route
  the new player there).
* Fit(P-104) matches the index.html §05 worked example: T-8=74, T-14=58, T-22=22.
* ΔHealth signs are sane (filling a healthy table ≥ 0).
* Integrity hard-gate: any new player at T-11 (CL-001 seated) is gated out.

Run:  python scripts/validate_seating.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scoring.integrity import score_integrity  # noqa: E402
from scoring.health import build_cluster_band_index, score_all_tables  # noqa: E402
from scoring.seating import score_seating  # noqa: E402


def main() -> int:
    rel = json.loads((ROOT / "data" / "relationships.json").read_text(encoding="utf-8"))
    praw = json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8"))
    players = praw["players"] if isinstance(praw, dict) else praw
    by = {p["player_id"]: p for p in players}
    roster = json.loads((ROOT / "data" / "table_roster.json").read_text(encoding="utf-8"))["tables"]
    tbl_by_id = {t["table_id"]: t for t in roster}
    sessions = [s for s in json.loads((ROOT / "data" / "sessions.json").read_text(encoding="utf-8"))["sessions"]
                if "session_id" in s]

    integ = score_integrity(rel, players)
    cbi = build_cluster_band_index(rel, integ)
    health = {h.table_id: h for h in score_all_tables(roster, by, cbi, sessions=sessions)}

    def seat(pid, tid):
        return score_seating(pid, tbl_by_id[tid], by, cbi, health[tid])

    failures = []

    def check(name, ok, got=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{got}]" if got else ""))
        if not ok:
            failures.append(name)

    print("=== P-104 (new) across candidate tables ===")
    print(f"  {'table':6} {'fit':>5} {'dHealth':>8} {'risk':>7} {'health':>6} {'band':20} gated")
    for tid in ("T-8", "T-14", "T-22", "T-11"):
        s = seat("P-104", tid)
        h = health[tid]
        print(f"  {tid:6} {s.fit:5.0f} {s.delta_health:8.1f} {s.seating_risk:>7} "
              f"{h.health:6.1f} {h.band:20} {'YES' if s.integrity_gated else ''}")

    print("\n=== Acceptance ===")
    t22 = seat("P-104", "T-22")
    check("Seating-risk(P-104, T-22) == HIGH", t22.seating_risk == "high",
          f"got {t22.seating_risk}")

    t8 = seat("P-104", "T-8")
    t14 = seat("P-104", "T-14")
    check("Seating-risk(P-104, T-8) == LOW", t8.seating_risk == "low",
          f"got {t8.seating_risk}")
    check("Seating-risk(P-104, T-14) == LOW", t14.seating_risk == "low",
          f"got {t14.seating_risk}")

    # Fit worked-example values (index.html §05)
    check("Fit(P-104, T-8) == 74", t8.fit == 74, f"got {t8.fit}")
    check("Fit(P-104, T-14) == 58", t14.fit == 58, f"got {t14.fit}")
    check("Fit(P-104, T-22) == 22", t22.fit == 22, f"got {t22.fit}")

    # ΔHealth sanity: adding the new player to a healthy table should not worsen it.
    check("dHealth(P-104, T-8) >= 0 (fills a healthy table)",
          t8.delta_health >= 0, f"got {t8.delta_health:+.1f}")

    # Integrity hard-gate at T-11 (CL-001 high-band cluster seated).
    t11 = seat("P-104", "T-11")
    check("T-11 integrity hard-gated (CL-001 seated)", t11.integrity_gated,
          f"gated={t11.integrity_gated}")
    check("T-11 gated seating-risk == HIGH", t11.seating_risk == "high")

    if failures:
        print(f"\nFAILED {len(failures)} check(s).")
        return 1
    print("\nAll seating acceptance checks pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
