"""Unified opponent roster — heuristic table styles plus any trained RL bots.

The whole point of the lab is that every opponent sits behind one ``act(obs, rng)``
seam, so the human can pick a hand-tuned table character (an ArchetypeAgent) or a
neural net they trained themselves (an RLPolicyAgent) from the same menu.

RL checkpoints are *discovered* at call time from ``pokerlab/rl/checkpoints/*.pt``
— train a bot, restart the server, and it shows up. torch is imported lazily, only
when an RL bot is actually built, so the game spine runs with no RL deps installed
and no checkpoints present.
"""
from __future__ import annotations

from pathlib import Path

from .agents import BOT_STYLES, DIFFICULTY_LABELS, build_bot, style_roster

# train.py saves here: pokerlab/rl/checkpoints/<name>.pt
CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "rl" / "checkpoints"
RL_PREFIX = "rl:"


def _rl_styles() -> dict[str, dict]:
    """Trained checkpoints presented as selectable opponents (keyed ``rl:<name>``)."""
    if not CHECKPOINT_DIR.is_dir():
        return {}
    out: dict[str, dict] = {}
    for path in sorted(CHECKPOINT_DIR.glob("*.pt")):
        key = RL_PREFIX + path.stem
        out[key] = {
            "key": key,
            "name": f"Trained Bot · {path.stem}",
            "blurb": "A neural net you trained (PPO). No fixed leak to exploit — "
                     "it learned to maximize chips. Beat it if you can.",
            "checkpoint": str(path),
            "kind": "rl",
            "difficulty": 4,
            "tier": "Trained",
        }
    return out


def roster() -> list[dict]:
    """UI-facing roster: heuristic styles first, then trained bots (no paths leak)."""
    heur = [{**s, "kind": "heuristic"} for s in style_roster()]
    rl = [{k: v for k, v in s.items() if k != "checkpoint"} for s in _rl_styles().values()]
    return heur + rl


def style_meta(style_key: str) -> dict | None:
    """Display metadata for one style, or None if unknown (no engine objects)."""
    if style_key in BOT_STYLES:
        s = BOT_STYLES[style_key]
        return {"key": s.key, "name": s.name, "blurb": s.blurb, "kind": "heuristic",
                "difficulty": s.difficulty, "tier": DIFFICULTY_LABELS[s.difficulty]}
    rl = _rl_styles().get(style_key)
    if rl is not None:
        return {k: v for k, v in rl.items() if k != "checkpoint"}
    return None


def known(style_key: str) -> bool:
    return style_key in BOT_STYLES or style_key in _rl_styles()


def make_agent(style_key: str, player_id: int, equity_samples: int = 30):
    """Build the agent for a style behind the standard ``act(obs, rng)`` seam.

    Heuristic styles → ArchetypeAgent. RL styles (``rl:<name>``) → RLPolicyAgent
    loaded from the checkpoint. torch is imported here, lazily, so picking a
    heuristic bot never touches the RL stack.
    """
    if style_key in BOT_STYLES:
        return build_bot(style_key, player_id, equity_samples)
    rl = _rl_styles().get(style_key)
    if rl is None:
        raise KeyError(f"unknown style {style_key!r}; known: {sorted(BOT_STYLES) + sorted(_rl_styles())}")
    from ..rl.policy import RLPolicyAgent      # lazy: imports torch only when an RL bot is picked
    return RLPolicyAgent(player_id, rl["checkpoint"])
