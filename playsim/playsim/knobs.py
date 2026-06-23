"""Archetype knob vectors + empirical target stats.

One parameterized policy, ten knob-sets — exactly the design in
``docs/archetype-play-profiles.md``. Knobs are normalized to roughly [0, 1].

* ``looseness``           preflop entering-range width (≈ target vpip)
* ``pf_aggression``       raise-first frequency (≈ target pfr)
* ``postflop_aggression`` bet/raise vs call after the flop (drives AF)
* ``sizing``              bet size as a fraction of the pot
* ``skill``               quality of the equity-vs-pot-odds decision
* ``bluff``               extra aggression with weak holdings
* ``stamina`` / ``tilt_quit``  session length / propensity to leave on a loss
* ``risk_aversion``       declines marginal +EV variance (promo_hunter)

Integrity / behavior flags:
* ``soft_play_members``   cut aggression + give up EV vs cluster members
* ``target_weak``         hunt the weakest opponent (predator / cluster outsider)
* ``timing_jitter``       latency variance; ~0 = robotic (bot tell)
* ``deterministic``       no mixed-strategy randomness (bot)

The ``targets`` block is the empirical median from the 122-player fixture
(``data/players.json``), reproduced from the archetype-play-profiles master
table. The calibration loop tunes knobs until realized stats hit these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class Knobs:
    archetype: str
    looseness: float
    pf_aggression: float
    postflop_aggression: float
    sizing: float
    skill: float
    bluff: float = 0.05
    risk_aversion: float = 0.2
    stamina: float = 0.5
    tilt_quit: float = 0.2
    # behavior / integrity layers
    soft_play_members: bool = False
    target_weak: bool = False
    timing_jitter: float = 0.5
    deterministic: bool = False
    # empirical targets (median) for the calibration report
    targets: Mapping[str, float] = field(default_factory=dict)


def _t(vpip, pfr, af, pot):
    return {"vpip": vpip, "pfr": pfr, "aggression_factor": af, "avg_pot_bb": pot}


# looseness ≈ target vpip and pf_aggression ≈ target pfr by construction
# (the preflop policy uses these directly as percentile thresholds), so preflop
# stats calibrate analytically. postflop_aggression is the one knob the
# calibration loop tunes against realized AF.
ARCHETYPES: dict[str, Knobs] = {
    "new": Knobs(
        "new", looseness=0.36, pf_aggression=0.08, postflop_aggression=0.18,
        sizing=0.40, skill=0.20, bluff=0.02, risk_aversion=0.15,
        stamina=0.10, tilt_quit=0.80, timing_jitter=0.7,
        targets=_t(0.36, 0.08, 0.89, 8),
    ),
    "recreational": Knobs(
        "recreational", looseness=0.38, pf_aggression=0.12, postflop_aggression=0.30,
        sizing=0.45, skill=0.30, bluff=0.04, risk_aversion=0.15,
        stamina=0.45, tilt_quit=0.30, timing_jitter=0.8,
        targets=_t(0.38, 0.12, 1.18, 11),
    ),
    "regular": Knobs(
        "regular", looseness=0.28, pf_aggression=0.22, postflop_aggression=0.55,
        sizing=0.60, skill=0.70, bluff=0.10, risk_aversion=0.25,
        stamina=0.6, tilt_quit=0.15, timing_jitter=0.5,
        targets=_t(0.28, 0.22, 2.06, 19),
    ),
    "grinder": Knobs(
        "grinder", looseness=0.23, pf_aggression=0.21, postflop_aggression=0.70,
        sizing=0.66, skill=0.85, bluff=0.14, risk_aversion=0.20, target_weak=True,
        stamina=0.95, tilt_quit=0.05, timing_jitter=0.45,
        targets=_t(0.23, 0.21, 2.69, 27),
    ),
    "aggressive_predatory": Knobs(
        "aggressive_predatory", looseness=0.59, pf_aggression=0.45, postflop_aggression=0.92,
        sizing=0.85, skill=0.80, bluff=0.30, risk_aversion=0.10, target_weak=True,
        stamina=0.75, tilt_quit=0.10, timing_jitter=0.55,
        targets=_t(0.59, 0.45, 4.30, 43),
    ),
    "promo_hunter": Knobs(
        "promo_hunter", looseness=0.30, pf_aggression=0.13, postflop_aggression=0.28,
        sizing=0.40, skill=0.40, bluff=0.02, risk_aversion=0.90,
        stamina=0.35, tilt_quit=0.25, timing_jitter=0.7,
        targets=_t(0.30, 0.13, 1.10, 10),
    ),
    "healthy_anchor": Knobs(
        "healthy_anchor", looseness=0.28, pf_aggression=0.18, postflop_aggression=0.50,
        sizing=0.55, skill=0.65, bluff=0.08, risk_aversion=0.30, target_weak=False,
        stamina=0.85, tilt_quit=0.10, timing_jitter=0.55,
        targets=_t(0.28, 0.18, 1.88, 18),
    ),
    "shared_device_household": Knobs(
        "shared_device_household", looseness=0.33, pf_aggression=0.16, postflop_aggression=0.42,
        sizing=0.52, skill=0.50, bluff=0.06, risk_aversion=0.25,
        stamina=0.55, tilt_quit=0.20, timing_jitter=0.65,
        targets=_t(0.33, 0.16, 1.55, 15),
    ),
    "cluster_member": Knobs(
        "cluster_member", looseness=0.30, pf_aggression=0.23, postflop_aggression=0.60,
        sizing=0.60, skill=0.72, bluff=0.10, risk_aversion=0.20,
        soft_play_members=True, target_weak=True,
        stamina=0.7, tilt_quit=0.10, timing_jitter=0.5,
        targets=_t(0.30, 0.23, 2.15, 20),
    ),
    "bot_like": Knobs(
        "bot_like", looseness=0.24, pf_aggression=0.20, postflop_aggression=0.58,
        sizing=0.58, skill=0.70, bluff=0.08, risk_aversion=0.20,
        deterministic=True, timing_jitter=0.02,
        stamina=1.0, tilt_quit=0.0,
        targets=_t(0.24, 0.20, 2.05, 20),
    ),
    # V2 baseline: a "solver-like grinder" / strong regular. Built-in high-skill
    # brain usable now; the RLCard/OpenSpiel adapter in playsim.baselines can
    # swap in a trained equilibrium agent under the same archetype name.
    "solver_like": Knobs(
        "solver_like", looseness=0.22, pf_aggression=0.19, postflop_aggression=0.80,
        sizing=0.66, skill=0.97, bluff=0.18, risk_aversion=0.18, target_weak=True,
        stamina=0.95, tilt_quit=0.02, timing_jitter=0.45,
        targets=_t(0.22, 0.19, 2.80, 28),
    ),
}


def _apply_calibration() -> None:
    """Overlay tuned ``postflop_aggression`` from ``calibration.json`` if present.

    The calibration loop (``playsim.calibrate``) writes that file; this keeps the
    hand-authored defaults in source while letting the empirical tuner refine the
    one knob that needs it. Safe no-op if the file is absent.
    """
    import json
    from dataclasses import replace
    from pathlib import Path

    path = Path(__file__).with_name("calibration.json")
    if not path.exists():
        return
    try:
        pf = json.loads(path.read_text()).get("postflop_aggression", {})
    except (ValueError, OSError):
        return
    for arch, val in pf.items():
        if arch in ARCHETYPES:
            ARCHETYPES[arch] = replace(ARCHETYPES[arch], postflop_aggression=float(val))


_apply_calibration()


# Natural session length (minutes) per archetype — median from the fixture
# (archetype-play-profiles master table). The retention/play-time model uses
# this as the baseline budget, which tilt shortens when a player is bleeding.
SESSION_MIN = {
    "new": 20, "recreational": 73, "regular": 135, "grinder": 325,
    "aggressive_predatory": 251, "promo_hunter": 39, "healthy_anchor": 209,
    "shared_device_household": 119, "cluster_member": 178, "bot_like": 182,
    "solver_like": 300,
}


def session_min_for(archetype: str) -> int:
    return SESSION_MIN.get(archetype, 90)


def knobs_for(archetype: str) -> Knobs:
    try:
        return ARCHETYPES[archetype]
    except KeyError:
        raise KeyError(
            f"unknown archetype {archetype!r}; known: {sorted(ARCHETYPES)}"
        ) from None
