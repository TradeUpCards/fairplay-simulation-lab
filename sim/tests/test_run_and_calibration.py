import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import run  # noqa: E402


def _cfg(hands: int, samples: int) -> dict:
    return {
        "master_seed": 7, "equity_samples": samples, "blinds": [1, 2],
        "starting_stack": 200, "hands_per_table": hands,
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
    cfg = _cfg(12, 20)
    a = run.simulate(copy.deepcopy(cfg))
    b = run.simulate(copy.deepcopy(cfg))
    assert a == b


def test_emergent_stats_separate_archetypes():
    _, _, ps = run.simulate(_cfg(80, 30))
    # Loose-aggressive plays far more hands than a tight promo-hunter.
    assert ps["A"]["vpip"] > ps["P"]["vpip"]
    # The aggressive archetype is at least as aggressive postflop as the recreational.
    assert ps["A"]["aggression_factor"] >= ps["R"]["aggression_factor"]
    # Every player has a stat row with provenance.
    assert all("archetype" in row for row in ps.values())
