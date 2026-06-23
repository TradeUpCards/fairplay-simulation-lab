# Poker Outcome Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standalone, deterministic NL Hold'em simulator where each archetype is a skill-parameterized agent, producing hand histories + rolled-up per-player behavioral stats.

**Architecture:** A `sim/` package. A swappable `Engine` interface wraps PokerKit (the only module importing it); above the seam, archetype agents decide each action via tools + a strong/weak policy blend, consuming only a `DecisionContext`. A driver runs hands from a seeded deck, logs events, and rolls them into stats.

**Tech Stack:** Python 3, PokerKit (engine), treys (equity), pytest.

## Global Constraints

- **Additive only** — all new code under `sim/`; outputs to `data/sim/`; edit no existing files. (Sole prior change this branch: `.gitignore` += `.superpowers/`.)
- **Dependencies (sim/requirements.txt):** `pokerkit`, `treys`, `pytest`.
- **Cards are 2-char strings** `'<rank><suit>'` — rank in `23456789TJQKA`, suit in `shdc` (treys-compatible, e.g. `'Ah'`, `'Td'`, `'2c'`). One representation everywhere.
- **Determinism:** one master seed; independent RNG streams for *dealing* vs *decisions/equity*; same config+seed → byte-identical outputs; no unseeded randomness anywhere.
- **Engine seam:** only `sim/engine/pokerkit_engine.py` imports `pokerkit`; agents/tools consume `DecisionContext` only.
- **Commit policy (user override of "frequent commits"):** do NOT commit per task. Stage as you go; a single commit happens in Task 8 after the message is approved. No push.

---

### Task 1 (GATE): requirements + PokerKit spike

Validates the three assumptions A rests on: (1) we can inject every decision, (2) manual dealing lets us control the deck, (3) a fixed deal+line reproduces identical results. **If this task can't be made to pass, STOP and switch the engine to option B (treys + own betting loop) — the rest of the plan is unchanged above the seam.**

**Files:**
- Create: `sim/__init__.py` (empty), `sim/tests/__init__.py` (empty)
- Create: `sim/requirements.txt`
- Create: `sim/tests/test_pokerkit_spike.py`

**Interfaces:**
- Produces: confirmation of the exact PokerKit call names used by Task 5 (`NoLimitTexasHoldem.create_state`, `deal_hole`, `deal_board`, `fold`, `check_or_call`, `complete_bet_or_raise_to`, attrs `actor_index` / `status` / `stacks` / `bets` / `total_pot_amount` / `payoffs`).

- [ ] **Step 1: Create `sim/requirements.txt`**

```text
# Poker Outcome Simulator (sim/). Run: python -m sim.run --config sim/config/default.json
pokerkit>=0.5
treys>=0.1.8
pytest>=8.0
```

- [ ] **Step 2: Write the spike test**

Create `sim/tests/test_pokerkit_spike.py`:

```python
"""GATE: prove PokerKit supports decision injection + manual dealing + determinism.
If this can't pass, switch the engine to option B (see plan)."""
from pokerkit import Automation, NoLimitTexasHoldem


AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)  # NOTE: HOLE_DEALING / BOARD_DEALING intentionally absent — we deal manually.


def _new_state():
    # 3-handed, blinds 1/2, no ante, 200-chip stacks.
    return NoLimitTexasHoldem.create_state(
        AUTOMATIONS, True, 0, (1, 2), 2, (200, 200, 200), 3,
    )


def _play_fixed_hand():
    s = _new_state()
    # Manual hole dealing: 2 cards per player, fixed order.
    s.deal_hole("AhAs")   # player 0
    s.deal_hole("KdKc")   # player 1
    s.deal_hole("7h2d")   # player 2
    # Preflop betting: UTG (player 0 in 3-handed is the button/dealer order per PokerKit) — drive a line.
    while s.status and not s.board_cards:        # finish preflop street
        if s.actor_index is None:
            break
        s.check_or_call()
    # Deal a flop, then everyone checks down where possible.
    if s.status:
        s.deal_board("2s2hKs")
    while s.status:
        if s.actor_index is None:
            break
        s.check_or_call()
        if s.can_deal_board() if hasattr(s, "can_deal_board") else False:
            pass
    return s


def test_decisions_inject_and_chips_conserve():
    s = _play_fixed_hand()
    assert s.payoffs is not None
    assert sum(s.payoffs) == 0          # chips conserved


def test_deal_and_line_are_deterministic():
    a = _play_fixed_hand()
    b = _play_fixed_hand()
    assert tuple(a.payoffs) == tuple(b.payoffs)
```

- [ ] **Step 3: Run the spike**

Run: `python -m pytest sim/tests/test_pokerkit_spike.py -v`
Expected: PASS. If `check_or_call` / `deal_board` / street-detection differ from the docs, fix the spike to the real API and **record the working call names in a comment at the top of the file** — Task 5 copies them. If decision injection or manual dealing is impossible, STOP and switch to engine option B.

---

### Task 2: Seam types + seeded deck

