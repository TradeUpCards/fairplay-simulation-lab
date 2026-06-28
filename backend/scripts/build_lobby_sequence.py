"""Freeze a policy-driven, two-room lobby sequence (demo Part 2).

Two rooms start identical. Each step, the SAME players stand and the SAME players
arrive — but each policy decides WHERE arrivals sit:

  - Standard seats each arrival at the **fullest open table** (concentration),
  - FairPlay routes each arrival via the **real router** (spread toward healthy tables).

So the two rooms diverge: Standard fills tables to capacity (they show as Full at the
bottom of the list), FairPlay keeps more healthy tables open. We record the per-step
seat events for an admin diagnostic, and emit the player-safe lobby for each room
(joinable tables first by that policy's order, full tables at the bottom).

Run:  python backend/scripts/build_lobby_sequence.py [--data-root DIR] [--player P-104]
Large-room: --data-root playsim/out/large-room-data --player P-10001
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scoring.integrity import score_integrity  # noqa: E402
from scoring.health import build_cluster_band_index, score_all_tables  # noqa: E402
from scoring.router import route  # noqa: E402

OUT = ROOT / "data" / "derived" / "lobby_sequence.json"

# Player-safe stat columns pulled from the (static) roster entry.
STAT_KEYS = {"avg_pot_size_usd": "avg_pot_usd", "hands_per_hour": "hands_per_hour"}


def _load(data_root: Path) -> dict:
    rel = json.loads((data_root / "relationships.json").read_text(encoding="utf-8"))
    praw = json.loads((data_root / "players.json").read_text(encoding="utf-8"))
    players = praw["players"] if isinstance(praw, dict) else praw
    roster = json.loads((data_root / "table_roster.json").read_text(encoding="utf-8"))["tables"]
    sess_path = data_root / "sessions.json"
    sessions = []
    if sess_path.exists():
        sessions = [s for s in json.loads(sess_path.read_text(encoding="utf-8")).get("sessions", [])
                    if "session_id" in s]
    classifications = None
    cl_path = data_root / "derived" / "classifications.json"
    if cl_path.exists():
        cl = json.loads(cl_path.read_text(encoding="utf-8"))
        rows = cl["classifications"] if isinstance(cl, dict) else cl
        classifications = {c["player_id"]: c["archetype"] for c in rows}
    return {"rel": rel, "players": players, "roster": roster, "sessions": sessions,
            "classifications": classifications}


# ── room mutation ─────────────────────────────────────────────────────────────

def _seated_set(tables: list[dict]) -> set[str]:
    return {pid for t in tables for pid in t.get("seated_player_ids", [])}


def _table_of(tables: list[dict], pid: str) -> dict | None:
    for t in tables:
        if pid in t.get("seated_player_ids", []):
            return t
    return None


def _unseat(tables: list[dict], pid: str) -> str | None:
    t = _table_of(tables, pid)
    if not t:
        return None
    t["seated_player_ids"].remove(pid)
    t["seated_count"] -= 1
    t["open_seats"] = t.get("open_seats", 0) + 1
    return t["table_id"]


def _seat(tables: list[dict], pid: str, table_id: str) -> None:
    t = next(x for x in tables if x["table_id"] == table_id)
    t["seated_player_ids"].append(pid)
    t["seated_count"] += 1
    t["open_seats"] -= 1


def _most_full_open(tables: list[dict]) -> str | None:
    """Standard policy: the fullest table that still has an open seat."""
    open_t = [t for t in tables if t.get("open_seats", 0) > 0]
    if not open_t:
        return None
    return min(open_t, key=lambda t: (-t["seated_count"], t["table_id"]))["table_id"]


def _fairplay_open(ctx: dict, tables: list[dict], player_id: str) -> list[str]:
    """FairPlay: the router's ranked open-table order (top = best routed seat)."""
    by = {p["player_id"]: p for p in ctx["players"]}
    health = {h.table_id: h for h in score_all_tables(tables, by, ctx["cbi"], sessions=ctx["sessions"])}
    routed = route(player_id, tables, by, ctx["cbi"], health, ctx["classifications"])
    return [t["table_id"] for t in routed["player_lobby"]]


