"""Room orchestrator — the closed-loop, per-hand, multi-table simulator.

Generalizes ``run_session``'s single-table loop to a global clock across all
tables, with seekers arriving over a horizon and being placed by a swappable
``SeatingPolicy``. Reuses the playsim primitives — ``play_hand``,
``apply_hand_accounting`` (the U1 helper), ``_effective_session_min``,
``derive_table_seed`` — so the economics are identical to ``run_session``.

Determinism (R3/AE5): each table owns ONE persistent ``Random`` for its whole
lifetime (keyed on ``derive_table_seed(master_seed, table_id)``), table_ids are
stable and never renumbered on break, and per-step table iteration is sorted.
Byte-identical replay survives a mid-run break.

Guardrail (R12): this module never imports ``playsim/health.py``. Routing uses
ONLY the backend predicted health reached through the policy/adapter. Realized
chip-flow outcomes are emitted as raw per-player state for evaluation (U6) and
never feed a seating decision.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from .arrivals import ArrivalIntent, build_arrival_intents
from .agent import ArchetypeAgent
from .knobs import knobs_for, session_min_for
from .population import (
    derive_table_seed,
    format_player_id,
    load_classifications,
    load_players_by_id,
    load_table_roster,
    parse_player_id,
)
from .router_adapter import make_table_dict
from .runner import _effective_session_min, apply_hand_accounting
from .table import HandRecord, play_hand

# Mirrors runner._COHORT / _WEAK — the vulnerable north-star cohort and the set
# the predator/cluster agents treat as prey.
COHORT = frozenset({"new", "recreational", "promo_hunter"})
WEAK = COHORT


@dataclass
class _Table:
    table_id: str
    max_seats: int
    style: str
    trend: str
    stakes: str
    game_type: str
    pace_label: str
    rng: random.Random
    seated: list[int] = field(default_factory=list)
    hands_dealt: int = 0

    @property
    def open_seats(self) -> int:
        return max(0, self.max_seats - len(self.seated))


@dataclass
class RoomResult:
    policy_name: str
    master_seed: int
    horizon_min: float
    hands_per_hour: int
    min_per_hand: float
    starting_stack_bb: int
    skill_edge: float
    equity_samples: int
    arrival_intents: list[ArrivalIntent]
    routing_decisions: list[dict]
    seat_events: list[dict]
    sessions: list[dict]
    table_timelines: dict
    checkpoints: dict
    hands_total: int
    # per-player final state (chip-flow — evaluation only)
    archetype_of: dict
    net_bb: dict
    seat_minutes: dict
    hands_played: dict
    busts: dict
    left_at_minute: dict
    balked: list[int]
    deferred: list[int]


class RoomSim:
    def __init__(
        self,
        policy,
        *,
        root: Path | None = None,
        master_seed: int = 42,
        horizon_min: float = 480.0,
        hands_per_hour: int = 80,
        equity_samples: int = 20,
        starting_stack_bb: int = 40,
        sb: int = 1,
        bb: int = 2,
        rebuy_threshold_bb: int = 8,
        skill_edge: float = 1.6,
        tables: list[str] | None = None,
        checkpoints_min: tuple[float, ...] = (120.0, 240.0, 480.0),
        arrival_intents: list[ArrivalIntent] | None = None,
    ) -> None:
        self.policy = policy
        self.master_seed = master_seed
        self.horizon_min = horizon_min
        self.hands_per_hour = hands_per_hour
        self.min_per_hand = 60.0 / hands_per_hour
        self.equity_samples = equity_samples
        self.starting_stack_bb = starting_stack_bb
        self.sb, self.bb = sb, bb
        self.start = starting_stack_bb * bb
        self.rebuy_threshold_bb = rebuy_threshold_bb
        self.skill_edge = skill_edge
        self.checkpoints_min = checkpoints_min

        self.players_by_id = load_players_by_id(root)
        self.classifications = load_classifications(root)
        roster = load_table_roster(root)
        if tables is not None:
            wanted = set(tables)
            roster = [t for t in roster if t["table_id"] in wanted]

        # arrival stream is policy-independent; allow injection so both arms share it
        self.arrival_intents = (
            arrival_intents if arrival_intents is not None
            else build_arrival_intents(horizon_min, seed=master_seed, root=root)
        )
        # restrict arrivals to classified players (always true for the fixture)
        self.arrival_intents = [a for a in self.arrival_intents
                                if format_player_id(a.player_id) in self.classifications]

        # global per-player state
        self.agents: dict[int, ArchetypeAgent] = {}
        self.knobs: dict[int, object] = {}
        self.archetype_of: dict[int, str] = {}
        self.cluster_of: dict[int, str | None] = {}
        self.spread: dict[int, float] = {}
        self.stacks: dict[int, int] = {}
        self.net_bb: dict[int, float] = {}
        self.busts: dict[int, int] = {}
        self.seat_minutes: dict[int, float] = {}
        self.hands_played: dict[int, int] = {}
        self.left_at_minute: dict[int, float | None] = {}
        self.departed: set[int] = set()          # terminal for the run (tilt/balk/defer)
        self._presence: dict[int, dict] = {}

        # outputs / causal trace
        self.routing_decisions: list[dict] = []
        self.seat_events: list[dict] = []
        self.sessions: list[dict] = []
        self.hands_total = 0
        self.balked: list[int] = []
        self.deferred: list[int] = []
        self.checkpoints: dict[str, dict] = {}
        self._next_checkpoint = 0

        # build tables from hour-0 roster, seat the initial players (no routing)
        self.tables: dict[str, _Table] = {}
        for t in roster:
            tid = t["table_id"]
            self.tables[tid] = _Table(
                table_id=tid, max_seats=int(t["max_seats"]),
                style=t.get("style_volatility_label", "moderate"),
                trend=t.get("paid_seat_time_trend", "stable"),
                stakes=t.get("stakes", ""), game_type=t.get("game_type", ""),
                pace_label=t.get("pace_label", ""),
                rng=random.Random(derive_table_seed(master_seed, tid)),
            )
        for t in roster:
            tid = t["table_id"]
            for raw in t.get("seated_player_ids", []):
                if raw not in self.classifications:
                    continue
                pid = parse_player_id(raw)
                self._ensure_player(pid, self.classifications[raw])
                self._seat_at(pid, tid, sim_time=0.0, origin="initial")

    # --- player / seat bookkeeping ---------------------------------------

    def _ensure_player(self, pid: int, archetype: str) -> None:
        if pid in self.agents:
            return
        self.archetype_of[pid] = archetype
        self.knobs[pid] = knobs_for(archetype)
        self.agents[pid] = ArchetypeAgent(pid, self.knobs[pid], self.equity_samples)
        self.stacks[pid] = self.start
        self.net_bb[pid] = 0.0
        self.busts[pid] = 0
        self.seat_minutes[pid] = 0.0
        self.hands_played[pid] = 0
        self.left_at_minute[pid] = None
        # spread drawn ONCE at first appearance from a player-keyed seed (stable,
        # independent of seating order)
        sr = random.Random(derive_table_seed(self.master_seed, f"spread:{pid}"))
        self.spread[pid] = sr.uniform(0.85, 1.15)
        row = self.players_by_id.get(format_player_id(pid), {}) or {}
        self.cluster_of[pid] = row.get("cluster_id")

    def _seat_at(self, pid: int, table_id: str, sim_time: float, origin: str) -> None:
        tbl = self.tables[table_id]
        tbl.seated.append(pid)
        self._presence[pid] = {
            "table_id": table_id, "start_min": round(sim_time, 2),
            "start_net": self.net_bb[pid], "start_hands": self.hands_played[pid],
        }
        self.seat_events.append({
            "min": round(sim_time, 2), "player_id": pid, "table_id": table_id,
            "event": "seat", "origin": origin,
        })

    def _close_presence(self, pid: int, sim_time: float, exit_reason: str) -> None:
        pr = self._presence.pop(pid, None)
        if pr is None:
            return
        self.sessions.append({
            "player_id": pid, "archetype": self.archetype_of[pid],
            "table_id": pr["table_id"], "start_min": pr["start_min"],
            "end_min": round(sim_time, 2),
            "duration_min": round(sim_time - pr["start_min"], 2),
            "hands": self.hands_played[pid] - pr["start_hands"],
            "net_bb": round(self.net_bb[pid] - pr["start_net"], 2),
            "exit_reason": exit_reason,
        })

    def _remove_from_table(self, pid: int, tbl: _Table) -> None:
        if pid in tbl.seated:
            tbl.seated.remove(pid)

    def _depart(self, pid: int, tbl: _Table, sim_time: float, reason: str) -> None:
        """Terminal departure for the run (tilt/voluntary)."""
        self._remove_from_table(pid, tbl)
        if self.left_at_minute[pid] is None:
            self.left_at_minute[pid] = round(self.seat_minutes[pid], 1)
        self._close_presence(pid, sim_time, exit_reason=reason)
        self.departed.add(pid)
        self.seat_events.append({
            "min": round(sim_time, 2), "player_id": pid, "table_id": tbl.table_id,
            "event": "leave", "reason": reason,
        })

    # --- routing ----------------------------------------------------------

    def _live_tables(self) -> list[dict]:
        from .policies import Seeker  # noqa: F401 (kept local; no backend import here)
        return [
            make_table_dict(
                tid, list(t.seated), t.max_seats,
                style_volatility_label=t.style, paid_seat_time_trend=t.trend,
                stakes=t.stakes, game_type=t.game_type, pace_label=t.pace_label,
            )
            for tid, t in sorted(self.tables.items())
        ]

    def _route_seeker(self, pid: int, archetype: str, sim_time: float, origin: str) -> None:
        from .policies import Seeker
        decision = self.policy.choose(Seeker(pid, archetype), self._live_tables())
        self.routing_decisions.append({
            "min": round(sim_time, 2), "player_id": pid, "archetype": archetype,
            "origin": origin, "policy": getattr(self.policy, "name", "?"),
            "table_id": decision.table_id, "reason": decision.reason,
            "deferred": decision.deferred,
        })
        if decision.seated:
            self._seat_at(pid, decision.table_id, sim_time, origin=origin)
            return
        # not seated -> terminal (arrive once / re-seek once)
        if self.left_at_minute[pid] is None:
            self.left_at_minute[pid] = round(self.seat_minutes[pid], 1)
        self.departed.add(pid)
        if decision.deferred:
            self.deferred.append(pid)
        else:
            self.balked.append(pid)

    def _seat_arrivals(self, sim_time: float, _idx: list[int]) -> None:
        intents = self.arrival_intents
        while _idx[0] < len(intents) and intents[_idx[0]].arrive_at_min <= sim_time:
            it = intents[_idx[0]]
            _idx[0] += 1
            if it.player_id in self.departed or it.player_id in self.agents:
                continue  # arrive once; never re-add an already-known player
            self._ensure_player(it.player_id, it.archetype)
            self._route_seeker(it.player_id, it.archetype, sim_time, origin="arrival")

    # --- dealing / departures / breaks -----------------------------------

    def _table_members(self, seated: list[int]) -> dict[int, frozenset[int]]:
        by_cluster: dict[str, list[int]] = {}
        for pid in seated:
            cid = self.cluster_of.get(pid)
            if cid:
                by_cluster.setdefault(cid, []).append(pid)
        out: dict[int, frozenset[int]] = {}
        for members in by_cluster.values():
            s = frozenset(members)
            for pid in members:
                out[pid] = s - {pid}
        return out

    def _deal_one_hand(self, tbl: _Table) -> None:
        seated = tbl.seated
        m = len(seated)
        h = tbl.hands_dealt
        dealer = h % m
        order = [seated[(dealer + i) % m] for i in range(m)]
        seat_agents = [self.agents[pid] for pid in order]
        seat_stacks = [self.stacks[pid] for pid in order]
        members = self._table_members(seated)          # table-scoped, recomputed
        weak_ids = frozenset(pid for pid in seated if self.archetype_of[pid] in WEAK)
        rec = play_hand(seat_agents, order, seat_stacks, self.sb, self.bb,
                        tbl.rng, h, members, weak_ids)
        apply_hand_accounting(
            rec, order, stacks=self.stacks, net_session=self.net_bb, busts=self.busts,
            seat_minutes=self.seat_minutes, hands_played=self.hands_played,
            knobs=self.knobs, bb=self.bb, start=self.start,
            min_per_hand=self.min_per_hand, rebuy_threshold_bb=self.rebuy_threshold_bb,
            skill_edge=self.skill_edge, persist_stacks=True,
        )
        tbl.hands_dealt += 1
        self.hands_total += 1

    def _check_departures(self, tbl: _Table, sim_time: float) -> None:
        leavers: list[int] = []
        for pid in list(tbl.seated):
            if self.archetype_of[pid] not in COHORT:
                continue
            hp = self.hands_played[pid]
            loss100 = (-self.net_bb[pid]) / (hp / 100.0) if hp >= 15 else 0.0
            budget = _effective_session_min(
                session_min_for(self.archetype_of[pid]),
                self.knobs[pid].tilt_quit, loss100, self.spread[pid],
            )
            if self.seat_minutes[pid] >= budget:
                leavers.append(pid)
        for pid in leavers:
            self._depart(pid, tbl, sim_time, reason="tilt")

    def _handle_breaks(self, sim_time: float) -> None:
        for tid in sorted(self.tables):
            tbl = self.tables[tid]
            if 0 < len(tbl.seated) < 2:
                displaced = list(tbl.seated)
                for pid in displaced:
                    self._remove_from_table(pid, tbl)
                    self._close_presence(pid, sim_time, exit_reason="break")
                self.seat_events.append({
                    "min": round(sim_time, 2), "table_id": tid, "event": "break",
                })
                for pid in displaced:
                    # displaced players re-seek once via the active policy
                    self._route_seeker(pid, self.archetype_of[pid], sim_time,
                                       origin="break_displace")

    # --- checkpoints / run ------------------------------------------------

    def _maybe_checkpoint(self, sim_time: float) -> None:
        while (self._next_checkpoint < len(self.checkpoints_min)
               and sim_time >= self.checkpoints_min[self._next_checkpoint]):
            cp = self.checkpoints_min[self._next_checkpoint]
            self._next_checkpoint += 1
            seated_now = [pid for t in self.tables.values() for pid in t.seated]
            self.checkpoints[f"{int(cp)}min"] = {
                "min": cp,
                "active_players": len(seated_now),
                "active_tables": sum(1 for t in self.tables.values() if len(t.seated) >= 2),
                "cumulative_paid_seat_min": round(sum(self.seat_minutes.values()), 1),
                "cohort_paid_seat_min": round(
                    sum(self.seat_minutes[p] for p in self.seat_minutes
                        if self.archetype_of.get(p) in COHORT), 1),
                "hands_total": self.hands_total,
            }

    def run(self) -> RoomResult:
        max_steps = int(self.horizon_min / self.min_per_hand) + 2
        idx = [0]  # mutable arrival cursor
        for s in range(max_steps):
            sim_time = round(s * self.min_per_hand, 4)
            if sim_time > self.horizon_min:
                break
            self._seat_arrivals(sim_time, idx)
            self._maybe_checkpoint(sim_time)
            active = False
            for tid in sorted(self.tables):
                tbl = self.tables[tid]
                if len(tbl.seated) < 2:
                    continue
                active = True
                self._deal_one_hand(tbl)
                self._check_departures(tbl, sim_time)
            self._handle_breaks(sim_time)
            if not active and idx[0] >= len(self.arrival_intents):
                break

        # finalize still-seated presences at horizon
        end = self.horizon_min
        for tid in sorted(self.tables):
            for pid in list(self.tables[tid].seated):
                self._close_presence(pid, end, exit_reason="horizon")

        table_timelines = {
            tid: {"max_seats": t.max_seats, "style_volatility_label": t.style,
                  "paid_seat_time_trend": t.trend, "hands_dealt": t.hands_dealt,
                  "final_seated": list(t.seated)}
            for tid, t in sorted(self.tables.items())
        }
        return RoomResult(
            policy_name=getattr(self.policy, "name", "?"),
            master_seed=self.master_seed, horizon_min=self.horizon_min,
            hands_per_hour=self.hands_per_hour, min_per_hand=self.min_per_hand,
            starting_stack_bb=self.starting_stack_bb, skill_edge=self.skill_edge,
            equity_samples=self.equity_samples,
            arrival_intents=self.arrival_intents,
            routing_decisions=self.routing_decisions, seat_events=self.seat_events,
            sessions=self.sessions, table_timelines=table_timelines,
            checkpoints=self.checkpoints, hands_total=self.hands_total,
            archetype_of=dict(self.archetype_of), net_bb=dict(self.net_bb),
            seat_minutes={k: round(v, 1) for k, v in self.seat_minutes.items()},
            hands_played=dict(self.hands_played), busts=dict(self.busts),
            left_at_minute=dict(self.left_at_minute),
            balked=list(self.balked), deferred=list(self.deferred),
        )


def run_room(policy, **kwargs) -> RoomResult:
    """Convenience: build and run a room simulation, returning the causal trace."""
    return RoomSim(policy, **kwargs).run()
