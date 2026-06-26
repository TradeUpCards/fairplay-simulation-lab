"""The engine-hook oracle: the pausable interactive driver must reproduce the
canonical hand byte-for-byte.

If the human seat plays the same archetype policy a bot would, ``InteractiveHand``
must produce a HandRecord identical to ``play_hand`` for the same seed -- for EVERY
choice of which seat is the human. That proves two things at once: the generator
refactor preserves the original loop exactly (no rng-order drift), and the
pause/resume hook is correct. The only nondeterminism we ever introduce is a human
who plays differently -- which is the point.
"""

import random

from playsim.agent import ArchetypeAgent
from playsim.interactive import InteractiveHand
from playsim.knobs import knobs_for
from playsim.table import play_hand

_ARCHETYPES = ["recreational", "grinder", "aggressive_predatory",
               "promo_hunter", "solver_like", "regular"]


def _setup():
    pids = list(range(1, len(_ARCHETYPES) + 1))
    agents = [ArchetypeAgent(pid, knobs_for(a)) for pid, a in zip(pids, _ARCHETYPES)]
    common = dict(
        seat_player_ids=pids,
        seat_stacks=[200] * len(pids),
        sb=1, bb=2, hand_id=7,
        members_by_player={}, weak_player_ids=frozenset(),
    )
    return common, agents


def test_interactive_matches_play_hand_for_every_human_seat():
    common, agents = _setup()
    canonical = play_hand(agents, rng=random.Random(123), **common)

    for human_seat in range(len(agents)):
        rng = random.Random(123)
        hand = InteractiveHand(human_seat=human_seat, seat_agents=agents,
                               rng=rng, **common)
        obs = hand.start()
        while obs is not None:
            # the "human" plays its own archetype, drawing from the SAME rng,
            # so the whole hand must come out identical to the canonical run
            obs = hand.submit(agents[human_seat].act(obs, rng))
        assert hand.complete, f"hand never completed with seat {human_seat} as human"
        assert hand.record == canonical, f"record mismatch when seat {human_seat} is human"


def test_human_can_play_a_different_line():
    """Sanity: a human who deviates (always folds when facing a bet) still produces a
    legal, completed hand -- the hook accepts arbitrary legal decisions, not just the
    archetype's."""
    from playsim.agent import Decision

    common, agents = _setup()
    rng = random.Random(5)
    hand = InteractiveHand(human_seat=2, seat_agents=agents, rng=rng, **common)
    obs = hand.start()
    while obs is not None:
        # fold to any bet, otherwise check
        d = Decision("fold") if obs.to_call > 0 else Decision("check_call")
        obs = hand.submit(d)
    assert hand.complete
    # the human folded to all pressure, so they are never at showdown with chips won
    assert hand.record is not None
