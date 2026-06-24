"""V2 — external baseline brains (RLCard / OpenSpiel) under the Agent protocol.

The point of V2 is a *stronger* opponent than the hand-tuned knob policy — a
"solver-like grinder" / strong regular trained by CFR/RL. Two paths:

1. **Built-in (no extra deps):** the ``solver_like`` archetype in ``knobs.py``
   is a high-skill, balanced, tight-aggressive brain usable today. Use it via
   the normal roster path (``Player(id, "solver_like")``).

2. **RLCard adapter (this module):** wrap a trained RLCard No-Limit Hold'em
   agent so it can sit at the table under the same ``act(obs, rng)`` interface.
   This keeps the engine (PokerKit) authoritative for legality while RLCard
   supplies the *decision*. RLCard is an optional dependency — install with
   ``pip install rlcard[torch]`` — so the import is lazy and guarded.

The adapter is a scaffold: it maps our :class:`Observation` onto an RLCard
action and back. RLCard's NLHE action space is discrete
(fold / check-call / raise-half-pot / raise-pot / all-in), which maps cleanly
onto our :class:`Decision`. Wire a concrete model in ``_select_action``.
"""

from __future__ import annotations

from .agent import Decision, Observation


class RLCardUnavailable(RuntimeError):
    pass


class RLCardAgent:
    """Adapter: an RLCard-trained brain playing at the PokerKit table.

    Parameters
    ----------
    player_id : int
    model_path : str | None
        Path to a saved RLCard agent (e.g. a DQN/NFSP checkpoint). If ``None``,
        a built-in heuristic fallback is used so the adapter is runnable.
    """

    agent_model = "rlcard"
    agent_version = "external"

    def __init__(self, player_id: int, model_path: str | None = None):
        self.player_id = player_id
        self.model_path = model_path
        # provenance reflects the loaded checkpoint when one is supplied
        self.agent_version = model_path if model_path else "heuristic-fallback"
        self._agent = None
        self._load()

    def _load(self) -> None:
        try:
            import rlcard  # noqa: F401
        except ImportError as e:  # pragma: no cover - optional dep
            raise RLCardUnavailable(
                "RLCard is not installed. Run `pip install rlcard[torch]`, or use "
                "the built-in `solver_like` archetype which needs no extra deps."
            ) from e
        if self.model_path:
            import torch  # pragma: no cover
            self._agent = torch.load(self.model_path, map_location="cpu")

    # Our discrete action vocabulary, aligned to RLCard NLHE:
    #   0 fold · 1 check/call · 2 raise half-pot · 3 raise pot · 4 all-in
    def _select_action(self, obs: Observation, rng) -> int:  # pragma: no cover
        if self._agent is not None:
            state = self._encode(obs)
            return int(self._agent.step(state))
        # Fallback heuristic so the adapter runs without a trained model:
        # tight-aggressive, equity-agnostic-but-reasonable.
        from .equity import equity_mc, preflop_percentile
        strength = (
            preflop_percentile(obs.hole) if obs.street == 0
            else equity_mc(obs.hole, obs.board, obs.n_active, rng, 24)
        )
        if strength < 0.45:
            return 1 if obs.to_call == 0 else 0
        if strength > 0.80:
            return 3
        return 2 if rng.random() < 0.6 else 1

    def _encode(self, obs: Observation):  # pragma: no cover
        """Map our Observation onto an RLCard state dict (model-specific)."""
        raise NotImplementedError(
            "Provide an encoder matching your RLCard model's observation space."
        )

    def act(self, obs: Observation, rng) -> Decision:
        a = self._select_action(obs, rng)
        if a == 0 and obs.to_call > 0:
            return Decision("fold", latency_ms=900)
        if a in (2, 3, 4) and obs.max_raise_to > obs.min_raise_to:
            frac = {2: 0.5, 3: 1.0, 4: 99.0}[a]
            amount = int(min(obs.max_raise_to, obs.to_call + obs.pot * frac + obs.to_call))
            amount = max(obs.min_raise_to, min(obs.max_raise_to, amount))
            return Decision("raise", amount=amount, is_raise=True, latency_ms=900)
        return Decision(
            "check_call", is_call=obs.to_call > 0,
            voluntary=obs.street == 0 and obs.to_call > 0, latency_ms=900,
        )
