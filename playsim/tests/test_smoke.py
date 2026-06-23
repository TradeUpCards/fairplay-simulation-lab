"""Sanity + emergence: signals fall in range and the bot tell shows up."""

from playsim.rosters import get_roster
from playsim.runner import Player, run_session
from playsim.store import load_features, save_result


def test_features_in_range():
    roster = get_roster("healthy_mix")
    r = run_session(roster, 200, seed=1, equity_samples=16)
    for f in r.features.values():
        assert 0.0 <= f["vpip"] <= 1.0
        assert 0.0 <= f["pfr"] <= f["vpip"] + 0.15  # pfr ⊆ vpip (small slack)
        assert f["aggression_factor"] >= 0.0
        assert 0.0 <= f["timing_regularity"] <= 1.0


def test_bot_timing_is_robotic():
    roster = [Player(1, "bot_like"), Player(2, "recreational"),
              Player(3, "regular"), Player(4, "grinder")]
    r = run_session(roster, 250, seed=3, equity_samples=16)
    bot = r.features[1]["timing_regularity"]
    human = r.features[2]["timing_regularity"]
    assert bot > human  # the bot's flat timing is detectable
    assert bot > 0.95


def test_cluster_soft_play_emerges():
    roster = get_roster("case_c")
    r = run_session(roster, 300, seed=5, equity_samples=16)
    # at least one cluster member shows a non-zero member-vs-member result
    members = [p.player_id for p in roster if p.cluster_id]
    assert any(r.features[pid]["soft_play_delta"] != 0.0 for pid in members)


def test_store_roundtrip(tmp_path):
    roster = get_roster("healthy_mix")
    r = run_session(roster, 60, seed=2, equity_samples=12)
    db = tmp_path / "sim.db"
    run_id = save_result(r, db, created_at=0.0)
    rows = load_features(db, run_id)
    assert len(rows) == len(roster)
    assert {row["player_id"] for row in rows} == {p.player_id for p in roster}


def test_health_and_routing():
    # seeded → deterministic; the averaged routing result is stable
    from playsim.service import simulate_routing
    r = simulate_routing(hands=200, seed=42, seeds=8, samples=8)
    pst = r["paid_seat_time"]
    assert isinstance(pst["delta_hours"], float)
    assert pst["fairplay_hours"] >= 0 and pst["standard_hours"] >= 0
    # the hypothesis: routing to a healthier table retains MORE paid seat-time
    assert pst["fairplay_hours"] >= pst["standard_hours"]
    assert r["health"]["fairplay"] >= r["health"]["standard"]