# ── lobby rows (player-safe) ──────────────────────────────────────────────────

def _row(t: dict, roster_by_id: dict, badge: str, badge_label: str) -> dict:
    rentry = roster_by_id.get(t["table_id"], {})
    row = {
        "table_id": t["table_id"],
        "stakes": t.get("stakes", rentry.get("stakes", "")),
        "game_type": t.get("game_type", rentry.get("game_type", "NLH")),
        "max_seats": t["max_seats"],
        "seated_count": t["seated_count"],
        "open_seats": t["open_seats"],
        "pace_label": t.get("pace_label", rentry.get("pace_label", "")),
        "badge": badge,
        "badge_label": badge_label,
    }
    for src, dst in STAT_KEYS.items():
        if src in rentry:
            row[dst] = rentry[src]
    seed = sum(ord(c) for c in t["table_id"])
    row["plrs_per_flop_pct"] = 26 + (seed % 38)
    return row


def _standard_lobby(tables: list[dict], roster_by_id: dict) -> list[dict]:
    """Joinable tables most-full first; full tables at the bottom. Neutral badges."""
    joinable = sorted([t for t in tables if t["open_seats"] > 0],
                      key=lambda t: (-t["seated_count"], t["table_id"]))
    full = sorted([t for t in tables if t["open_seats"] <= 0], key=lambda t: t["table_id"])
    return [_row(t, roster_by_id, "available", "Available") for t in joinable + full]


def _fairplay_lobby(ctx: dict, tables: list[dict], player_id: str, roster_by_id: dict) -> list[dict]:
    """Router-ranked joinable tables (with badges); full tables at the bottom."""
    by = {p["player_id"]: p for p in ctx["players"]}
    health = {h.table_id: h for h in score_all_tables(tables, by, ctx["cbi"], sessions=ctx["sessions"])}
    routed = route(player_id, tables, by, ctx["cbi"], health, ctx["classifications"])
    by_tid = {t["table_id"]: t for t in tables}
    rows = []
    for pl in routed["player_lobby"]:  # already ordered + player-safe badges
        t = by_tid[pl["table_id"]]
        rows.append(_row(t, roster_by_id, pl["badge"], pl["badge_label"]))
    seen = {pl["table_id"] for pl in routed["player_lobby"]}
    full = sorted([t for t in tables if t["table_id"] not in seen], key=lambda t: t["table_id"])
    rows += [_row(t, roster_by_id, "available", "Available") for t in full]
    return rows


def _composition(ctx: dict, table: dict) -> list[dict]:
    """Seated archetype mix (operator diagnostic — 'who is at this table')."""
    cl = ctx["classifications"] or {}
    counts = Counter(cl.get(pid, "unknown") for pid in table.get("seated_player_ids", []))
    return [{"archetype": a, "count": n} for a, n in counts.most_common()]


def _op_details(ctx: dict, tables: list[dict], player_id: str) -> dict:
    """OPERATOR-side per-table detail (the 'pull back the curtain' data): health +
    term breakdown, seating-risk, rank/badge, and the seated composition. Shown only
    behind the curtain button, never in the player-facing rows."""
    by = {p["player_id"]: p for p in ctx["players"]}
    health = {h.table_id: h for h in score_all_tables(tables, by, ctx["cbi"], sessions=ctx["sessions"])}
    routed = route(player_id, tables, by, ctx["cbi"], health, ctx["classifications"])
    opv = {o["table_id"]: o for o in routed["operator_view"]}
    out = {}
    for t in tables:
        tid = t["table_id"]
        h = health.get(tid)
        o = opv.get(tid)
        d = {
            "table_id": tid, "stakes": t.get("stakes", ""),
            "seated_count": t["seated_count"], "max_seats": t["max_seats"],
            "open_seats": t["open_seats"], "full": t["open_seats"] <= 0,
            "composition": _composition(ctx, t),
        }
        if h:
            d.update(health=round(h.health, 1), band=h.band, terms=h.terms,
                     reasons=[{"code": rc.code, "detail": rc.detail} for rc in h.reason_codes])
        if o:
            d.update(rank=o["rank"], badge=o["badge"], fit=o["fit"],
                     delta_health=o["delta_health"], seating_risk=o["seating_risk"])
        out[tid] = d
    return out


