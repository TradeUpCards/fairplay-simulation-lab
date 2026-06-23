"""FairPlay play-simulation engine.

A deterministic, seeded poker simulator: archetype agents play real No-Limit
Hold'em hands on the PokerKit engine, and the integrity/health signals our
scoring system consumes (vpip, pfr, aggression, soft-play, timing) *emerge from
play* instead of being asserted as fields.

This package is the engine described in ``docs/archetype-play-profiles.md`` and
``docs/learn/poker-sim-walkthrough.html``. It lives in its own top-level folder
so it does not clobber teammate-owned ``sim/``, ``scoring/`` or ``data/``.

V1 (this): FairPlay archetype agents + PokerKit.
V2: optional RLCard/OpenSpiel baseline brains for a "solver-like grinder"
    (see ``playsim.baselines``).
"""

from .runner import run_session, SimResult  # noqa: F401
from .knobs import ARCHETYPES, knobs_for  # noqa: F401

__all__ = ["run_session", "SimResult", "ARCHETYPES", "knobs_for"]
