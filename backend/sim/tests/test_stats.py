import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import stats  # noqa: E402


def test_rollup_computes_vpip_pfr_aggression():
    # P1: 2 hands. H1 = preflop raise (voluntary + pfr), then a flop bet and a turn
    # call → postflop AF = 1 raise / 1 call = 1.0. H2 = preflop fold.
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
    assert abs(out["vpip"] - 0.5) < 1e-9
    assert abs(out["pfr"] - 0.5) < 1e-9
    assert abs(out["aggression_factor"] - 1.0) < 1e-9
    assert out["net_chips"] == 48
    # avg_pot is over CONTESTED hands only: H1 (pot 20.0) counts, the H2 fold doesn't.
    assert out["hands_contested"] == 1
    assert out["avg_pot_size_bb"] == 20.0
