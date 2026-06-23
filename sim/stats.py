"""Pure rollup of the event log into per-player behavioral features."""
from __future__ import annotations

from collections import defaultdict


def rollup(events: list[dict], results: list[dict]) -> dict[str, dict]:
    hands = defaultdict(set)                 # player -> {hand_id} dealt in
    vpip_hands = defaultdict(set)            # preflop voluntary money in
    pfr_hands = defaultdict(set)             # preflop raise
    contested = defaultdict(set)             # any voluntary money in (any street)
    postflop_raises = defaultdict(int)
    postflop_calls = defaultdict(int)
    net = defaultdict(int)
    hand_pot = {}                            # hand_id -> pot in bb

    for r in results:
        if r.get("dealt_in"):
            hands[r["player_id"]].add(r["hand_id"])
            net[r["player_id"]] += r["net"]
            hand_pot[r["hand_id"]] = r["pot_bb"]

    for e in events:
        p = e["player_id"]
        if e["voluntary"]:
            contested[p].add(e["hand_id"])
        if e["street"] == "preflop" and e["voluntary"]:
            vpip_hands[p].add(e["hand_id"])
        if e["street"] == "preflop" and e["is_raise"]:
            pfr_hands[p].add(e["hand_id"])
        if e["street"] != "preflop":
            if e["is_raise"]:
                postflop_raises[p] += 1
            elif e["kind"] == "check_call":
                postflop_calls[p] += 1

    out: dict[str, dict] = {}
    for p, hset in hands.items():
        n = len(hset)
        calls = postflop_calls[p]
        # avg_pot_size_bb is over hands the player CONTESTED (was involved in),
        # matching the real field's "average pot when the player is involved".
        contested_pots = [hand_pot[h] for h in contested[p] if h in hand_pot]
        out[p] = {
            "lifetime_hands": n,
            "vpip": round(len(vpip_hands[p]) / n, 3) if n else 0.0,
            "pfr": round(len(pfr_hands[p]) / n, 3) if n else 0.0,
            "aggression_factor": (round(postflop_raises[p] / calls, 3)
                                  if calls else float(postflop_raises[p])),
            "avg_pot_size_bb": (round(sum(contested_pots) / len(contested_pots), 2)
                                if contested_pots else 0.0),
            "hands_contested": len(contested[p]),
            "net_chips": net[p],
        }
    return out
