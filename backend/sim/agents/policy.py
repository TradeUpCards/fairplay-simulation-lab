"""Reference policies + style overlay. Pure functions over a DecisionContext.

v1.2 (realism pass): preflop hand *selection* is handled by the range gate in
archetype.py; here, playable hands **open-raise** (good players raise, not limp)
and the postflop lines **fold more to big bets** so pots don't balloon. Preflop
opens are small multiples of the big blind; postflop bets are ~half pot.
Bluff-raises are tagged so the log can tell them from value raises.
"""
from __future__ import annotations

import random

from sim.agents import tools
from sim.engine.base import Action, DecisionContext


def _raise_to(ctx: DecisionContext, pot_fraction: float, tag: str = "") -> Action:
    if ctx.street == "preflop":
        target = max(3 * ctx.big_blind, 3 * ctx.to_call)     # ~3bb open / 3x a raise
    else:
        target = ctx.to_call + int((ctx.pot + ctx.to_call) * pot_fraction)
    target = max(target, ctx.to_call + ctx.big_blind)        # at least a min-ish raise
    target = min(target, ctx.stack)                          # cap at all-in
    return Action("raise_to", target, tag=tag)


def strong_policy(ctx: DecisionContext, equity: float) -> Action:
    odds = tools.pot_odds(ctx.pot, ctx.to_call)
    if ctx.street == "preflop":
        if ctx.to_call <= ctx.big_blind:         # unraised pot: open-raise
            return _raise_to(ctx, 0.0)
        if equity > odds + 0.15:                 # facing a raise: 3-bet a premium
            return _raise_to(ctx, 0.0)
        if equity >= odds:
            return Action("check_call")
        return Action("fold")
    # postflop: value-bet edges, fold marginal hands — and demand more to call a big bet.
    if ctx.to_call == 0:
        return _raise_to(ctx, 0.5) if equity > 0.62 else Action("check_call")
    big_bet = ctx.to_call > ctx.pot * 0.7
    if equity > odds + 0.20:
        return _raise_to(ctx, 0.5)
    if equity >= odds + (0.12 if big_bet else 0.0):
        return Action("check_call")
    return Action("fold")


def beginner_policy(ctx: DecisionContext, equity: float) -> Action:
    odds = tools.pot_odds(ctx.pot, ctx.to_call)
    if ctx.street == "preflop":
        if ctx.to_call <= ctx.big_blind:         # passive: limp playable hands
            return Action("check_call")
        if equity >= odds - 0.10:                # call a raise fairly light
            return Action("check_call")
        return Action("fold")
    # postflop: loose calling-station, but folds clear air to a big bet.
    if ctx.to_call == 0:
        return _raise_to(ctx, 0.5) if equity > 0.58 else Action("check_call")
    big_bet = ctx.to_call > ctx.pot * 0.8
    threshold = odds if big_bet else odds - 0.12
    return Action("check_call") if equity >= threshold else Action("fold")


def apply_style(base: Action, ctx: DecisionContext, equity: float,
                arch, rng: random.Random) -> Action:
    # Aggression: occasionally upgrade a call/check into a (value) raise.
    if base.kind == "check_call" and rng.random() < arch.aggression * 0.25:
        return _raise_to(ctx, 0.5)
    # Bluff: occasionally turn a fold into a tagged bluff-raise on weak equity.
    if base.kind == "fold" and rng.random() < arch.bluff_freq * 0.5 and equity < 0.30:
        return _raise_to(ctx, 0.5, tag="bluff")
    return base
