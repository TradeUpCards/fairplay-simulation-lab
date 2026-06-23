"""Aggregate played hands back into the player features the scorer consumes.

This is the Contract-1 bridge: the integrity/health signals (vpip, pfr,
aggression_factor, avg_pot, timing_regularity, soft_play_delta, net result)
*emerge from play* here instead of being typed in. If these match the archetype
targets, the simulation is a faithful stand-in for the static generator.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from .table import HandRecord


def _timing_regularity(latencies: list[int]) -> float:
    """1.0 = perfectly uniform timing (robotic); lower = human variance."""
    if len(latencies) < 3:
        return 0.0
    mean = statistics.fmean(latencies)
    if mean <= 0:
        return 0.0
    cv = statistics.pstdev(latencies) / mean
    return round(1.0 / (1.0 + cv), 3)


def aggregate(
    hands: list[HandRecord],
    player_ids: list[int],
    members_by_player: dict[int, frozenset[int]] | None = None,
    big_blind: int = 2,
) -> dict[int, dict]:
    members_by_player = members_by_player or {}
    dealt = defaultdict(int)
    vpip = defaultdict(int)
    pfr = defaultdict(int)
    pf_bets = defaultdict(int)
    pf_calls = defaultdict(int)
    pf_raises = defaultdict(int)
    pf_calls_post = defaultdict(int)
    latencies = defaultdict(list)
    net = defaultdict(int)
    pots_involved = defaultdict(list)
    # soft-play: EV given up in member-vs-member pots (net result when only
    # teammates are live) — proxy for soft_play_delta
    member_pot_net = defaultdict(list)

    for h in hands:
        per_hand = defaultdict(lambda: {"vol": False, "raise": False, "involved": False})
        for a in h.actions:
            pid = a.player_id
            latencies[pid].append(a.latency_ms)
            if a.street == 0:
                if a.voluntary:
                    per_hand[pid]["vol"] = True
                if a.is_raise:
                    per_hand[pid]["raise"] = True
            else:
                if a.is_raise:
                    pf_bets[pid] += 1  # bets+raises (aggression numerator)
                elif a.is_call:
                    pf_calls_post[pid] += 1  # calls (denominator)
            if a.action not in ("fold",):
                per_hand[pid]["involved"] = True

        for pid in h.seat_player_ids:
            dealt[pid] += 1
            net[pid] += h.payoffs.get(pid, 0)
            if per_hand[pid]["vol"]:
                vpip[pid] += 1
                pots_involved[pid].append(h.pot_bb)
            if per_hand[pid]["raise"]:
                pfr[pid] += 1
        # soft-play proxy: in pots contested only among teammates
        live = set(h.showdown_player_ids)
        for pid in h.seat_player_ids:
            mates = members_by_player.get(pid, frozenset())
            if mates and live and live <= (mates | {pid}) and len(live) > 1:
                member_pot_net[pid].append(h.payoffs.get(pid, 0) / big_blind)

    out: dict[int, dict] = {}
    for pid in player_ids:
        d = max(dealt[pid], 1)
        af_num = pf_bets[pid]
        af_den = pf_calls_post[pid]
        af = round(af_num / af_den, 2) if af_den else (float(af_num) if af_num else 0.0)
        soft = member_pot_net.get(pid)
        out[pid] = {
            "hands_dealt": dealt[pid],
            "vpip": round(vpip[pid] / d, 3),
            "pfr": round(pfr[pid] / d, 3),
            "aggression_factor": af,
            "avg_pot_bb": round(statistics.fmean(pots_involved[pid]), 2)
            if pots_involved[pid] else 0.0,
            "timing_regularity": _timing_regularity(latencies[pid]),
            "net_bb": round(net[pid] / big_blind, 2),
            "soft_play_delta": round(statistics.fmean(soft), 2) if soft else 0.0,
        }
    return out