**Files:**
- Create: `sim/engine/__init__.py` (empty)
- Create: `sim/engine/base.py`
- Create: `sim/deck.py`
- Create: `sim/tests/test_deck.py`

**Interfaces:**
- Produces: `Action(kind: str, amount: int = 0)` with `kind ∈ {"fold","check_call","raise_to"}`; `DecisionContext` (dataclass, fields below); `HandResult(payoffs: list[int], final_board: list[str], total_pot: int)`; `Engine` protocol. `deck.full_deck() -> list[str]`; `deck.shuffled(rng) -> list[str]`; `deck.derive(master: int, *parts: int) -> int`.

- [ ] **Step 1: Write `sim/engine/base.py`**

```python
"""Engine seam — shared types + the Engine protocol. No PokerKit knowledge here."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Action:
    kind: str            # "fold" | "check_call" | "raise_to"
    amount: int = 0      # total bet level for "raise_to"; ignored otherwise


@dataclass
class DecisionContext:
    seat: int
    hole: list[str]
    board: list[str]
    to_call: int
    pot: int
    stack: int
    big_blind: int
    position: str        # "early" | "middle" | "late" | "blind"
    n_opponents: int
    street: str          # "preflop" | "flop" | "turn" | "river"
    num_players: int


@dataclass
class HandResult:
    payoffs: list[int]           # net chips per seat (sums to 0)
    final_board: list[str]
    total_pot: int


class Engine(Protocol):
    def start_hand(self, *, deck: list[str], button: int,
                   blinds: tuple[int, int], starting_stacks: list[int]) -> None: ...
    def is_done(self) -> bool: ...
    def actor(self) -> int | None: ...
    def context(self) -> DecisionContext: ...
    def apply(self, action: Action) -> None: ...
    def result(self) -> HandResult: ...
```

- [ ] **Step 2: Write the failing deck test**

Create `sim/tests/test_deck.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import deck  # noqa: E402


def test_full_deck_is_52_unique():
    d = deck.full_deck()
    assert len(d) == 52 and len(set(d)) == 52


def test_shuffle_is_seed_deterministic():
    import random
    a = deck.shuffled(random.Random(7))
    b = deck.shuffled(random.Random(7))
    c = deck.shuffled(random.Random(8))
    assert a == b and a != c and sorted(a) == sorted(deck.full_deck())


def test_derive_is_stable_and_distinct():
    assert deck.derive(42, 1) == deck.derive(42, 1)
    assert deck.derive(42, 1) != deck.derive(42, 2)
```

- [ ] **Step 3: Run it (fails)**

Run: `python -m pytest sim/tests/test_deck.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.deck'`.

- [ ] **Step 4: Write `sim/deck.py`**

```python
"""Seeded deck — the determinism owner. Cards are 2-char strings 'Ah','Td', etc."""
from __future__ import annotations

import random

RANKS = "23456789TJQKA"
SUITS = "shdc"


def full_deck() -> list[str]:
    return [r + s for r in RANKS for s in SUITS]


def shuffled(rng: random.Random) -> list[str]:
    d = full_deck()
    rng.shuffle(d)
    return d


def derive(master: int, *parts: int) -> int:
    """Stable child seed from a master seed + integer parts (no global RNG)."""
    h = master
    for p in parts:
        h = (h * 1_000_003 + p + 1) & 0x7FFF_FFFF_FFFF_FFFF
    return h
```

- [ ] **Step 5: Run it (passes)**

Run: `python -m pytest sim/tests/test_deck.py -v`
Expected: PASS (3 tests).

---

### Task 3: Tools (pot odds, position, equity)

**Files:**
- Create: `sim/agents/__init__.py` (empty)
- Create: `sim/agents/tools.py`
- Create: `sim/tests/test_tools.py`

**Interfaces:**
- Consumes: `deck.full_deck`.
- Produces: `pot_odds(pot: int, to_call: int) -> float`; `position(seat: int, button: int, num_players: int) -> str`; `hand_equity(hole: list[str], board: list[str], n_opponents: int, rng: random.Random, samples: int = 200) -> float`.

- [ ] **Step 1: Write the failing test**

Create `sim/tests/test_tools.py`:

```python
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim.agents import tools  # noqa: E402


def test_pot_odds():
    assert tools.pot_odds(100, 0) == 0.0
    assert abs(tools.pot_odds(150, 50) - 0.25) < 1e-9


def test_equity_aces_dominate_preflop_heads_up():
    eq = tools.hand_equity(["Ah", "As"], [], n_opponents=1,
                           rng=random.Random(1), samples=400)
    assert eq > 0.80                    # AA vs one random ≈ 0.85


def test_equity_made_nuts_on_river_is_one():
    # Royal-ish lock: our hand makes the best possible vs the board.
    eq = tools.hand_equity(["Ah", "Kh"], ["Qh", "Jh", "Th", "2c", "3d"],
                           n_opponents=1, rng=random.Random(1), samples=200)
    assert eq == 1.0


def test_position_buckets():
    assert tools.position(seat=1, button=1, num_players=6) in {"late", "blind", "early", "middle"}
```

- [ ] **Step 2: Run it (fails)**

