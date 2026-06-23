"""FairPlay scoring core (P3, Contract 2).

Deterministic "champion" scorers that read P2's ``data/*.json`` and emit the
scores, recommendations, and reason codes the frontend + evidence packet
consume. Pure functions over already-frozen fixtures — this layer never calls
the simulator live (stack decision D0).
"""

from .classify import classify, ARCHETYPES, classify_all

__all__ = ["classify", "classify_all", "ARCHETYPES"]
