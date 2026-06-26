"""GameSession — a series of hands with a human seat, driving bots automatically.

Holds persistent stacks across hands, rotates the button, and advances bot turns
until it's the human's turn (then pauses) or the hand ends. The server owns one
GameSession per game and pumps it via ``submit_human`` / ``next_hand``; the UI
renders ``state_view``.
"""
from __future__ import annotations

import random

from playsim.agent import Decision

from ..coach import coach_hand
from .game import HandSession
from .roster import known, make_agent, style_meta

HUMAN_ID = 0


class GameSession:
    def __init__(self, bot_style: str, starting_stack: int = 200, sb: int = 1, bb: int = 2,
                 seed: int | None = None, equity_samples: int = 30):
        if not known(bot_style):
            raise KeyError(f"unknown bot style {bot_style!r}")
        meta = style_meta(bot_style)
        self.bot_id = 1
        self.bot_style = bot_style
        self.bot_meta = meta
        self.player_ids = [HUMAN_ID, self.bot_id]      # heads-up MVP
        self.names = {HUMAN_ID: "You", self.bot_id: meta["name"]}
        self.agents = {self.bot_id: make_agent(bot_style, self.bot_id, equity_samples)}
        self.starting_stack = starting_stack
        self.sb, self.bb = sb, bb
        self._seed = seed
        self.rng = random.Random(seed)

        self.stacks = {pid: starting_stack for pid in self.player_ids}
        self.button = 0
        self.hand_no = 0
        self.hand: HandSession | None = None
        self._hand_finished = True
        self.last_result: dict | None = None
        self.payoffs: dict | None = None
        self._walk_count = 0
        self._walk_net = 0
        # session tracking / hand history
        self.history: list[dict] = []          # one entry per real (human-acted) hand
        self.last_coaching: dict | None = None
        self._last_narration: str | None = None
        self._net_chips_total = 0
        self._hands_real = self._walks_total = 0
        self._won = self._lost = self._tie = 0
        self._coach_samples = 120
        self._deal_until_playable()

    # -- hand lifecycle ---------------------------------------------------
    def _start_hand(self):
        order = self.player_ids[self.button:] + self.player_ids[:self.button]
        self.cur_seat_player_ids = order
        seat_stacks = [self.stacks[pid] for pid in order]
        self.hand = HandSession(order, seat_stacks, self.sb, self.bb, self.rng)
        self._hand_finished = False
        self.last_result = None
        self.payoffs = None
        self._auto_advance()

    def _deal_until_playable(self, max_walks: int = 100):
        """Deal hands until the human actually faces a decision, skipping *walks* —
        hands the bot ends before the human ever acts (it open-folds the small blind
        while the human is the big blind). Without this the player is dumped on a
        "you won, you did nothing" screen, which feels broken. The skipped walks are
        accumulated so the UI can report them ("bot folded N hands, +X bb")."""
        self._walk_count = 0
        self._walk_net = 0
        for _ in range(max_walks):
            self._start_hand()
            human_acted = any(ev.player_id == HUMAN_ID for ev in self.hand.events)
            playable = not (self.hand.done and self._hand_finished)
            if playable or human_acted:
                return                                  # the human has (or had) a turn
            self._walk_count += 1                        # a walk — count it and re-deal
            self._walk_net += (self.payoffs or {}).get(HUMAN_ID, 0)

    def _auto_advance(self):
        """Play bot turns until it's the human's turn or the hand ends."""
        while not self.hand.done:
            seat = self.hand.actor_seat()
            pid = self.cur_seat_player_ids[seat]
            if pid == HUMAN_ID:
                return                                  # pause for the human
            agent = self.agents[pid]
            self.hand.apply(agent.act(self.hand.observation(), self.rng))
        if not self._hand_finished:
            self._finish_hand()

    def _finish_hand(self):
        self._hand_finished = True
        self.payoffs = self.hand.payoffs()
        self.stacks = self.hand.stacks()                # final stacks = start + payoff
        reloaded = any(self.stacks[pid] <= 0 for pid in self.player_ids)
        if reloaded:
            self.stacks = {pid: self.starting_stack for pid in self.player_ids}
        net = self.payoffs.get(HUMAN_ID, 0)
        self._net_chips_total += net
        showdown = len(self.hand.showdown_seats()) > 1
        self.last_result = {
            "payoffs": self.payoffs,
            "net_you": net,
            "board": list(self.hand.board),
            "showdown": showdown,
            "reloaded": reloaded,
        }

        self._last_narration = None            # narration is recomputed per hand, on demand
        human_acted = any(ev.player_id == HUMAN_ID for ev in self.hand.events)
        if human_acted:
            # Compute coaching ONCE here (before hand_no advances) and cache it — it
            # powers the live review, the history replay, and the session EV stats.
            seed = (self._seed or 0) * 1_000_003 + self.hand_no
            self.last_coaching = coach_hand(self.hand, HUMAN_ID, self.sb, self.bb,
                                            seed=seed, samples=self._coach_samples)
            self._hands_real += 1
            outcome = "won" if net > 0 else ("lost" if net < 0 else "tie")
            self._won += outcome == "won"
            self._lost += outcome == "lost"
            self._tie += outcome == "tie"
            self.history.append({
                "hand_no": self.hand_no,
                "hole": self.last_coaching["hole"],
                "board": list(self.hand.board),
                "net_bb": net / self.bb,
                "outcome": outcome,
                "showdown": showdown,
                "coaching": self.last_coaching,
            })
        else:
            self.last_coaching = None
            self._walks_total += 1

        self.button = (self.button + 1) % len(self.player_ids)
        self.hand_no += 1

    # -- driven by the server ---------------------------------------------
    def _human_to_act(self) -> bool:
        if self.hand.done:
            return False
        seat = self.hand.actor_seat()
        return seat is not None and self.cur_seat_player_ids[seat] == HUMAN_ID

    def submit_human(self, decision: Decision):
        if not self._human_to_act():
            raise RuntimeError("not the human's turn")
        self.hand.apply(decision)
        self._auto_advance()

    def next_hand(self):
        if not (self.hand.done and self._hand_finished):
            raise RuntimeError("current hand is not over")
        self._deal_until_playable()

    def coaching(self) -> dict:
        """EV/equity coaching for the just-finished hand (computed once at finish)."""
        if not (self.hand.done and self._hand_finished):
            raise RuntimeError("hand is not over")
        if self.last_coaching is None:
            raise RuntimeError("no coaching for this hand")   # a walk — nothing to review
        return self.last_coaching

    def narration(self) -> str | None:
        """Lazy, cached LLM 'coach's take' for the just-finished hand (None if the
        narrator isn't configured or errors)."""
        if not (self.hand.done and self._hand_finished):
            raise RuntimeError("hand is not over")
        if self.last_coaching is None:
            raise RuntimeError("no coaching for this hand")
        if self._last_narration is None:
            from ..coach.narrator import narrate
            self._last_narration = narrate(self.last_coaching, self.bot_meta.get("name", ""))
        return self._last_narration

    def session_stats(self) -> dict:
        """Running scoreboard for the session (real hands; walks counted separately)."""
        played = self._hands_real
        net_bb = self._net_chips_total / self.bb
        ev_lost = sum(h["coaching"]["summary"]["ev_lost_bb"] for h in self.history)
        return {
            "hands_played": played,
            "walks_won": self._walks_total,
            "net_bb": round(net_bb, 1),
            "bb_per_100": round(net_bb / played * 100, 1) if played else 0.0,
            "won": self._won, "lost": self._lost, "tie": self._tie,
            "win_rate": round(self._won / played, 3) if played else 0.0,
            "ev_lost_bb": round(ev_lost, 1),
        }

    def history_view(self) -> dict:
        """Past real hands (newest first) + session stats, for the review panel."""
        return {"stats": self.session_stats(), "hands": list(reversed(self.history))}

    # -- view -------------------------------------------------------------
    def state_view(self) -> dict:
        hand = self.hand
        over = hand.done and self._hand_finished
        your_turn = self._human_to_act()
        in_hand_stacks = hand.stacks()
        showdown_seats = set(hand.showdown_seats())
        reveal_opp = over and len(showdown_seats) > 1

        # In heads-up the button is the small blind — the last seat in the order,
        # which posts the SB and acts first preflop.
        button_seat = len(self.cur_seat_player_ids) - 1

        seats = []
        for seat, pid in enumerate(self.cur_seat_player_ids):
            is_human = pid == HUMAN_ID
            show = is_human or (reveal_opp and seat in showdown_seats)
            seats.append({
                "seat": seat,
                "player_id": pid,
                "name": self.names[pid],
                "is_human": is_human,
                "stack": in_hand_stacks.get(pid, 0),
                "folded": seat in hand.folded,
                "is_button": seat == button_seat,
                "hole": list(hand.hole[seat]) if show else None,
                "to_act": (not over) and hand.actor_seat() == seat,
            })

        return {
            "hand_no": self.hand_no,
            "sb": self.sb, "bb": self.bb,
            "board": list(hand.board),
            "pot": hand.pot(),
            "seats": seats,
            "your_turn": your_turn,
            "legal": hand.legal() if your_turn else None,
            "log": [vars(ev) for ev in hand.events],
            "over": over,
            "result": self.last_result if over else None,
            "walks": ({"count": self._walk_count, "net_bb": self._walk_net / self.bb}
                      if self._walk_count else None),
            "stats": self.session_stats(),
            "bot": {
                "style": self.bot_style,
                "name": self.names[self.bot_id],
                "kind": self.bot_meta.get("kind", "heuristic"),
                "blurb": self.bot_meta.get("blurb", ""),
            },
        }
