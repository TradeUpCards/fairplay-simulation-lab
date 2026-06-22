"""Validate the router (kickoff §2 ⑧ acceptance).

Pinned acceptance (P-104 seeking a table, CASE-A):
* T-8  → badge **recommended** ("Recommended for you")
* T-14 → badge **good_fit**    ("Good fit")
* T-22 → badge **available**   (not promoted to the new player)
* T-11 → **hidden_gated**      (integrity hard-gate; removed from lobby)
* Rank ordering T-8 > T-14 > T-22.

Plus the player-facing/operator-facing guardrail: the player_lobby view must
NOT leak rank, health, seating-risk, archetype, or integrity language.

Run:  python scripts/validate_router.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.integrity import score_integrity  # noqa: E402
from scoring.health import build_cluster_band_index, score_all_tables  # noqa: E402
from scoring.router import route, LOBBY_SAFE_FIELDS  # noqa: E402

# POSITIVE whitelist: the ONLY keys a player_lobby entry may contain. Asserting a
# subset of this (rather than scanning for known-bad keys) means a future leak
# through any new field fails the test by default — the robust check.
ALLOWED_LOBBY_KEYS = set(LOBBY_SAFE_FIELDS) | {"badge", "badge_label"}

# Token denylist — a secondary backstop on the *values* (a safe key could still
# carry a leaky string, e.g. a style label). Kept broad on purpose.
FORBIDDEN_LOBBY_TOKENS = ("predator", "predatory", "integrity", "cluster",
                          "collusion", "bot", "soft_play", "vpip", "pfr",
                          "flagged", "suspect", "seating_risk", "declining")


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
    health = {h.table_id: h for h in score_all_tables(roster, by, cbi, sessions=sessions)}

    res = route("P-104", roster, by, cbi, health)
    op = {r["table_id"]: r for r in res["operator_view"]}

    failures = []

    def check(name, ok, got=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{got}]" if got else ""))
        if not ok:
            failures.append(name)

    print("=== Operator view (P-104) ===")
    print(f"  {'tbl':5} {'rank':>5} {'badge':13} {'health':>6} {'risk':>7}")
    for r in res["operator_view"]:
        print(f"  {r['table_id']:5} {r['rank']:5.1f} {r['badge']:13} "
              f"{r['health']:6.1f} {r['seating_risk']:>7}")

    print("\n=== Acceptance ===")
    check("T-8 badge == recommended", op["T-8"]["badge"] == "recommended",
          f"got {op['T-8']['badge']}")
    check("T-14 badge == good_fit", op["T-14"]["badge"] == "good_fit",
          f"got {op['T-14']['badge']}")
    check("T-22 badge == available (not promoted)", op["T-22"]["badge"] == "available",
          f"got {op['T-22']['badge']}")
    check("T-11 badge == hidden_gated (integrity gate)",
          op["T-11"]["badge"] == "hidden_gated", f"got {op['T-11']['badge']}")
    check("rank ordering T-8 > T-14 > T-22",
          op["T-8"]["rank"] > op["T-14"]["rank"] > op["T-22"]["rank"],
          f"{op['T-8']['rank']} > {op['T-14']['rank']} > {op['T-22']['rank']}")

    # CASE-A: T-22 must never be promoted to the new player.
    check("T-22 not promoted (not recommended/good_fit)",
          op["T-22"]["badge"] not in ("recommended", "good_fit"))

    print("\n=== Player-facing leakage guardrail ===")
    lobby = res["player_lobby"]
    # 1. Gated table absent from lobby entirely.
    lobby_ids = {e["table_id"] for e in lobby}
    check("T-11 (gated) absent from player_lobby", "T-11" not in lobby_ids)
    # 2. Whitelist subset: every lobby key must be in the allowed safe set.
    leaked_keys = {k for e in lobby for k in e if k not in ALLOWED_LOBBY_KEYS}
    check(f"player_lobby keys are a subset of the safe whitelist "
          f"(stray keys: {leaked_keys or 'none'})", not leaked_keys)
    # 3. No operator-language tokens anywhere in the serialized lobby.
    blob = json.dumps(lobby).lower()
    leaked_tokens = [t for t in FORBIDDEN_LOBBY_TOKENS if t in blob]
    check(f"no operator-language tokens in player_lobby (found {leaked_tokens or 'none'})",
          not leaked_tokens)

    if failures:
        print(f"\nFAILED {len(failures)} check(s).")
        return 1
    print("\nAll router acceptance + guardrail checks pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