def _event(ctx: dict, pid: str, action: str, table_id: str | None, tables: list[dict]) -> dict:
    occ = ""
    if table_id:
        t = next((x for x in tables if x["table_id"] == table_id), None)
        if t:
            occ = f"{t['seated_count']}/{t['max_seats']}"
    arch = (ctx["classifications"] or {}).get(pid)
    return {"player_id": pid, "archetype": arch, "action": action,
            "table_id": table_id, "occ_after": occ}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=str(ROOT / "data"))
    ap.add_argument("--player", default="P-104")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--stand", type=int, default=6)
    ap.add_argument("--sit", type=int, default=14)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    data_root = Path(args.data_root)
    ctx = _load(data_root)
    ctx["integ"] = score_integrity(ctx["rel"], ctx["players"])  # seating-independent → once
    ctx["cbi"] = build_cluster_band_index(ctx["rel"], ctx["integ"])
    roster_by_id = {t["table_id"]: t for t in ctx["roster"]}
    rng = random.Random(args.seed)

    room_std = copy.deepcopy(ctx["roster"])
    room_fp = copy.deepcopy(ctx["roster"])

    steps = []
    for i in range(args.steps):
        std_events: list[dict] = []
        fp_events: list[dict] = []
        if i > 0:
            seated = sorted(_seated_set(room_std) - {args.player})
            leavers = rng.sample(seated, min(args.stand, len(seated)))
            for pid in leavers:
                t1 = _unseat(room_std, pid)
                std_events.append(_event(ctx, pid, "stand", t1, room_std))
                t2 = _unseat(room_fp, pid)
                fp_events.append(_event(ctx, pid, "stand", t2, room_fp))
            unseated = sorted({p["player_id"] for p in ctx["players"]} - _seated_set(room_std)
                              - {args.player})
            arrivals = rng.sample(unseated, min(args.sit, len(unseated)))
            for pid in arrivals:
                ts = _most_full_open(room_std)
                if ts:
                    _seat(room_std, pid, ts)
                    std_events.append(_event(ctx, pid, "sit", ts, room_std))
                ranked = _fairplay_open(ctx, room_fp, pid)
                tf = ranked[0] if ranked else None
                if tf:
                    _seat(room_fp, pid, tf)
                    fp_events.append(_event(ctx, pid, "sit", tf, room_fp))
        standard = _standard_lobby(room_std, roster_by_id)
        fairplay = _fairplay_lobby(ctx, room_fp, args.player, roster_by_id)
        label = "Open" if i == 0 else f"After activity {i}"
        steps.append({"label": label, "standard": standard, "fairplay": fairplay,
                      "events": {"standard": std_events, "fairplay": fp_events},
                      "op_detail": _op_details(ctx, room_fp, args.player)})

    out = {
        "meta": {
            "source": str(data_root.name),
            "seed": args.seed,
            "player_id": args.player,
            "note": ("Two rooms, same arrivals/departures, seated by each policy "
                     "(Standard = most-full; FairPlay = real router). Rooms diverge over "
                     "steps. Player-safe lobby rows; full tables at the bottom. "
                     "events[] is an admin diagnostic of the per-step seating."),
        },
        "steps": steps,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(steps)}-step policy-driven lobby for {args.player} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
