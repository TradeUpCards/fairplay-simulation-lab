"""The coaching-quality eval -- the dominant oracle for the training coach.

Two layers, deliberately separated:

* ``grade_mechanical`` -- DETERMINISTIC, offline. The unambiguous checks: the
  guardrails held, and the coaching actually cited the decision's equity number.
  Cheap and fast; safe for a recorded-output Stop-gate smoke.
* ``judge_coaching`` -- an LLM-as-judge for the SEMANTIC verdict no string match can
  settle: did the coaching recommend the type-correct line (not the trap line), name
  the opponent's specific leak, and satisfy the fixture's special requirements (frame
  a bluff-catcher, reconcile raw-equity-vs-range, avoid a GTO claim)? Live / on-demand.

``run_eval`` ties them together over the golden set and is the make-or-break gate:
a fixture passes iff the mechanical checks are clean AND the judge passes it. The
coach model under test defaults to Sonnet; ``--model claude-haiku-4-5`` sweeps Haiku.
The judge defaults to the strongest model so the examiner out-classes the coachee.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .coach import MODEL as COACH_MODEL, coach_hand
from .leaks import read_for
from .summary import build_summary, load_golden

JUDGE_MODEL = "claude-opus-4-8"


# ---------------------------------------------------------------- mechanical ---
def grade_mechanical(coaching: dict[str, Any] | None,
                     fixture: dict[str, Any]) -> list[str]:
    """Deterministic failures (empty list == clean). Does NOT judge correctness --
    only the unambiguous, machine-checkable requirements."""
    if not coaching:
        return ["no coaching produced (refusal or parse failure)"]
    rubric = fixture["rubric"]
    fails: list[str] = []

    target = float(rubric["must_cite_equity_pct"])
    tol = float(rubric.get("equity_tolerance", 5.0))
    cited = [d.get("equity_pct") for d in coaching.get("decisions", [])
             if isinstance(d.get("equity_pct"), (int, float))]
    if not any(abs(float(e) - target) <= tol for e in cited):
        fails.append(f"did not cite the decision equity ~{target}% (got {cited or 'none'})")

    verdicts = [d.get("verdict") for d in coaching.get("decisions", [])]
    if rubric.get("must_not_claim_mistake") and "mistake" in verdicts:
        fails.append("called a correctly-played hand a 'mistake' (over-critical)")
    if rubric.get("expected_verdict") and rubric["expected_verdict"] not in verdicts:
        fails.append(f"no decision marked verdict '{rubric['expected_verdict']}' (got {verdicts})")

    return fails


# --------------------------------------------------------------------- judge ---
JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["passes", "reason", "failed_requirements"],
    "properties": {
        "passes": {"type": "boolean",
                   "description": "True only if EVERY listed requirement is met."},
        "reason": {"type": "string",
                   "description": "One or two sentences justifying the verdict."},
        "failed_requirements": {
            "type": "array", "items": {"type": "string"},
            "description": "The exact requirement strings that were NOT met (empty if passes).",
        },
    },
}

JUDGE_SYSTEM = """\
You are a strict poker-coaching examiner. You are given (1) the hand the student \
played, (2) a checklist of REQUIREMENTS a good coaching note must meet for this hand, \
and (3) the coaching note that was produced. Decide whether the note meets EVERY \
requirement. Judge the substance, not the wording -- a requirement is met if the note \
clearly accomplishes it in any phrasing. Be strict: if the note recommends a line the \
requirements forbid, or omits a required point, it FAILS. List each unmet requirement \
verbatim. Do not be swayed by confident tone; only the requirements matter."""


def _requirements(fixture: dict[str, Any]) -> list[str]:
    """Human-readable requirement checklist for the judge, from the fixture rubric +
    the resolved opponent read (single source of truth)."""
    r = fixture["rubric"]
    read = read_for(fixture["decisive_opponent"]["archetype"])
    reqs = [
        f"Recommends the correct line: {r['better_line']}.",
        f"Does NOT recommend any of these (the trap lines): {r['must_not_recommend']}.",
        f"Names this opponent's specific leak ({read.style_label}: {read.leak}).",
    ]
    if r.get("must_frame_as_bluff_catcher"):
        reqs.append("Frames the hero's hand as a bluff-catcher that beats the "
                    "opponent's bluffs (not as a strong made hand).")
    if r.get("must_reconcile_equity_vs_range"):
        reqs.append("Explicitly reconciles the high RAW equity with the recommended "
                    "fold by reasoning about the opponent's actual betting range -- "
                    "not just quoting the raw number.")
    if r.get("must_reference_pot_odds"):
        reqs.append("References the pot odds / the price of the call.")
    if r.get("must_not_claim_gto"):
        reqs.append("Does NOT claim the advice is GTO, optimal, or solved.")
    if r.get("must_affirm"):
        reqs.append("AFFIRMS the student's play as correct: marks the decision 'good' (not a "
                    "mistake), does NOT invent a different 'better' line, and the better_line "
                    "confirms the play actually taken. Explains why the play is right here.")
    return reqs


def judge_coaching(summary: dict[str, Any], fixture: dict[str, Any],
                   coaching: dict[str, Any], *, client: Any,
                   model: str = JUDGE_MODEL) -> dict[str, Any]:
    """LLM-as-judge semantic verdict for one coached hand."""
    reqs = _requirements(fixture)
    user = (
        "HAND THE STUDENT PLAYED:\n```json\n"
        + json.dumps(summary, indent=2) + "\n```\n\n"
        "REQUIREMENTS the coaching note must meet:\n"
        + "\n".join(f"{i+1}. {req}" for i, req in enumerate(reqs))
        + "\n\nCOACHING NOTE produced:\n```json\n"
        + json.dumps(coaching, indent=2) + "\n```\n\n"
        "Does the note meet every requirement?"
    )
    resp = client.messages.create(
        model=model, max_tokens=2000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium",
                       "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return json.loads(text)


# --------------------------------------------------------------------- runner ---
def run_eval(*, model: str = COACH_MODEL, judge_model: str = JUDGE_MODEL,
             client: Any = None) -> dict[str, Any]:
    """Run the coach over the golden set and grade each hand. Returns a report dict;
    ``report['passed']`` is True only if every fixture passes."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    hands = load_golden()
    results: list[dict[str, Any]] = []
    for fixture in hands:
        summary = build_summary(fixture)
        out = coach_hand(summary, client=client, model=model)
        mech = list(out["guardrail_violations"]) + grade_mechanical(out["coaching"], fixture)
        verdict = {"passes": False, "reason": "skipped (no coaching)", "failed_requirements": []}
        if out["coaching"] and not out["guardrail_violations"]:
            verdict = judge_coaching(summary, fixture, out["coaching"],
                                     client=client, model=judge_model)
        passed = (not mech) and bool(verdict["passes"])
        results.append({
            "hand_id": fixture["hand_id"],
            "passed": passed,
            "mechanical_failures": mech,
            "judge_passes": verdict["passes"],
            "judge_reason": verdict["reason"],
            "judge_failed_requirements": verdict.get("failed_requirements", []),
            "coaching": out["coaching"],
        })

    return {
        "model": model,
        "judge_model": judge_model,
        "passed": all(r["passed"] for r in results),
        "n_passed": sum(r["passed"] for r in results),
        "n_total": len(results),
        "results": results,
    }


def _print_report(report: dict[str, Any]) -> None:
    print(f"\nCoach eval  model={report['model']}  judge={report['judge_model']}")
    print(f"{report['n_passed']}/{report['n_total']} hands passed\n")
    for r in report["results"]:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['hand_id']}")
        for f in r["mechanical_failures"]:
            print(f"         mechanical: {f}")
        if not r["judge_passes"]:
            print(f"         judge: {r['judge_reason']}")
            for fr in r["judge_failed_requirements"]:
                print(f"           - unmet: {fr}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the poker-coach quality eval.")
    ap.add_argument("--model", default=COACH_MODEL,
                    help="coach model under test (e.g. claude-sonnet-4-6, claude-haiku-4-5)")
    ap.add_argument("--judge-model", default=JUDGE_MODEL, help="examiner model")
    args = ap.parse_args()
    report = run_eval(model=args.model, judge_model=args.judge_model)
    _print_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
