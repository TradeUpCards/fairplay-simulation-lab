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


def make_policy(name: str, adapter: RouterAdapter | None = None, **kwargs):
    """Config switch -> policy instance. The room loop calls the same ``choose``
    regardless of which policy this returns."""
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
    raise ValueError(f"unknown policy {name!r}")
