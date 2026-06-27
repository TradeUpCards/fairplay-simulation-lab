"""Seating policies — the swappable decision seam the room loop selects by config.

The room orchestrator is policy-agnostic: it hands each seeker plus the live
table set to ``policy.choose`` and acts on the returned ``PolicyDecision``. Three
policies sit behind one interface:

* ``StandardPolicy`` — most-full open table (liquidity-seeking), the honest null.
  Never calls the backend.
* ``FairPlayRoutePolicy`` — delegates to the real backend router via
  ``router_adapter``; seats the best non-gated open table. The MVP headline arm.
* ``FairPlayProtectPolicy`` — same routing, but may *defer* (balk) a vulnerable
  seeker when the best available predicted health is below a safety threshold.
  Experimental / disabled-by-default; not tuned and not used for headline claims.

A defer (protect declining a bad-only option) is distinct from a balk (no open
seat exists at all): ``PolicyDecision.deferred`` separates them for metrics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .router_adapter import RouterAdapter

# Backend routing-gate cohort (matches scoring.seating.VULNERABLE_ARCHETYPES).
# Distinct from playsim's north-star _COHORT, which also includes promo_hunter.
VULNERABLE_ARCHETYPES = frozenset({"new", "recreational"})


@dataclass
class Seeker:
    player_id: int      # playsim int id
    archetype: str


@dataclass
class PolicyDecision:
    table_id: str | None        # None -> not seated this attempt
    reason: str                 # badge / selection reason, e.g. "most_full", "recommended", "protect_deferred"
    meta: dict = field(default_factory=dict)
    deferred: bool = False      # True only when protect declined an available-but-unsafe seat

    @property
    def seated(self) -> bool:
        return self.table_id is not None


class RandomPolicy:
    """Uniformly random open table — the *neutral* baseline (no routing intelligence
    at all). Isolates a health/liquidity policy's effect from the do-nothing case.
    Seeded for deterministic replay; balks only when no seat is open room-wide."""

    name = "random"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def choose(self, seeker: Seeker, live_tables: list[dict]) -> PolicyDecision:
        candidates = sorted(
            (t for t in live_tables if t.get("open_seats", 0) > 0),
            key=lambda t: t["table_id"],
        )
        if not candidates:
            return PolicyDecision(None, "no_open_seat")
        t = self.rng.choice(candidates)
        return PolicyDecision(t["table_id"], "random",
                              {"seated_count": t.get("seated_count", 0)})


class StandardPolicy:
    """Most-full open table; deterministic tie-break (lowest table_id). No backend."""

    name = "standard"

    def choose(self, seeker: Seeker, live_tables: list[dict]) -> PolicyDecision:
        candidates = [t for t in live_tables if t.get("open_seats", 0) > 0]
        if not candidates:
            return PolicyDecision(None, "no_open_seat")
        best = min(candidates, key=lambda t: (-t.get("seated_count", 0), t["table_id"]))
        return PolicyDecision(best["table_id"], "most_full",
                              {"seated_count": best.get("seated_count", 0)})


class FairPlayRoutePolicy:
    """Best non-gated open table per the real backend router. MVP headline arm."""

    name = "fairplay_route"

    def __init__(self, adapter: RouterAdapter) -> None:
        self.adapter = adapter

    def choose(self, seeker: Seeker, live_tables: list[dict]) -> PolicyDecision:
        p = self.adapter.recommend(seeker.player_id, live_tables)
        if p.table_id is None:
            return PolicyDecision(None, "no_open_seat",
                                  {"operator_view": p.operator_view})
        return PolicyDecision(p.table_id, p.badge or "available",
                              {"rank": p.rank, "health": p.health,
                               "health_band": p.health_band,
                               "operator_view": p.operator_view})


class FairPlayProtectPolicy:
    """FairPlay routing that may defer a vulnerable seeker from unsafe-only seats.

    Experimental: ``enabled`` defaults to False (behaves exactly like route).
    ``safety_threshold`` is a provisional, untuned constant — not a headline knob.
    """

    name = "fairplay_protect"

    def __init__(self, adapter: RouterAdapter, *, enabled: bool = False,
                 safety_threshold: float = 50.0) -> None:
        self.adapter = adapter
        self.enabled = enabled
        self.safety_threshold = safety_threshold

    def choose(self, seeker: Seeker, live_tables: list[dict]) -> PolicyDecision:
        p = self.adapter.recommend(seeker.player_id, live_tables)
        if p.table_id is None:
            return PolicyDecision(None, "no_open_seat",
                                  {"operator_view": p.operator_view})
        if (self.enabled
                and seeker.archetype in VULNERABLE_ARCHETYPES
                and p.health is not None
                and p.health < self.safety_threshold):
            return PolicyDecision(
                None, "protect_deferred",
                {"best_health": p.health, "best_table": p.table_id,
                 "threshold": self.safety_threshold,
                 "operator_view": p.operator_view},
                deferred=True,
            )
        return PolicyDecision(p.table_id, p.badge or "available",
                              {"rank": p.rank, "health": p.health,
                               "health_band": p.health_band,
                               "operator_view": p.operator_view})


class FairPlayBalancedPolicy:
    """FairPlay routing with a liquidity / load-balancing term.

    Plain FairPlay-route is a greedy per-seeker health maximizer: it piles
    vulnerable seekers onto the single healthiest table, which (a) strands later
    arrivals and (b) concentrates fish so a fish-heavy table collapses all at once
    when they tilt out together. This variant instead spreads seekers across the
    set of *healthy-enough* open tables, picking the one with the fewest vulnerable
    players already seated — so no single healthy table accumulates (and then loses)
    the whole cohort. Falls back to plain route when no table clears the floor.

    Experimental: tests whether de-concentrating recovers the FairPlay thesis.
    """

    name = "fairplay_balanced"

    def __init__(self, adapter: RouterAdapter, *, health_floor: float = 50.0) -> None:
        self.adapter = adapter
        self.health_floor = health_floor

    def choose(self, seeker: Seeker, live_tables: list[dict]) -> PolicyDecision:
        p = self.adapter.recommend(seeker.player_id, live_tables)
        if p.table_id is None:
            return PolicyDecision(None, "no_open_seat",
                                  {"operator_view": p.operator_view})
        ov = {e["table_id"]: e for e in p.operator_view}
        cls = self.adapter.classifications

        def vuln_count(t: dict) -> int:
            return sum(1 for pid in t.get("seated_player_ids", [])
                       if cls.get(pid) in VULNERABLE_ARCHETYPES)

        acceptable = [
            t for t in live_tables
            if t.get("open_seats", 0) > 0
            and t["table_id"] in ov
            and ov[t["table_id"]]["badge"] != "hidden_gated"
            and ov[t["table_id"]]["health"] >= self.health_floor
        ]
        if not acceptable:
            # nothing clears the health floor -> behave like plain route
            return PolicyDecision(p.table_id, p.badge or "available",
                                  {"rank": p.rank, "health": p.health,
                                   "health_band": p.health_band,
                                   "operator_view": p.operator_view})
        # spread: fewest fish already seated, tie-break higher health then id
        best = min(acceptable, key=lambda t: (vuln_count(t),
                                              -ov[t["table_id"]]["health"], t["table_id"]))
        e = ov[best["table_id"]]
        return PolicyDecision(best["table_id"], "balanced",
                              {"rank": e["rank"], "health": e["health"],
                               "health_band": e["health_band"],
                               "operator_view": p.operator_view})


class FairPlayLivenessPolicy:
    """FairPlay routing that can seed/grow a forming healthy table.

    This is not "most-full with a health tiebreak." It first asks whether a good
    dealable healthy seat already exists. If not, it can choose the best non-gated
    forming candidate so FairPlay can express the table-growth mechanism that the
    baseline model lacked. If multiple forming options exist, it prefers growing
    an existing one-player table before seeding another empty table; otherwise the
    policy scatters liquidity into unpaid solo tables.
    """

    name = "fairplay_liveness"

    def __init__(
        self,
        adapter: RouterAdapter,
        *,
        dealable_health_floor: float = 80.0,
        forming_health_floor: float = 70.0,
    ) -> None:
        self.adapter = adapter
        self.dealable_health_floor = dealable_health_floor
        self.forming_health_floor = forming_health_floor

    def choose(self, seeker: Seeker, live_tables: list[dict]) -> PolicyDecision:
        p = self.adapter.recommend(seeker.player_id, live_tables)
        if p.table_id is None:
            return PolicyDecision(None, "no_open_seat",
                                  {"operator_view": p.operator_view})

        by_id = {t["table_id"]: t for t in live_tables}
        visible = [
            e for e in p.operator_view
            if e.get("badge") != "hidden_gated"
            and by_id.get(e["table_id"], {}).get("open_seats", 0) > 0
        ]
        dealable = [
            e for e in visible
            if by_id[e["table_id"]].get("seated_count", 0) >= 2
        ]
        good_dealable = [
            e for e in dealable
            if e.get("health", 0.0) >= self.dealable_health_floor
            and e.get("seating_risk") == "low"
        ]
        if good_dealable:
            best = good_dealable[0]
            return PolicyDecision(
                best["table_id"], "liveness_dealable",
                {"rank": best["rank"], "health": best["health"],
                 "health_band": best["health_band"],
                 "operator_view": p.operator_view},
            )

        forming = [
            e for e in visible
            if (
                by_id[e["table_id"]].get("table_mode") == "forming"
                or by_id[e["table_id"]].get("seated_count", 0) < 2
            )
            and e.get("health", 0.0) >= self.forming_health_floor
        ]
        if forming:
            growable = [
                e for e in forming
                if by_id[e["table_id"]].get("seated_count", 0) == 1
            ]
            best = (growable or forming)[0]
            return PolicyDecision(
                best["table_id"], "liveness_forming",
                {"rank": best["rank"], "health": best["health"],
                 "health_band": best["health_band"],
                 "operator_view": p.operator_view},
            )

        return PolicyDecision(p.table_id, p.badge or "available",
                              {"rank": p.rank, "health": p.health,
                               "health_band": p.health_band,
                               "operator_view": p.operator_view})


def make_policy(name: str, adapter: RouterAdapter | None = None, **kwargs):
    """Config switch -> policy instance. The room loop calls the same ``choose``
    regardless of which policy this returns."""
    if name == "random":
        return RandomPolicy(seed=kwargs.get("seed", 0))
    if name == "standard":
        return StandardPolicy()
    if name == "fairplay_route":
        if adapter is None:
            raise ValueError("fairplay_route requires a RouterAdapter")
        return FairPlayRoutePolicy(adapter)
    if name == "fairplay_protect":
        if adapter is None:
            raise ValueError("fairplay_protect requires a RouterAdapter")
        return FairPlayProtectPolicy(adapter, **kwargs)
    if name == "fairplay_balanced":
        if adapter is None:
            raise ValueError("fairplay_balanced requires a RouterAdapter")
        return FairPlayBalancedPolicy(adapter, **kwargs)
    if name == "fairplay_liveness":
        if adapter is None:
            raise ValueError("fairplay_liveness requires a RouterAdapter")
        return FairPlayLivenessPolicy(adapter, **kwargs)
    raise ValueError(f"unknown policy {name!r}")