Run: `python -m pytest sim/tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.agents.tools'`.

- [ ] **Step 3: Write `sim/agents/tools.py`**

```python
"""Decision tools — pure reads over a DecisionContext snapshot. No engine."""
from __future__ import annotations

import random

from treys import Card, Evaluator

from sim import deck

_EV = Evaluator()


def pot_odds(pot: int, to_call: int) -> float:
    if to_call <= 0:
        return 0.0
    return to_call / (pot + to_call)


def position(seat: int, button: int, num_players: int) -> str:
    # Seats after the button act later; blinds are the two seats after the button.
    rel = (seat - button) % num_players
    if rel in (1, 2):
        return "blind"
    if rel <= num_players // 3:
        return "early"
    if rel <= 2 * num_players // 3:
        return "middle"
    return "late"


def _t(cards: list[str]) -> list[int]:
    return [Card.new(c) for c in cards]


def hand_equity(hole: list[str], board: list[str], n_opponents: int,
                rng: random.Random, samples: int = 200) -> float:
    """Monte-Carlo win probability. Deterministic given rng. Lower treys score = better."""
    known = set(hole) | set(board)
    live = [c for c in deck.full_deck() if c not in known]
    hole_t = _t(hole)
    wins = ties = 0
    for _ in range(samples):
        d = live[:]
        rng.shuffle(d)
        i = 0
        opp_holes = []
        for _ in range(n_opponents):
            opp_holes.append(d[i:i + 2])
            i += 2
        need = 5 - len(board)
        full_board = board + d[i:i + need]
        board_t = _t(full_board)
        mine = _EV.evaluate(board_t, hole_t)
        best_opp = min(_EV.evaluate(board_t, _t(o)) for o in opp_holes)
        if mine < best_opp:
            wins += 1
        elif mine == best_opp:
            ties += 1
    return (wins + 0.5 * ties) / samples
```

- [ ] **Step 4: Run it (passes)**

Run: `python -m pytest sim/tests/test_tools.py -v`
Expected: PASS (4 tests). If `test_equity_aces_dominate` is flaky at the boundary, raise `samples`.

---

### Task 4: Skill model (archetypes + policy + agent)

**Files:**
- Create: `sim/agents/archetype.py`
- Create: `sim/agents/policy.py`
- Create: `sim/tests/test_policy.py`

**Interfaces:**
- Consumes: `Action`, `DecisionContext` (base.py); `tools`.
- Produces: `Archetype(name, skill, aggression, tightness, bluff_freq)`; `ARCHETYPES: dict[str, Archetype]`; `Agent(archetype)` with `decide(ctx: DecisionContext, rng: random.Random) -> Action`; `strong_policy(ctx, equity) -> Action`; `beginner_policy(ctx, equity) -> Action`.

- [ ] **Step 1: Write the failing test**

Create `sim/tests/test_policy.py`:

```python
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim.engine.base import DecisionContext  # noqa: E402
from sim.agents import policy  # noqa: E402
from sim.agents.archetype import Agent, ARCHETYPES  # noqa: E402


def _ctx(to_call=10, pot=30, stack=200):
    return DecisionContext(seat=0, hole=["Ah", "Ks"], board=["Kd", "7c", "2h"],
                           to_call=to_call, pot=pot, stack=stack, big_blind=2,
                           position="late", n_opponents=1, street="flop", num_players=6)


def test_strong_folds_when_behind_facing_bet():
    assert policy.strong_policy(_ctx(), equity=0.10).kind == "fold"


def test_strong_raises_when_far_ahead():
    assert policy.strong_policy(_ctx(), equity=0.90).kind == "raise_to"


def test_beginner_calls_too_light():
    # equity below pot odds (0.25) but a beginner still calls.
    assert policy.beginner_policy(_ctx(to_call=10, pot=30), equity=0.30).kind == "check_call"


def test_higher_skill_folds_marginal_spots_more_than_beginner():
    # Mediocre hand facing a pot-sized bet (odds 0.5): the strong line folds,
    # the beginner line calls too light. Style noise removed (aggression/bluff = 0).
    marginal = DecisionContext(seat=0, hole=["9h", "8c"], board=["Kd", "7s", "2h"],
                               to_call=30, pot=30, stack=200, big_blind=2,
                               position="late", n_opponents=1, street="flop", num_players=6)
    strong = Agent(ARCHETYPES["grinder"]._replace(skill=1.0, aggression=0.0, bluff_freq=0.0))
    weak = Agent(ARCHETYPES["grinder"]._replace(skill=0.0, aggression=0.0, bluff_freq=0.0))
    strong_folds = sum(strong.decide(marginal, random.Random(i)).kind == "fold" for i in range(30))
    weak_folds = sum(weak.decide(marginal, random.Random(i)).kind == "fold" for i in range(30))
    assert strong_folds > weak_folds
```

- [ ] **Step 2: Run it (fails)**

Run: `python -m pytest sim/tests/test_policy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.agents.policy'`.

- [ ] **Step 3: Write `sim/agents/archetype.py`**

