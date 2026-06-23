"""Playsim-native hand history export (rich hand documents, not legacy flat events)."""

from __future__ import annotations

from typing import Any

from .population import format_player_id
from .runner import SimResult
from .table import HandRecord

_STREET_NAMES = ("preflop", "flop", "turn", "river")


def _street_name(street: int) -> str:
    if 0 <= street < len(_STREET_NAMES):
        return _STREET_NAMES[street]
    return f"street_{street}"


def hand_to_dict(
    hand: HandRecord,
    *,
    table_id: str,
    archetype_of: dict[int, str] | None = None,
    cluster_of: dict[int, str | None] | None = None,
    household_of: dict[int, str | None] | None = None,
) -> dict[str, Any]:
    bb = hand.big_blind or 1
    archetype_of = archetype_of or {}
    cluster_of = cluster_of or {}
    household_of = household_of or {}
    seats = []
    for seat_idx, pid in enumerate(hand.seat_player_ids):
        hole = hand.hole.get(pid)
        seats.append({
            "seat": seat_idx + 1,
            "player_id": format_player_id(pid),
            "starting_stack_bb": round(hand.starting_stacks.get(pid, 0) / bb, 2),
            "hole": list(hole) if hole else None,
            "archetype": archetype_of.get(pid),
            "cluster_id": cluster_of.get(pid),
            "household_id": household_of.get(pid),
        })
    actions = []
    for a in hand.actions:
        actions.append({
            "player_id": format_player_id(a.player_id),
            "street": a.street,
            "street_name": _street_name(a.street),
            "action": a.action,
            "amount": a.amount,
            "pot_before": a.pot_before,
            "to_call": None,
            "voluntary": a.voluntary,
            "is_raise": a.is_raise,
            "is_call": a.is_call,
            "latency_ms": a.latency_ms,
        })
    showdown = set(hand.showdown_player_ids)
    results = []
    for pid in hand.seat_player_ids:
        net = hand.payoffs.get(pid, 0)
        results.append({
            "player_id": format_player_id(pid),
            "net_chips": net,
            "net_bb": round(net / bb, 2),
            "dealt_in": True,
            "showdown": pid in showdown,
        })
    return {
        "hand_id": f"{table_id}-H{hand.hand_id:04d}",
        "table_id": table_id,
        "button_seat": hand.button_seat + 1,
        "big_blind": bb,
        "seats": seats,
        "board": list(hand.board),
        "actions": actions,
        "results": results,
        "pot_bb": hand.pot_bb,
    }


def session_to_hand_docs(
    result: SimResult,
    *,
    table_id: str,
) -> list[dict[str, Any]]:
    arch = {p.player_id: p.archetype for p in result.roster}
    cluster = {p.player_id: p.cluster_id for p in result.roster}
    household = {p.player_id: p.household_id for p in result.roster}
    return [
        hand_to_dict(
            h,
            table_id=table_id,
            archetype_of=arch,
            cluster_of=cluster,
            household_of=household,
        )
        for h in result.hands
    ]


def build_player_index(
    hand_docs: list[dict[str, Any]],
    *,
    targets: dict[str, int] | None = None,
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for doc in hand_docs:
        tid = doc["table_id"]
        for seat in doc["seats"]:
            pid = seat["player_id"]
            entry = index.setdefault(pid, {
                "hands_dealt": 0,
                "hands_target": targets.get(pid) if targets else None,
                "table_ids": [],
            })
            entry["hands_dealt"] += 1
            if tid not in entry["table_ids"]:
                entry["table_ids"].append(tid)
    return index


def features_for_export(result: SimResult) -> dict[str, dict[str, Any]]:
    out: dict[str, dict] = {}
    for pid, feats in result.features.items():
        row = dict(feats)
        row["player_id"] = format_player_id(pid)
        row["archetype"] = next(p.archetype for p in result.roster if p.player_id == pid)
        out[format_player_id(pid)] = row
    return out
