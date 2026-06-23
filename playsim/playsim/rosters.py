"""Pre-built demo table rosters — the scenarios the lab cares about.

Each returns a ``list[Player]``. Player ids are stable within a table so runs
are comparable. These map onto the mandatory demo cases (see
``data/seeded_case_labels.json``) so the simulation can feed the same stories.
"""

from __future__ import annotations

from .runner import Player

# name -> builder
def healthy_mix() -> list[Player]:
    """A balanced, healthy 6-max: regulars + an anchor + a couple recreationals."""
    return [
        Player(1, "regular"), Player(2, "healthy_anchor"), Player(3, "recreational"),
        Player(4, "regular"), Player(5, "recreational"), Player(6, "grinder"),
    ]


def case_a_new_player() -> list[Player]:
    """CASE-A: a new player at a predator-heavy, beginner-unfriendly table."""
    return [
        Player(104, "new"), Player(176, "aggressive_predatory"),
        Player(177, "aggressive_predatory"), Player(50, "grinder"),
        Player(51, "regular"), Player(52, "recreational"),
    ]


def case_c_cluster() -> list[Player]:
    """CASE-C: a 3-account collusion ring among outsiders (the true positive)."""
    return [
        Player(198, "cluster_member", cluster_id="C-1"),
        Player(199, "cluster_member", cluster_id="C-1"),
        Player(200, "cluster_member", cluster_id="C-1"),
        Player(60, "recreational"), Player(61, "regular"),
        Player(62, "healthy_anchor"),
    ]


def case_e_household() -> list[Player]:
    """CASE-E: two accounts on one device, independent play (false-positive trap)."""
    return [
        Player(210, "shared_device_household", household_id="H-1"),
        Player(211, "shared_device_household", household_id="H-1"),
        Player(70, "regular"), Player(71, "recreational"),
        Player(72, "grinder"), Player(73, "healthy_anchor"),
    ]


def solver_bench() -> list[Player]:
    """V2: solver-like grinders vs the field — a strength benchmark table."""
    return [
        Player(1, "solver_like"), Player(2, "solver_like"),
        Player(3, "regular"), Player(4, "recreational"),
        Player(5, "grinder"), Player(6, "new"),
    ]


# --- Health/routing counterfactual --------------------------------------
# The SAME vulnerable cohort (fixed ids 900-902) is seated at two compositions.
# Running both under the same seed isolates the routing decision; the play-time
# metrics measure exactly these routed ids (the intersection of both rosters), so
# the fields can differ freely. 1 new (early-break story) + 2 recreational (the
# churn/play-time "cohort to protect").
_COHORT = [Player(900, "new"), Player(901, "recreational"), Player(902, "recreational")]


def routing_standard() -> list[Player]:
    """Standard room: cohort hunted by skilled extractors (grinders + a predator).

    The unhealthy case per the PRD: competent regulars/grinders steadily extract
    from the lone fish → fast bleed → tilt → short session.
    """
    return _COHORT + [
        Player(910, "grinder"), Player(911, "grinder"),
        Player(912, "aggressive_predatory"),
    ]


def routing_fairplay() -> list[Player]:
    """FairPlay room: cohort routed to recreational depth (fish among fish).

    The healthy case: the cohort plays mostly peers (other recreationals) + one
    mild non-predatory anchor → slow chip movement, low loss rate → long session.
    """
    return _COHORT + [
        Player(920, "recreational"), Player(921, "recreational"),
        Player(923, "healthy_anchor"),
    ]


TABLES = {
    "healthy_mix": healthy_mix,
    "case_a": case_a_new_player,
    "case_c": case_c_cluster,
    "case_e": case_e_household,
    "solver_bench": solver_bench,
    "routing_standard": routing_standard,
    "routing_fairplay": routing_fairplay,
}


def get_roster(name: str) -> list[Player]:
    try:
        return TABLES[name]()
    except KeyError:
        raise KeyError(f"unknown table {name!r}; known: {sorted(TABLES)}") from None
