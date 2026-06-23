import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim.agents.archetype import Agent, ARCHETYPES  # noqa: E402
from sim.driver import run_table  # noqa: E402
from sim.engine.pokerkit_engine import PokerKitEngine  # noqa: E402
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
    by_hand = {}
    for r in log.results:
        by_hand.setdefault(r["hand_id"], 0)
        by_hand[r["hand_id"]] += r["net"]
    assert all(v == 0 for v in by_hand.values())          # chips conserved per hand


def test_run_is_deterministic():
    a, b = _run(42), _run(42)
    assert a.events == b.events and a.results == b.results