```python
"""Archetype = skill% + style knobs. The 7 behavioral archetypes (v1)."""
from __future__ import annotations

import random
from typing import NamedTuple

from sim.agents import policy, tools
from sim.engine.base import Action, DecisionContext


class Archetype(NamedTuple):
    name: str
    skill: float        # 0..1, probability of playing the strong line
    aggression: float   # 0..1, shifts calls/checks toward raises
    tightness: float    # 0..1, preflop range narrowness
    bluff_freq: float   # 0..1, raise frequency with low equity


ARCHETYPES: dict[str, Archetype] = {
    "new":                  Archetype("new", 0.10, 0.30, 0.30, 0.05),
    "recreational":         Archetype("recreational", 0.35, 0.25, 0.20, 0.05),
    "regular":              Archetype("regular", 0.60, 0.50, 0.55, 0.10),
    "grinder":              Archetype("grinder", 0.85, 0.65, 0.80, 0.12),
    "aggressive_predatory": Archetype("aggressive_predatory", 0.90, 0.90, 0.45, 0.30),
    "healthy_anchor":       Archetype("healthy_anchor", 0.75, 0.55, 0.65, 0.10),
    "promo_hunter":         Archetype("promo_hunter", 0.30, 0.20, 0.90, 0.03),
}


class Agent:
    def __init__(self, archetype: Archetype):
        self.arch = archetype

    def decide(self, ctx: DecisionContext, rng: random.Random) -> Action:
        equity = tools.hand_equity(ctx.hole, ctx.board, ctx.n_opponents,
                                   rng, samples=120)
        base = (policy.strong_policy(ctx, equity)
                if rng.random() < self.arch.skill
                else policy.beginner_policy(ctx, equity))
        return policy.apply_style(base, ctx, equity, self.arch, rng)
```

- [ ] **Step 4: Write `sim/agents/policy.py`**

```python
"""Reference policies + style overlay. Pure functions over a DecisionContext."""
from __future__ import annotations

import random

from sim.agents import tools
from sim.engine.base import Action, DecisionContext

_PREFLOP_PLAY_EQUITY = 0.45   # baseline 'is this hand worth playing' bar (style-adjusted)


def _raise_to(ctx: DecisionContext, pot_fraction: float) -> Action:
    target = ctx.to_call + int((ctx.pot + ctx.to_call) * pot_fraction)
    target = max(target, ctx.to_call + ctx.big_blind)        # at least a min-ish raise
    target = min(target, ctx.stack)                          # cap at all-in
    return Action("raise_to", target)


def strong_policy(ctx: DecisionContext, equity: float) -> Action:
    odds = tools.pot_odds(ctx.pot, ctx.to_call)
    if ctx.to_call == 0:
        return _raise_to(ctx, 0.66) if equity > 0.60 else Action("check_call")
    if equity > odds + 0.15:
        return _raise_to(ctx, 0.75)
    if equity >= odds:
        return Action("check_call")
    return Action("fold")


def beginner_policy(ctx: DecisionContext, equity: float) -> Action:
    # Plays absolute strength: bets big hands, calls far too light, rarely folds.
    if ctx.to_call == 0:
        return _raise_to(ctx, 0.5) if equity > 0.50 else Action("check_call")
    if equity > 0.22:                       # calling station — ignores pot odds
        return Action("check_call")
    return Action("fold")


def apply_style(base: Action, ctx: DecisionContext, equity: float,
                arch, rng: random.Random) -> Action:
    # Aggression: sometimes upgrade a call/check into a raise.
    if base.kind == "check_call" and rng.random() < arch.aggression * 0.5:
        return _raise_to(ctx, 0.5 + 0.3 * arch.aggression)
    # Bluff: occasionally raise with weak equity.
    if base.kind == "fold" and rng.random() < arch.bluff_freq and equity < 0.30:
        return _raise_to(ctx, 0.5)
    # Tightness: a fold stays a fold; looseness turns marginal folds into calls preflop.
    if base.kind == "fold" and ctx.street == "preflop" and rng.random() > arch.tightness:
        return Action("check_call")
    return base
```

- [ ] **Step 5: Run it (passes)**

Run: `python -m pytest sim/tests/test_policy.py -v`
Expected: PASS (4 tests).

---

### Task 5: PokerKit engine adapter

**Files:**
- Create: `sim/engine/pokerkit_engine.py`
- Create: `sim/tests/test_pokerkit_engine.py`

**Interfaces:**
- Consumes: `Engine`, `Action`, `DecisionContext`, `HandResult` (base.py); the PokerKit call names confirmed in Task 1.
- Produces: `PokerKitEngine()` implementing `Engine`.

- [ ] **Step 1: Write the failing test**

