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
from .behavior import DefaultBehaviorPolicy, LeaveContext, SeatOffer
from .knobs import knobs_for
from .population import (
    derive_table_seed,
    format_player_id,
    load_classifications,
    load_players_by_id,
    load_table_roster,
    parse_player_id,
)
from .router_adapter import make_table_dict
from .runner import (
    _COHORT as COHORT,
    _WEAK as WEAK,
    apply_hand_accounting,
)
from .table import play_hand


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
    ever_broken: bool = False

    @property
    def open_seats(self) -> int:
        return max(0, self.max_seats - len(self.seated))

    @property
    def state(self) -> str:
        if len(self.seated) >= 2:
            return "active"
        if len(self.seated) == 1:
            return "forming"
        return "broken_empty" if self.ever_broken else "empty"


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
    arrival_mode: str
    arrival_rate_per_hour: float | None
    formation_mode: str
    agent_model: str
    agent_version: str
    behavior_name: str
    behavior_params: dict
    instrumentation: dict
    arrival_intents: list[ArrivalIntent]
    routing_decisions: list[dict]
    seat_events: list[dict]
    sessions: list[dict]
    hourly: list[dict]
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
    declined: list[int]
    wait_balked: list[int]


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
        arrival_mode: str = "fixture-once",
        arrival_rate_per_hour: float | None = None,
        formation_mode: str = "none",
        debug_trace: bool = False,
        behavior=None,
    ) -> None:
        self.policy = policy
        self.behavior = behavior or DefaultBehaviorPolicy()
        self.debug_trace = debug_trace
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
        self.arrival_mode = arrival_mode
        self.arrival_rate_per_hour = arrival_rate_per_hour
        if formation_mode not in {"none", "forming"}:
            raise ValueError(f"unknown formation mode {formation_mode!r}")
        self.formation_mode = formation_mode
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
            else build_arrival_intents(
                horizon_min, seed=master_seed, root=root,
                mode=arrival_mode,
                arrival_rate_per_hour=arrival_rate_per_hour,
            )
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
        self.declined: list[int] = []
        self.wait_balked: list[int] = []
        self.pending_seek: list[dict] = []
        self.checkpoints: dict[str, dict] = {}
        self._next_checkpoint = 0
        self.hourly: list[dict] = []
        self._next_hour = 1
        self.instrumentation = {
            "routing_attempts": 0,
            "no_good_existing_seat_count": 0,
            "empty_table_available_count": 0,
            "sub_quorum_table_available_count": 0,
            "table_reactivation_count": 0,
            "forming_seat_count": 0,
            "formation_activation_count": 0,
        }

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

        # Mirror run_session's "need at least 2 players" guard: a room with no
        # tables or fewer than 2 simulatable players (initial seated + arrivals)
        # cannot produce a meaningful comparison — fail loudly rather than emit a
        # silently-empty "successful" room_sim.
        if not self.tables:
            raise ValueError("no tables matched the requested set")
        simulatable = ({pid for t in self.tables.values() for pid in t.seated}
                       | {a.player_id for a in self.arrival_intents})
        if len(simulatable) < 2:
            raise ValueError(
                "room needs at least 2 simulatable players "
                "(check --tables and classifications coverage)"
            )

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
        active_before = len(tbl.seated) >= 2
        tbl.seated.append(pid)
        active_after = len(tbl.seated) >= 2
        track_formation = origin != "initial"
        if track_formation and not active_after:
            self.instrumentation["forming_seat_count"] += 1
        if track_formation and not active_before and active_after:
            self.instrumentation["formation_activation_count"] += 1
        if track_formation and not active_before and active_after and tbl.ever_broken:
            self.instrumentation["table_reactivation_count"] += 1
        self._presence[pid] = {
            "table_id": table_id, "start_min": round(sim_time, 2),
            "start_net": self.net_bb[pid], "start_hands": self.hands_played[pid],
        }
        self.seat_events.append({
            "min": round(sim_time, 2), "player_id": pid, "table_id": table_id,
            "event": "seat", "origin": origin, "table_state_after": tbl.state,
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

    def _behavior_exit_action(self, reason: str, archetype: str) -> str:
        fn = getattr(self.behavior, "exit_action", None)
        if fn is not None:
            return fn(reason, archetype)
        if reason == "table_break" and self.behavior.reseek_on_break(archetype):
            return "reseek"
        return "terminal"

    def _wait_tolerance_min(self, reason: str, archetype: str) -> float:
        fn = getattr(self.behavior, "wait_tolerance_min", None)
        if fn is None:
            return 0.0
        return max(0.0, float(fn(reason, archetype)))

    def _queue_reseek(self, pid: int, archetype: str, sim_time: float, reason: str) -> bool:
        tolerance = self._wait_tolerance_min(reason, archetype)
        if tolerance <= 0:
            return False
        if any(p["player_id"] == pid for p in self.pending_seek):
            return True
        self.pending_seek.append({
            "player_id": pid,
            "archetype": archetype,
            "reason": reason,
            "queued_at_min": round(sim_time, 2),
            "next_try_min": round(sim_time + self.min_per_hand, 4),
            "expire_min": round(sim_time + tolerance, 4),
            "attempts": 0,
        })
        self.seat_events.append({
            "min": round(sim_time, 2),
            "player_id": pid,
            "event": "wait_start",
            "reason": reason,
            "wait_tolerance_min": round(tolerance, 2),
        })
        return True

    def _mark_unseated_terminal(self, pid: int, reason: str, *, deferred: bool = False,
                                declined: bool = False, waited: bool = False) -> None:
        if self.left_at_minute[pid] is None:
            self.left_at_minute[pid] = round(self.seat_minutes[pid], 1)
        self.departed.add(pid)
        if waited:
            self.wait_balked.append(pid)
        elif declined:
            self.declined.append(pid)
        elif deferred:
            self.deferred.append(pid)
        else:
            self.balked.append(pid)

    # --- routing ----------------------------------------------------------

    def _live_tables(self) -> list[dict]:
        return [
            make_table_dict(
                tid, list(t.seated), t.max_seats,
                style_volatility_label=t.style, paid_seat_time_trend=t.trend,
                stakes=t.stakes, game_type=t.game_type, pace_label=t.pace_label,
            )
            for tid, t in sorted(self.tables.items())
        ]

    def _formation_gap_snapshot(self) -> dict:
        """Passive instrumentation for the missing table-formation dynamic.

        "Good existing seat" is intentionally conservative here: an open seat at
        an already-dealable table (>=2 seated). It does not use backend health or
        fit scores, so the metric stays policy-independent and cheap.
        """
        open_tables = [t for t in self.tables.values() if t.open_seats > 0]
        active_open = [t for t in open_tables if len(t.seated) >= 2]
        empty_open = [t for t in open_tables if len(t.seated) == 0]
        sub_quorum_open = [t for t in open_tables if 0 < len(t.seated) < 2]
        snap = {
            "no_good_existing_seat": not active_open,
            "empty_table_available": bool(empty_open),
            "sub_quorum_table_available": bool(sub_quorum_open),
            "active_open_table_count": len(active_open),
            "empty_open_table_count": len(empty_open),
            "sub_quorum_open_table_count": len(sub_quorum_open),
        }
        self.instrumentation["routing_attempts"] += 1
        if snap["no_good_existing_seat"]:
            self.instrumentation["no_good_existing_seat_count"] += 1
        if snap["empty_table_available"]:
            self.instrumentation["empty_table_available_count"] += 1
        if snap["sub_quorum_table_available"]:
            self.instrumentation["sub_quorum_table_available_count"] += 1
        return snap

    def _route_seeker(self, pid: int, archetype: str, sim_time: float, origin: str,
                      require_pair: bool = False, queue_on_fail: bool = True,
                      exit_reason: str | None = None,
                      terminal_on_fail: bool = True) -> bool:
        from .policies import Seeker
        formation_gap = self._formation_gap_snapshot()
        decision = self.policy.choose(Seeker(pid, archetype), self._live_tables())
        table_id = decision.table_id
        reason = decision.reason
        # By default, break/table-thinning re-seek requires a currently dealable
        # partner. In formation mode, allow the player to seed an empty table;
        # no paid seat-time accrues until another player joins and the table
        # becomes active (>=2 seated).
        if (table_id is not None and require_pair
                and len(self.tables[table_id].seated) < 1):
            if self.formation_mode != "forming":
                table_id, reason = None, "no_dealable_seat"
        rec = {
            "min": round(sim_time, 2), "player_id": pid, "archetype": archetype,
            "origin": origin, "policy": getattr(self.policy, "name", "?"),
            "table_id": table_id, "reason": reason, "deferred": decision.deferred,
            "formation_gap": formation_gap,
        }
        # FairPlay rationale: for a backend-routed seat, record the chosen table's
        # rank breakdown so the trace answers "why this table?". Minimal by default;
        # the full ranked candidate list only under debug_trace. Standard/Random
        # carry no operator_view, so this is a no-op for them.
        ov = decision.meta.get("operator_view") if decision.meta else None
        if ov:
            if table_id is not None:
                chosen = next((e for e in ov if e["table_id"] == table_id), None)
                if chosen:
                    rec["rationale"] = {
                        "rank": chosen.get("rank"),
                        "health": chosen.get("health"),
                        "delta_health": chosen.get("delta_health"),
                        "seating_risk": chosen.get("seating_risk"),
                        "badge": chosen.get("badge"),
                        "integrity_gated": chosen.get("integrity_gated"),
                    }
            if self.debug_trace:
                rec["candidates"] = ov
        # the seeker may decline the offered seat. DefaultBehaviorPolicy always
        # accepts (forced placement → no behavior change); the fit-aware policy
        # (Phase 2) may decline on poor fit. Declines fold into balks for now.
        if table_id is not None:
            t = self.tables[table_id]
            offer = SeatOffer(
                archetype, table_id, rec.get("rationale"),
                table_archetypes=tuple(self.archetype_of[p] for p in t.seated),
                table_style=t.style, seated_count=len(t.seated), max_seats=t.max_seats,
            )
            if not self.behavior.accept_seat(offer):
                table_id = None
                rec["table_id"] = None
                rec["reason"] = "bad_fit_decline"
                rec["declined"] = True
        self.routing_decisions.append(rec)
        if table_id is not None:
            self._seat_at(pid, table_id, sim_time, origin=origin)
            return True
        fail_reason = (
            "bad_fit_decline" if rec.get("declined")
            else "table_break" if origin == "break_displace"
            else exit_reason or reason
        )
        if (
            queue_on_fail
            and self._behavior_exit_action(fail_reason, archetype) == "reseek"
            and self._queue_reseek(pid, archetype, sim_time, fail_reason)
        ):
            return False
        if not terminal_on_fail:
            return False
        # not seated and not waiting -> terminal for this run
        self._mark_unseated_terminal(
            pid,
            fail_reason,
            deferred=decision.deferred,
            declined=bool(rec.get("declined")),
        )
        return False

    def _process_pending_seekers(self, sim_time: float) -> None:
        if not self.pending_seek:
            return
        keep: list[dict] = []
        for pending in self.pending_seek:
            if pending["player_id"] in self.departed:
                continue
            if pending["next_try_min"] > sim_time:
                keep.append(pending)
                continue
            if sim_time > pending["expire_min"]:
                self._mark_unseated_terminal(
                    pending["player_id"], pending["reason"], waited=True,
                )
                self.seat_events.append({
                    "min": round(sim_time, 2),
                    "player_id": pending["player_id"],
                    "event": "wait_balk",
                    "reason": pending["reason"],
                    "attempts": pending["attempts"],
                })
                continue
            pending["attempts"] += 1
            seated = self._route_seeker(
                pending["player_id"],
                pending["archetype"],
                sim_time,
                origin=f"wait_{pending['reason']}",
                require_pair=pending["reason"] in {"table_break", "table_thinning"},
                queue_on_fail=False,
                exit_reason=pending["reason"],
                terminal_on_fail=False,
            )
            if not seated and pending["player_id"] not in self.departed:
                pending["next_try_min"] = round(sim_time + self.min_per_hand, 4)
                keep.append(pending)
        self.pending_seek = keep

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
        archs = tuple(self.archetype_of[p] for p in tbl.seated)
        seated_count = len(tbl.seated)
        leavers: list[tuple[int, str]] = []
        for pid in list(tbl.seated):
            leaving, reason = self.behavior.should_leave(LeaveContext(
                archetype=self.archetype_of[pid], seat_minutes=self.seat_minutes[pid],
                net_bb=self.net_bb[pid], hands_played=self.hands_played[pid],
                tilt_quit=self.knobs[pid].tilt_quit, spread=self.spread[pid],
                table_archetypes=archs, table_style=tbl.style,
                seated_count=seated_count, max_seats=tbl.max_seats,
            ))
            if leaving:
                leavers.append((pid, reason or "tilt"))
        for pid, reason in leavers:
            if self._behavior_exit_action(reason, self.archetype_of[pid]) == "reseek":
                self._remove_from_table(pid, tbl)
                self._close_presence(pid, sim_time, exit_reason=reason)
                self.seat_events.append({
                    "min": round(sim_time, 2), "player_id": pid, "table_id": tbl.table_id,
                    "event": "leave", "reason": reason,
                })
                self._route_seeker(
                    pid, self.archetype_of[pid], sim_time,
                    origin=reason, require_pair=True, exit_reason=reason,
                )
            else:
                self._depart(pid, tbl, sim_time, reason=reason)

    def _handle_breaks(self, sim_time: float) -> None:
        for tid in sorted(self.tables):
            tbl = self.tables[tid]
            if 0 < len(tbl.seated) < 2:
                if self.formation_mode == "forming":
                    continue
                displaced = list(tbl.seated)
                tbl.ever_broken = True
                for pid in displaced:
                    self._remove_from_table(pid, tbl)
                    self._close_presence(pid, sim_time, exit_reason="break")
                self.seat_events.append({
                    "min": round(sim_time, 2), "table_id": tid, "event": "break",
                })
                for pid in displaced:
                    if self._behavior_exit_action("table_break", self.archetype_of[pid]) == "reseek":
                        # displaced players re-seek once via the active policy
                        self._route_seeker(pid, self.archetype_of[pid], sim_time,
                                           origin="break_displace", require_pair=True,
                                           exit_reason="table_break")
                    else:
                        if self.left_at_minute[pid] is None:
                            self.left_at_minute[pid] = round(self.seat_minutes[pid], 1)
                        self.departed.add(pid)

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

    def _maybe_hourly(self, sim_time: float) -> None:
        """Time-resolved cumulative paid-seat-time rollup at each hour boundary —
        consistent with the seat_minutes north-star (not session wall-clock)."""
        while self._next_hour * 60.0 <= sim_time + 1e-9:
            hour = self._next_hour
            self._next_hour += 1
            seated_now = [pid for t in self.tables.values() for pid in t.seated]
            active_tables = sum(1 for t in self.tables.values() if len(t.seated) >= 2)
            cohort_seen = [p for p in self.archetype_of if self.archetype_of[p] in COHORT]
            cohort_active = [pid for pid in seated_now if self.archetype_of.get(pid) in COHORT]
            cohort_durs = [s["duration_min"] for s in self.sessions if s["archetype"] in COHORT]
            breaks_so_far = sum(1 for e in self.seat_events if e.get("event") == "break")
            self.hourly.append({
                "hour": hour,
                "cumulative_paid_seat_min": round(sum(self.seat_minutes.values()), 1),
                "cohort_paid_seat_min": round(
                    sum(self.seat_minutes[p] for p in self.seat_minutes
                        if self.archetype_of.get(p) in COHORT), 1),
                "active_players": len(seated_now),
                "active_tables": active_tables,
                "active_healthy_tables": active_tables,   # proxy: per-hour realized health not classified
                "cohort_retention_pct": round(100 * len(cohort_active) / max(len(cohort_seen), 1)),
                "avg_casual_session_min": round(sum(cohort_durs) / len(cohort_durs)) if cohort_durs else 0,
                "early_table_breaks": breaks_so_far,
                "high_risk_formations": self._seating_formations(),
                "hands_total": self.hands_total,
            })

    def _seating_formations(self) -> int:
        """Count seated cluster formations (>=2 members of one cluster co-seated).
        A composition proxy for 'high-risk seating formations' — no backend call."""
        total = 0
        for t in self.tables.values():
            by_cluster: dict[str, int] = {}
            for pid in t.seated:
                cid = self.cluster_of.get(pid)
                if cid:
                    by_cluster[cid] = by_cluster.get(cid, 0) + 1
            total += sum(1 for n in by_cluster.values() if n >= 2)
        return total

    def run(self) -> RoomResult:
        max_steps = int(self.horizon_min / self.min_per_hand) + 2
        idx = [0]  # mutable arrival cursor
        for s in range(max_steps):
            sim_time = round(s * self.min_per_hand, 4)
            if sim_time > self.horizon_min:
                break
            self._process_pending_seekers(sim_time)
            self._seat_arrivals(sim_time, idx)
            self._maybe_checkpoint(sim_time)
            self._maybe_hourly(sim_time)
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
                  "final_seated": list(t.seated), "final_state": t.state}
            for tid, t in sorted(self.tables.items())
        }
        return RoomResult(
            policy_name=getattr(self.policy, "name", "?"),
            master_seed=self.master_seed, horizon_min=self.horizon_min,
            hands_per_hour=self.hands_per_hour, min_per_hand=self.min_per_hand,
            starting_stack_bb=self.starting_stack_bb, skill_edge=self.skill_edge,
            equity_samples=self.equity_samples,
            arrival_mode=self.arrival_mode,
            arrival_rate_per_hour=self.arrival_rate_per_hour,
            formation_mode=self.formation_mode,
            agent_model=ArchetypeAgent.agent_model,
            agent_version=ArchetypeAgent.agent_version,
            behavior_name=getattr(self.behavior, "name", self.behavior.__class__.__name__),
            behavior_params={
                k: v for k, v in getattr(self.behavior, "__dict__", {}).items()
                if isinstance(v, (str, int, float, bool, type(None)))
            },
            instrumentation=dict(self.instrumentation),
            arrival_intents=self.arrival_intents,
            routing_decisions=self.routing_decisions, seat_events=self.seat_events,
            sessions=self.sessions, hourly=self.hourly, table_timelines=table_timelines,
            checkpoints=self.checkpoints, hands_total=self.hands_total,
            archetype_of=dict(self.archetype_of), net_bb=dict(self.net_bb),
            seat_minutes={k: round(v, 1) for k, v in self.seat_minutes.items()},
            hands_played=dict(self.hands_played), busts=dict(self.busts),
            left_at_minute=dict(self.left_at_minute),
            balked=list(self.balked), deferred=list(self.deferred),
            declined=list(self.declined), wait_balked=list(self.wait_balked),
        )


def run_room(policy, **kwargs) -> RoomResult:
    """Convenience: build and run a room simulation, returning the causal trace."""
    return RoomSim(policy, **kwargs).run()
