"""The unified opponent roster: heuristic styles always present; trained RL
checkpoints discovered from disk, built behind the same act() seam, and playable
through GameSession. The RL half is skipped when torch isn't installed, so the
game spine stays testable without the RL deps."""
from __future__ import annotations

import pytest

from playsim.agent import Decision
from pokerlab.engine import GameSession, known, make_agent, roster, style_meta
from pokerlab.engine.roster import CHECKPOINT_DIR


def test_heuristic_roster_without_checkpoints():
    keys = [s["key"] for s in roster()]
    assert {"rock", "station", "maniac", "grinder", "solver"} <= set(keys)
    assert all(s["kind"] == "heuristic" for s in roster() if not s["key"].startswith("rl:"))
    assert known("maniac")
    assert not known("garbage")
    assert not known("rl:does-not-exist")
    assert type(make_agent("rock", 1)).__name__ == "ArchetypeAgent"
    assert style_meta("solver")["kind"] == "heuristic"


def test_unknown_style_rejected():
    with pytest.raises(KeyError):
        GameSession("rl:nope")


def test_rl_checkpoint_discovered_and_playable():
    torch = pytest.importorskip("torch")
    from pokerlab.rl.encode import N_ACTIONS, OBS_DIM
    from pokerlab.rl.model import ActorCritic

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    probe = CHECKPOINT_DIR / "_pytest_probe.pt"
    try:
        net = ActorCritic(OBS_DIM, N_ACTIONS, 128)
        torch.save({"model": net.state_dict(), "obs_dim": OBS_DIM, "n_actions": N_ACTIONS,
                    "hidden": 128, "opponent": "probe"}, probe)

        entry = next((s for s in roster() if s["key"] == "rl:_pytest_probe"), None)
        assert entry is not None and entry["kind"] == "rl"
        assert "checkpoint" not in entry          # internal path must not leak to the UI
        assert known("rl:_pytest_probe")
        assert type(make_agent("rl:_pytest_probe", 1)).__name__ == "RLPolicyAgent"

        g = GameSession("rl:_pytest_probe", seed=21)
        assert g.state_view()["bot"]["kind"] == "rl"
        for _ in range(3):
            guard = 0
            while not g.state_view()["over"]:
                guard += 1
                assert guard < 200
                if g.state_view()["your_turn"]:
                    g.submit_human(Decision("check_call"))
            assert g.state_view()["result"] is not None
            g.next_hand()
    finally:
        if probe.exists():
            probe.unlink()