Create `sim/tests/test_pokerkit_engine.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim.engine.base import Action  # noqa: E402
from sim.engine.pokerkit_engine import PokerKitEngine  # noqa: E402
from sim import deck  # noqa: E402


def _run_all_fold_to_one(seed_deck):
    eng = PokerKitEngine()
    eng.start_hand(deck=seed_deck, button=0, blinds=(1, 2),
                   starting_stacks=[200, 200, 200])
    guard = 0
    while not eng.is_done() and guard < 500:
        guard += 1
        if eng.actor() is None:
            break
        ctx = eng.context()
        # Everyone folds when facing a bet; the BB wins the blinds.
        eng.apply(Action("fold") if ctx.to_call > 0 else Action("check_call"))
    return eng


def test_hand_completes_and_conserves_chips():
    d = deck.full_deck()           # fixed order = deterministic
    eng = _run_all_fold_to_one(d)
    res = eng.result()
    assert eng.is_done()
    assert sum(res.payoffs) == 0
    assert len(res.payoffs) == 3


def test_same_deck_same_payoffs():
    d = deck.full_deck()
    a = _run_all_fold_to_one(d).result()
    b = _run_all_fold_to_one(d).result()
    assert a.payoffs == b.payoffs
```

- [ ] **Step 2: Run it (fails)**

Run: `python -m pytest sim/tests/test_pokerkit_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.engine.pokerkit_engine'`.

- [ ] **Step 3: Write `sim/engine/pokerkit_engine.py`**

> Use the exact call names confirmed by the Task 1 spike. The structure below matches the documented API; adjust method names only where the spike recorded a difference.

```python
"""The ONLY module that imports pokerkit. Adapts it to the Engine seam."""
from __future__ import annotations

from pokerkit import Automation, NoLimitTexasHoldem

from sim.engine.base import Action, DecisionContext, HandResult

_AUTO = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)
_STREET = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}


class PokerKitEngine:
    def __init__(self) -> None:
        self._s = None
        self._deck: list[str] = []
        self._i = 0
        self._n = 0
        self._button = 0
        self._bb = 0
        self._hole: list[list[str]] = []

    def start_hand(self, *, deck, button, blinds, starting_stacks) -> None:
        self._deck, self._i = list(deck), 0
        self._n = len(starting_stacks)
        self._button, self._bb = button, blinds[1]
        self._s = NoLimitTexasHoldem.create_state(
            _AUTO, True, 0, blinds, blinds[1], tuple(starting_stacks), self._n)
        # Manual hole dealing: 2 cards per player, in seat order.
        self._hole = []
        for _ in range(self._n):
            two = self._deck[self._i:self._i + 2]
            self._i += 2
            self._hole.append(two)
            self._s.deal_hole("".join(two))
        self._deal_board_if_needed()

    def _draw(self, k: int) -> str:
        cards = self._deck[self._i:self._i + k]
        self._i += k
        return "".join(cards)

    def _deal_board_if_needed(self) -> None:
        # When the engine is awaiting community cards, supply them from our deck.
        while self._s.status and self._s.actor_index is None and self._s.can_deal_board():
            need = self._s.street.board_dealing_count if self._s.street else 0
            self._s.deal_board(self._draw(need or 1))

    def is_done(self) -> bool:
        return not self._s.status

    def actor(self) -> int | None:
        self._deal_board_if_needed()
        return self._s.actor_index

    def context(self) -> DecisionContext:
        s = self._s
        a = s.actor_index
        to_call = max(s.bets) - s.bets[a]
        return DecisionContext(
            seat=a, hole=self._hole[a], board=list(s.board_cards),
            to_call=to_call, pot=s.total_pot_amount, stack=s.stacks[a],
            big_blind=self._bb, num_players=self._n,
            n_opponents=sum(1 for x in s.statuses if x) - 1,
            position=self._position(a),
            street=_STREET.get(len(s.board_cards), "river"))

    def _position(self, seat: int) -> str:
        rel = (seat - self._button) % self._n
        if rel in (1, 2):
            return "blind"
        if rel <= self._n // 3:
            return "early"
        if rel <= 2 * self._n // 3:
            return "middle"
        return "late"

    def apply(self, action: Action) -> None:
        s = self._s
        if action.kind == "fold":
            s.fold()
        elif action.kind == "check_call":
            s.check_or_call()
        else:  # raise_to, clamped to legal
            a = s.actor_index
            to_call = max(s.bets) - s.bets[a]
            amt = action.amount
            if not s.can_complete_bet_or_raise_to(amt):
                # Clamp: try min-raise, else just call/check.
                lo = s.min_completion_betting_or_raising_to_amount
                if lo is not None and s.can_complete_bet_or_raise_to(lo):
                    amt = lo
                else:
                    s.check_or_call()
                    self._deal_board_if_needed()
                    return
            s.complete_bet_or_raise_to(amt)
        self._deal_board_if_needed()

    def result(self) -> HandResult:
        s = self._s
        return HandResult(payoffs=list(s.payoffs),
                          final_board=list(s.board_cards),
                          total_pot=sum(s.pot_amounts))
```

- [ ] **Step 4: Run it (passes)**

Run: `python -m pytest sim/tests/test_pokerkit_engine.py -v`
Expected: PASS (2 tests). If a method/attribute name differs from the spike, fix it here only.

---

### Task 6: Log + stats rollup

**Files:**
- Create: `sim/log.py`
- Create: `sim/stats.py`
- Create: `sim/tests/test_stats.py`

