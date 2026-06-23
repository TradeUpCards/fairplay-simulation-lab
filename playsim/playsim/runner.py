"""Orchestrate a seeded session: deal hands, rotate position, collect features.

``run_session`` is the one entry point. Same ``(roster, seed, n_hands)`` →
byte-identical result, every time (the replay guarantee). The button rotates
each hand by remapping players to seats, so positions are fair without touching
PokerKit's blind posting.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .agent import ArchetypeAgent
from .features import aggregate
from .knobs import knobs_for, session_min_for
from .table import HandRecord, play_hand

# archetypes the predator / cluster agents treat as "weak" prey
_WEAK = frozenset({"new", "recreational", "promo_hunter"})
# the vulnerable cohort whose play-time is the north-star metric
_COHORT = frozenset({"new", "recreational", "promo_hunter"})


def _effective_session_min(
    base_session_min: float, tilt_quit: float, loss_per_100_bb: float, spread: float
) -> float:
    """A player's session budget (minutes) before logging off.

    Starts at the archetype's natural session length and **shrinks the faster the
    player is bleeding** (tilt, scaled by ``tilt_quit``). This is what turns a
    higher loss-rate at an unhealthy table into shorter sessions → less retained
    paid seat-time. The loss-rate is *derived* from real play (not asserted), so
    the play-decay it produces is a genuine consequence of the routing.
    """
    tilt = 1.0 - max(0.0, loss_per_100_bb) / 130.0 * (0.5 + tilt_quit)
    tilt = max(0.12, min(1.25, tilt))
    return base_session_min * spread * tilt


@dataclass(frozen=True)
class Player:
    player_id: int
    archetype: str
    cluster_id: str | None = None
    household_id: str | None = None


@dataclass
class SimResult:
    seed: int
    n_hands: int
    big_blind: int
    roster: list[Player]
    hands: list[HandRecord]
    features: dict[int, dict]
    label: str = ""
    persist_stacks: bool = False
    busts: dict[int, int] = field(default_factory=dict)        # rebuys per player
    final_stacks_bb: dict[int, float] = field(default_factory=dict)
    # retention / paid-seat-time (only populated when retention=True)
    retention: bool = False
    hands_played: dict[int, int] = field(default_factory=dict)
    seat_minutes: dict[int, float] = field(default_factory=dict)
    left_at_minute: dict[int, float | None] = field(default_factory=dict)
    dealt_player_hands: int = 0
    paid_seat_minutes: float = 0.0
    hands_per_hour: int = 80
    minutes_per_hand: float = 0.75

    def realized_vs_target(self) -> list[dict]:
        rows = []
        for p in self.roster:
            t = knobs_for(p.archetype).targets
            f = self.features[p.player_id]
            rows.append({
                "player_id": p.player_id, "archetype": p.archetype,
                "vpip": (f["vpip"], t.get("vpip")),
                "pfr": (f["pfr"], t.get("pfr")),
                "aggression_factor": (f["aggression_factor"], t.get("aggression_factor")),
                "avg_pot_bb": (f["avg_pot_bb"], t.get("avg_pot_bb")),
                "timing_regularity": f["timing_regularity"],
                "soft_play_delta": f["soft_play_delta"],
                "net_bb": f["net_bb"],
            })
        return rows


def _members_by_player(roster: list[Player]) -> dict[int, frozenset[int]]:
    by_cluster: dict[str, list[int]] = {}
    for p in roster:
        if p.cluster_id:
            by_cluster.setdefault(p.cluster_id, []).append(p.player_id)
    out: dict[int, frozenset[int]] = {}
    for members in by_cluster.values():
        s = frozenset(members)
        for pid in members:
            out[pid] = s - {pid}
    return out


def run_session(
    roster: list[Player],
    n_hands: int,
    seed: int,
    *,
    starting_stack_bb: int = 100,
    sb: int = 1,
    bb: int = 2,
    equity_samples: int = 30,
    label: str = "",
    persist_stacks: bool = False,
    rebuy_threshold_bb: int = 8,
    retention: bool = False,
    hands_per_hour: int = 80,
    skill_edge: float = 0.0,
    quota_hands: dict[int, int] | None = None,
) -> SimResult:
    """Play a seeded session.

    Three modes:

    * default (``persist_stacks=False``) — stacks reset each hand: stable feature
      calibration (the **integrity loop**).
    * ``persist_stacks=True`` — chips carry over, busted players rebuy: bust
      dynamics without anyone leaving (a fixed-length health snapshot).
    * ``retention=True`` — chips carry over AND players **log off** (the leave
      model). The vulnerable cohort quits when it busts/tilts, so **play-time
      decays**. ``n_hands`` is the horizon; the session ends early if the table
      empties. This is the **north-star loop**: how long does the cohort play?
    * ``quota_hands={player_id: limit}`` — players leave immediately after
      being dealt their quota hand. ``n_hands`` remains the table horizon.
    """
    if len(roster) < 2:
        raise ValueError("need at least 2 players at the table")
    persist_stacks = persist_stacks or retention

    rng = random.Random(seed)
    agents = {
        p.player_id: ArchetypeAgent(p.player_id, knobs_for(p.archetype), equity_samples)
        for p in roster
    }
    knobs = {p.player_id: knobs_for(p.archetype) for p in roster}
    arch_of = {p.player_id: p.archetype for p in roster}
    cohort = {p.player_id for p in roster if p.archetype in _COHORT}
    members = _members_by_player(roster)
    weak_ids = frozenset(p.player_id for p in roster if p.archetype in _WEAK)
    start = starting_stack_bb * bb
    n = len(roster)
    pids = [p.player_id for p in roster]

    min_per_hand = 60.0 / hands_per_hour
    # each cohort player gets a seeded session-length jitter so they don't all
    # quit at the same minute
    spread = {pid: rng.uniform(0.85, 1.15) for pid in pids}

    stacks = {pid: start for pid in pids}
    busts = {pid: 0 for pid in pids}
    hands_played = {pid: 0 for pid in pids}
    seat_minutes = {pid: 0.0 for pid in pids}
    net_session = {pid: 0.0 for pid in pids}
    left_at_min: dict[int, float | None] = {pid: None for pid in pids}
    quota_targets = (
        {int(pid): max(0, int(limit)) for pid, limit in quota_hands.items()}
        if quota_hands is not None else None
    )
    seated = [
        pid for pid in pids
        if quota_targets is None or pid not in quota_targets or quota_targets[pid] > 0
    ]
    dealt_player_hands = 0

    hands: list[HandRecord] = []
    for h in range(n_hands):
        if len(seated) < 2:
            break  # the table broke
        m = len(seated)
        dealer = h % m
        order = [seated[(dealer + s) % m] for s in range(m)]
        seat_agents = [agents[pid] for pid in order]
        seat_stacks = [stacks[pid] for pid in order] if persist_stacks else [start] * m
        rec = play_hand(
            seat_agents, order, seat_stacks, sb, bb, rng, h, members, weak_ids
        )
        # Skill-edge model: heuristic play alone yields no reliable chip-EV edge,
        # so we apply a small ZERO-SUM transfer among contestants from weaker to
        # stronger players — the bb/100 skill gap that variance otherwise hides.
        # It's a behavioral *input* (a known poker quantity); health/seat-time
        # stay *derived* from the resulting chip flow (no circularity). A real
        # solver brain (playsim.baselines) would make this emerge instead.
        if skill_edge > 0:
            contest = ({a.player_id for a in rec.actions if a.street > 0}
                       | set(rec.showdown_player_ids)) & set(rec.payoffs)
            if len(contest) >= 2:
                sk = {pid: knobs[pid].skill for pid in contest}
                mean_sk = sum(sk.values()) / len(sk)
                pot_chips = rec.pot_bb * bb
                for pid in contest:
                    rec.payoffs[pid] += int(round((sk[pid] - mean_sk) * skill_edge * pot_chips))
        hands.append(rec)

        dealt_player_hands += m
        for pid in order:
            hands_played[pid] += 1
            seat_minutes[pid] += min_per_hand     # paid seat-time accrues

        leavers: set[int] = set()
        if persist_stacks:
            for pid in order:
                payoff = rec.payoffs.get(pid, 0)
                stacks[pid] += payoff
                net_session[pid] += payoff / bb
                if stacks[pid] < rebuy_threshold_bb * bb:   # busted → always rebuy
                    busts[pid] += 1
                    stacks[pid] = start
                # the cohort logs off when its (tilt-shortened) session is spent;
                # the field stays put, keeping the experiment controlled
                if retention and pid in cohort:
                    hp = hands_played[pid]
                    loss100 = (-net_session[pid]) / (hp / 100.0) if hp >= 15 else 0.0
                    budget = _effective_session_min(
                        session_min_for(arch_of[pid]), knobs[pid].tilt_quit,
                        loss100, spread[pid],
                    )
                    if seat_minutes[pid] >= budget:
                        leavers.add(pid)
        if quota_targets is not None:
            for pid in order:
                target = quota_targets.get(pid)
                if target is not None and hands_played[pid] >= target:
                    leavers.add(pid)
        if leavers:
            for pid in order:
                if pid not in leavers:
                    continue
                seated.remove(pid)
                if left_at_min[pid] is None:
                    left_at_min[pid] = round(seat_minutes[pid], 1)

    feats = aggregate(hands, pids, members, bb)
    return SimResult(
        seed=seed, n_hands=len(hands), big_blind=bb, roster=roster,
        hands=hands, features=feats, label=label,
        persist_stacks=persist_stacks,
        busts=busts if persist_stacks else {},
        final_stacks_bb={pid: round(stacks[pid] / bb, 1) for pid in pids}
        if persist_stacks else {},
        retention=retention,
        hands_played=hands_played if retention or quota_targets is not None else {},
        seat_minutes={pid: round(v, 1) for pid, v in seat_minutes.items()}
        if retention else {},
        left_at_minute=left_at_min if retention else {},
        dealt_player_hands=dealt_player_hands if retention or quota_targets is not None else 0,
        paid_seat_minutes=round(sum(seat_minutes.values()), 1) if retention else 0.0,
        hands_per_hour=hands_per_hour, minutes_per_hand=round(min_per_hand, 3),
    )
