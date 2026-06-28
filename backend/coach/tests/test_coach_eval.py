"""Coach eval tests.

Two tiers:
* DETERMINISTIC (offline, no network) -- the golden set is well-formed, the summary
  assembler resolves the opponent read from leaks.py, the guardrails catch banned
  language, and the mechanical grader catches a wrong/missing equity citation. These
  are the Stop-gate-safe checks and they go green as soon as the grader is correct.
* LIVE (the dominant oracle) -- run the real coach over the golden set and require
  every fixture to pass the judge. Skipped without ANTHROPIC_API_KEY; this is the
  RED-until-built-green check the make-or-break rides on. Run on demand:
      python -m coach.eval --model claude-sonnet-4-6
"""

import os

import pytest

from coach.guardrails import check_coaching
from coach.eval import grade_mechanical
from coach.summary import build_summary, load_golden

GOLDEN = {h["hand_id"]: h for h in load_golden()}


def _coaching(equity, *, verdict="mistake",
              tell="they barrel a value-heavy range and rarely back off",
              better="fold to the sustained barrel", why="against this player's "
              "value-weighted betting range your hand is behind far more than the raw "
              "number suggests",
              headline="Fold -- your hand only beats bluffs against this opponent."):
    """A minimal, schema-valid coaching note for grader tests."""
    return {
        "headline": headline,
        "opponent_read": {"seat": 3, "style_label": "grinder / TAG", "tell": tell},
        "decisions": [{
            "street": "river", "your_action": "call 16bb", "equity_pct": equity,
            "verdict": verdict, "why_this_play": why, "better_line": better,
        }],
        "summary": "Fold to sustained aggression from a disciplined player.",
    }


# ----------------------------------------------------------- golden set shape ---
def test_golden_set_is_well_formed():
    hands = load_golden()
    assert len(hands) == 7
    ids = {h["hand_id"] for h in hands}
    assert ids == {"G1-station-value", "G2-maniac-calldown", "G3-nit-steal",
                   "G4-solver-bluff", "G5-grinder-fold", "G6-well-played-fold",
                   "G7-multiway-3bet-fold"}
    for h in hands:
        assert h["decisions"] and h["rubric"]["must_cite_equity_pct"] > 0
        assert h["decisive_opponent"]["archetype"]


def test_grader_rejects_fabricated_mistake_on_well_played_hand():
    g6 = GOLDEN["G6-well-played-fold"]
    # calling a correct play a "mistake" must fail; affirming it ("good") is clean
    assert grade_mechanical(_coaching(15.2, verdict="mistake"), g6)
    assert grade_mechanical(_coaching(15.2, verdict="good"), g6) == []


def test_build_summary_resolves_the_leak():
    summary = build_summary(GOLDEN["G5-grinder-fold"])
    opp = summary["decisive_opponent"]
    assert opp["style_label"] == "grinder / TAG"
    assert len(opp["leak"]) > 15          # the named leak is carried through
    assert opp["tendencies"]["bluff_pct"] == 14   # transcribed from knobs (bluff=0.14)
    # equity stays frozen from the fixture
    assert summary["decisions"][0]["hero_equity_pct"] == 68.8


# ------------------------------------------------------------- mechanical grade ---
def test_grader_passes_when_equity_is_cited():
    assert grade_mechanical(_coaching(68.8), GOLDEN["G5-grinder-fold"]) == []
    assert grade_mechanical(_coaching(66.0), GOLDEN["G5-grinder-fold"]) == []  # within tol


def test_grader_flags_wrong_or_missing_equity():
    assert grade_mechanical(_coaching(40.0), GOLDEN["G5-grinder-fold"])      # too far off
    assert grade_mechanical(None, GOLDEN["G5-grinder-fold"])                 # no coaching


# ---------------------------------------------------------------- guardrails ---
def test_guardrails_catch_real_money_and_gto():
    assert check_coaching(_coaching(68.8)) == []
    assert any("real-money" in v for v in check_coaching(_coaching(68.8, why="withdraw your winnings to bank the equity edge")))
    assert any("GTO" in v for v in check_coaching(_coaching(68.8, headline="This is the GTO play.")))


# -------------------------------------------------------------- live oracle ---
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"),
                    reason="live coach eval requires ANTHROPIC_API_KEY")
def test_live_coach_passes_golden_set():
    from coach.eval import run_eval
    report = run_eval(model="claude-sonnet-4-6")
    failing = [r["hand_id"] for r in report["results"] if not r["passed"]]
    assert report["passed"], f"coach failed on: {failing}"