**Interfaces:**
- Consumes: `Action`, `DecisionContext`, `HandResult`.
- Produces: `EventLog` with `.record_action(hand_id, table_id, player_id, ctx, action)`, `.record_result(hand_id, table_id, seats, result)`, `.events: list[dict]`, `.results: list[dict]`; `stats.rollup(events, results) -> dict[str, dict]` keyed by player_id with `vpip, pfr, aggression_factor, avg_pot_size_bb, lifetime_hands, net_chips`.

> **Deferred fields (spec §9):** `net_chips` is the v1 profitability signal. The spec's `win_rate (bb/100)` is a trivial later transform of `net_chips` + `lifetime_hands` + the blind, and the time fields (`avg_session_minutes`, `sessions_last_30d`) need a hands→time model — both belong to the deferred Contract-1 **schema-mapping phase**, not this standalone deliverable. The skill→win-rate relationship is eyeballed in the Task 8 manual run (variance over a modest sample makes it a poor automated gate).

- [ ] **Step 1: Write the failing test**

Create `sim/tests/test_stats.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import stats  # noqa: E402


def test_rollup_computes_vpip_pfr_aggression():
    # Player P1: 2 hands. Hand1 preflop raise (voluntary, pfr). Hand2 preflop fold.
    # Postflop in hand1: one bet, one call → AF = bets/calls = 1/1 = 1.0.
    events = [
        {"hand_id": "H1", "player_id": "P1", "street": "preflop", "kind": "raise_to", "voluntary": True, "is_raise": True},
        {"hand_id": "H1", "player_id": "P1", "street": "flop", "kind": "raise_to", "voluntary": True, "is_raise": True},
        {"hand_id": "H1", "player_id": "P1", "street": "turn", "kind": "check_call", "voluntary": True, "is_raise": False},
        {"hand_id": "H2", "player_id": "P1", "street": "preflop", "kind": "fold", "voluntary": False, "is_raise": False},
    ]
    results = [
        {"hand_id": "H1", "player_id": "P1", "net": 50, "pot_bb": 20.0, "dealt_in": True},
        {"hand_id": "H2", "player_id": "P1", "net": -2, "pot_bb": 3.0, "dealt_in": True},
    ]
    out = stats.rollup(events, results)["P1"]
    assert out["lifetime_hands"] == 2
    assert abs(out["vpip"] - 0.5) < 1e-9          # voluntary in 1 of 2 hands
    assert abs(out["pfr"] - 0.5) < 1e-9           # preflop raise in 1 of 2 hands
    assert abs(out["aggression_factor"] - 1.0) < 1e-9   # 1 postflop raise / 1 postflop call
    assert out["net_chips"] == 48
```

- [ ] **Step 2: Run it (fails)**

Run: `python -m pytest sim/tests/test_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.stats'`.

- [ ] **Step 3: Write `sim/log.py`**

```python
"""Hand-history event log. Captures exactly what the stat rollup needs."""
from __future__ import annotations

from sim.engine.base import Action, DecisionContext, HandResult


class EventLog:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.results: list[dict] = []

    def record_action(self, hand_id, table_id, player_id,
                      ctx: DecisionContext, action: Action) -> None:
        voluntary = action.kind != "fold" and not (
            ctx.street == "preflop" and action.kind == "check_call" and ctx.to_call == 0)
        self.events.append({
            "hand_id": hand_id, "table_id": table_id, "player_id": player_id,
            "street": ctx.street, "kind": action.kind,
            "voluntary": voluntary, "is_raise": action.kind == "raise_to",
        })

    def record_result(self, hand_id, table_id, seats, result: HandResult, big_blind: int) -> None:
        pot_bb = result.total_pot / big_blind if big_blind else 0.0
        for seat, player_id in enumerate(seats):
            self.results.append({
                "hand_id": hand_id, "table_id": table_id, "player_id": player_id,
                "net": result.payoffs[seat], "pot_bb": round(pot_bb, 2), "dealt_in": True,
            })
```

- [ ] **Step 4: Write `sim/stats.py`**

```python
"""Pure rollup of the event log into per-player behavioral features."""
from __future__ import annotations

from collections import defaultdict


def rollup(events: list[dict], results: list[dict]) -> dict[str, dict]:
    hands = defaultdict(set)                 # player -> {hand_id} dealt in
    vpip_hands = defaultdict(set)
    pfr_hands = defaultdict(set)
    postflop_raises = defaultdict(int)
    postflop_calls = defaultdict(int)
    net = defaultdict(int)
    pots = defaultdict(list)

    for r in results:
        if r.get("dealt_in"):
            hands[r["player_id"]].add(r["hand_id"])
            net[r["player_id"]] += r["net"]
            pots[r["player_id"]].append(r["pot_bb"])

    for e in events:
        p = e["player_id"]
        if e["voluntary"]:
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
        out[p] = {
            "lifetime_hands": n,
            "vpip": round(len(vpip_hands[p]) / n, 3) if n else 0.0,
            "pfr": round(len(pfr_hands[p]) / n, 3) if n else 0.0,
            "aggression_factor": round(postflop_raises[p] / calls, 3) if calls else float(postflop_raises[p]),
            "avg_pot_size_bb": round(sum(pots[p]) / len(pots[p]), 2) if pots[p] else 0.0,
            "net_chips": net[p],
        }
    return out
```

- [ ] **Step 5: Run it (passes)**

Run: `python -m pytest sim/tests/test_stats.py -v`
Expected: PASS.

---

### Task 7: Driver (the loop)

**Files:**
- Create: `sim/driver.py`
- Create: `sim/tests/test_driver.py`

**Interfaces:**
- Consumes: `Engine` (via `PokerKitEngine`), `Agent`, `deck`, `EventLog`.
- Produces: `run_table(*, table_id, engine, agents, player_ids, blinds, starting_stack, hands, table_seed, log) -> None`. (`agents`/`player_ids` are per-seat lists; `engine` is any `Engine`.)

- [ ] **Step 1: Write the failing test**

Create `sim/tests/test_driver.py`:

```python
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim.driver import run_table  # noqa: E402
from sim.engine.pokerkit_engine import PokerKitEngine  # noqa: E402
from sim.agents.archetype import Agent, ARCHETYPES  # noqa: E402
from sim.log import EventLog  # noqa: E402


def _agents():
    names = ["grinder", "recreational", "aggressive_predatory"]
    return [Agent(ARCHETYPES[n]) for n in names]


def _run(seed):
    log = EventLog()
    run_table(table_id="T1", engine=PokerKitEngine(), agents=_agents(),
              player_ids=["P1", "P2", "P3"], blinds=(1, 2), starting_stack=200,
              hands=12, table_seed=seed, log=log)
    return log


def test_run_produces_results_for_all_hands():
    log = _run(42)
    assert len({r["hand_id"] for r in log.results}) == 12
    # Chips conserved per hand.
    by_hand = {}
    for r in log.results:
        by_hand.setdefault(r["hand_id"], 0)
        by_hand[r["hand_id"]] += r["net"]
    assert all(v == 0 for v in by_hand.values())


def test_run_is_deterministic():
    a, b = _run(42), _run(42)
    assert a.events == b.events and a.results == b.results
```

- [ ] **Step 2: Run it (fails)**

Run: `python -m pytest sim/tests/test_driver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.driver'`.

- [ ] **Step 3: Write `sim/driver.py`**

```python
"""Drives hands at a table: seeded deck per hand, button rotation, reload-to-stack."""
from __future__ import annotations

import random

from sim import deck
from sim.log import EventLog


def run_table(*, table_id, engine, agents, player_ids, blinds,
              starting_stack, hands, table_seed, log: EventLog) -> None:
    n = len(agents)
    deal_rng = random.Random(deck.derive(table_seed, 1))
    decision_rng = random.Random(deck.derive(table_seed, 2))
    bb = blinds[1]

    for h in range(hands):
        button = h % n
        d = deck.shuffled(deal_rng)
        stacks = [starting_stack] * n          # cash game: reload each hand
        engine.start_hand(deck=d, button=button, blinds=blinds, starting_stacks=stacks)
        hand_id = f"{table_id}-H{h:04d}"

        guard = 0
        while not engine.is_done() and guard < 1000:
            guard += 1
            if engine.actor() is None:
                break
            ctx = engine.context()
            action = agents[ctx.seat].decide(ctx, decision_rng)
            log.record_action(hand_id, table_id, player_ids[ctx.seat], ctx, action)
            engine.apply(action)

        log.record_result(hand_id, table_id, player_ids, engine.result(), bb)
```

- [ ] **Step 4: Run it (passes)**

Run: `python -m pytest sim/tests/test_driver.py -v`
Expected: PASS (2 tests).

---

### Task 8: Entrypoint, config, calibration + the single commit

**Files:**
- Create: `sim/run.py`
- Create: `sim/config/default.json`
- Create: `sim/tests/test_run_and_calibration.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `python -m sim.run --config <path>` writing `data/sim/hand_histories.json` + `data/sim/player_stats.json`; `sim.run.simulate(config: dict) -> tuple[list, list, dict]` returning `(events, results, player_stats)`.

- [ ] **Step 1: Write `sim/config/default.json`**

```json
{
  "master_seed": 42,
  "equity_samples": 120,
  "blinds": [1, 2],
  "starting_stack": 200,
  "hands_per_table": 300,
  "tables": [
    {"table_id": "T1", "seats": [
      {"player_id": "SIM-001", "archetype": "grinder"},
      {"player_id": "SIM-002", "archetype": "recreational"},
      {"player_id": "SIM-003", "archetype": "aggressive_predatory"},
      {"player_id": "SIM-004", "archetype": "new"},
      {"player_id": "SIM-005", "archetype": "regular"},
      {"player_id": "SIM-006", "archetype": "healthy_anchor"}
    ]},
    {"table_id": "T2", "seats": [
      {"player_id": "SIM-007", "archetype": "regular"},
      {"player_id": "SIM-008", "archetype": "promo_hunter"},
      {"player_id": "SIM-009", "archetype": "recreational"},
      {"player_id": "SIM-010", "archetype": "grinder"},
      {"player_id": "SIM-011", "archetype": "healthy_anchor"},
      {"player_id": "SIM-012", "archetype": "aggressive_predatory"}
    ]}
  ]
}
```

- [ ] **Step 2: Write `sim/run.py`**

```python
"""Entrypoint: config -> run all tables -> write hand histories + player stats."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sim import deck, stats
from sim.agents.archetype import Agent, ARCHETYPES
from sim.engine.pokerkit_engine import PokerKitEngine
from sim.driver import run_table
from sim.log import EventLog

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "sim"


def simulate(config: dict):
    log = EventLog()
    blinds = tuple(config["blinds"])
    for idx, table in enumerate(config["tables"]):
        seats = table["seats"]
        agents = [Agent(ARCHETYPES[s["archetype"]]) for s in seats]
        player_ids = [s["player_id"] for s in seats]
        run_table(
            table_id=table["table_id"], engine=PokerKitEngine(), agents=agents,
            player_ids=player_ids, blinds=blinds,
            starting_stack=config["starting_stack"],
            hands=config["hands_per_table"],
            table_seed=deck.derive(config["master_seed"], idx),
            log=log)
    player_stats = stats.rollup(log.events, log.results)
    # Attach provenance (archetype) to each player's stats.
    arch_of = {s["player_id"]: s["archetype"]
               for t in config["tables"] for s in t["seats"]}
    for pid, row in player_stats.items():
        row["archetype"] = arch_of.get(pid)
    return log.events, log.results, player_stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "sim" / "config" / "default.json"))
    args = ap.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    events, results, player_stats = simulate(config)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "hand_histories.json").write_text(
        json.dumps({"events": events, "results": results}, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "player_stats.json").write_text(
        json.dumps({"players": player_stats}, indent=2) + "\n", encoding="utf-8")
    print(f"{len(results)} hand-results · {len(player_stats)} players "
          f"-> {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Write the calibration + determinism test**

Create `sim/tests/test_run_and_calibration.py`:

```python
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import run  # noqa: E402

CONFIG = {
    "master_seed": 7, "equity_samples": 80, "blinds": [1, 2],
    "starting_stack": 200, "hands_per_table": 200,
    "tables": [{"table_id": "T1", "seats": [
        {"player_id": "G", "archetype": "grinder"},
        {"player_id": "R", "archetype": "recreational"},
        {"player_id": "A", "archetype": "aggressive_predatory"},
        {"player_id": "P", "archetype": "promo_hunter"},
        {"player_id": "N", "archetype": "new"},
        {"player_id": "H", "archetype": "healthy_anchor"},
    ]}],
}


def test_determinism_same_config_same_output():
    a = run.simulate(copy.deepcopy(CONFIG))
    b = run.simulate(copy.deepcopy(CONFIG))
    assert a == b


def test_emergent_stats_separate_archetypes():
    _, _, ps = run.simulate(copy.deepcopy(CONFIG))
    # Loose-aggressive plays more hands than a tight promo-hunter.
    assert ps["A"]["vpip"] > ps["P"]["vpip"]
    # The aggressive archetype is more aggressive postflop than the recreational.
    assert ps["A"]["aggression_factor"] >= ps["R"]["aggression_factor"]
    # Every player has a stat row with provenance.
    assert all("archetype" in row for row in ps.values())
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest sim/tests/ -v`
Expected: PASS (all tasks' tests). If a calibration assertion is too tight for the sample size, widen the band or raise `hands_per_table` — but do not weaken it to a tautology.

- [ ] **Step 5: Manual adversarial run (you run this; watch the output)**

Run: `python -m sim.run --config sim/config/default.json`
Then confirm: it prints a hand-result + player count and writes `data/sim/hand_histories.json` + `data/sim/player_stats.json`; open `player_stats.json` and sanity-check that (a) `aggressive_predatory`/`grinder` show higher vpip/aggression than `promo_hunter`/`new`, (b) higher-skill archetypes (`grinder`, `healthy_anchor`) trend toward higher `net_chips` than low-skill ones over the full run (the win-rate signal — eyeballed here, not unit-asserted, because of variance), and (c) running it twice yields identical output.

- [ ] **Step 6: Confirm only new files changed**

Run: `git status -s`
Expected: modified `.gitignore`; untracked `sim/`, `data/sim/`, `docs/superpowers/`. No other existing source modified.

- [ ] **Step 7: Stage everything**

Run: `git add sim data/sim docs/superpowers .gitignore`

- [ ] **Step 8: Single commit (show the message for approval first, then run)**

```bash
git commit -m "feat(sim): archetype-driven NL Hold'em outcome simulator

Standalone, deterministic poker simulator: each archetype is a skill-%
agent that decides via tools + a strong/weak policy blend, played through
a PokerKit engine behind a swappable Engine seam. Produces hand histories
and rolled-up per-player behavioral stats (vpip/pfr/aggression/net).
Additive; outputs to data/sim/.

Includes the brainstorming spec + implementation plan under docs/superpowers/."
```
Expected: one commit on `feat/poker-outcome-sim`. Do NOT push.
