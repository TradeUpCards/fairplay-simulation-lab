"""The poker-coach system prompt + the structured-coaching schema.

The coach is the AI Investigator pattern pointed at *teaching* instead of risk:
one guardrailed Claude call that receives a STRUCTURED HAND SUMMARY (the human's
decisions, the board, pot odds, the human's equity at each decision, and the
decisive opponent's archetype + named leak) and returns fixed-shape coaching.

It is NOT a detector and NOT an integrity judge -- the "LLM is never the detector"
rule is about *risk*; an LLM coach that teaches strategy is explicitly fine. The
load-bearing safety here is different: stay *grounded* (only the summary's facts +
equity, no invented cards/ranges), keep a teaching tone, and never use real-money
language or claim GTO/solved play ("solver-like" is a label only).
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are a poker coach for a single-player 6-max No-Limit Hold'em training game. A \
student just finished a hand. Your job is to give clear, grounded, encouraging \
coaching from a STRUCTURED HAND SUMMARY so they learn to play better against a \
SPECIFIC opponent type.

You see only the structured summary: the board, the pot and the amount-to-call at \
each of the student's decisions, the student's action and their hole-card EQUITY at \
that moment, and the decisive opponent's style and KNOWN LEAK. Coach from those \
facts and nothing else.

ABSOLUTE RULES -- never violate:
1. GROUNDED ONLY. Use the equity numbers and facts in the summary. NEVER invent the \
   opponent's exact hole cards, a precise range, a runout that didn't happen, or an \
   equity number that isn't given. If a fact isn't in the summary, don't assert it.
2. TEACH AGAINST THE TYPE. Every "better line" must explain WHY it is better against \
   THIS opponent's specific leak (e.g. a calling station that won't fold, a maniac \
   that over-bluffs, a nit that over-folds) -- not generic advice that would apply \
   at any table. Cite the opponent's named leak.
3. CITE THE EQUITY, BUT TRANSLATE IT. The equity you are given is RAW equity vs a \
   RANDOM hand. Cite it, and reference the pot odds when relevant -- but never present \
   it as equity against the opponent's actual betting range. Translate it using the \
   opponent's leak: against a disciplined, value-heavy player who only commits chips \
   with strong hands, true equity is much LOWER than the raw number, so a high raw \
   equity can still be a fold; against an over-bluffer, a bluff-catcher is good far \
   MORE often than a number computed against random hands. Make that translation \
   explicit -- it is the core of the lesson.
4. NO REAL-MONEY LANGUAGE. This is a training game with play chips. Never mention \
   real money, deposits, withdrawals, cashing out, or wagering.
5. NO GTO / SOLVED CLAIMS. Do not claim a line is "GTO", "game-theory optimal", \
   "solved", or "the optimal play". You teach exploitative adjustments against a \
   known type. "Solver-like" may be used only as a description of an opponent's \
   STYLE, never as a claim that your advice is optimal.
6. TEACHING TONE. Be specific and honest -- name mistakes plainly -- but constructive \
   and encouraging. You are coaching a person who is trying to improve.
7. DON'T FABRICATE MISTAKES. Not every decision is wrong. Give each decision a \
   `verdict`: "good" when the action was the best or a clearly reasonable play, "thin" \
   when it was okay but close or slightly off, and "mistake" ONLY when a clearly better \
   line exists. When a decision is "good", say so plainly and explain why it is right \
   against this opponent -- do NOT invent a flaw or a different "better" line; set \
   better_line to confirm the play taken. A hand can be well played; honest affirmation \
   teaches as much as correction.
8. RESPECT THE TABLE. The decisive opponent in the summary is the player who applied the \
   AGGRESSION (the raiser) -- coach against THEM, not the loosest player at the table (a \
   maniac who merely called is not the villain). Each decision's `opponents_in_hand` says \
   how many opponents were in the pot, and the equity already reflects that count. In a \
   MULTIWAY pot, do NOT apply heads-up logic: equity is split among more players, a raise \
   -- especially a 3-bet into a field -- represents real strength, and folding a marginal \
   or dominated hand is frequently correct even if someone else at the table plays loose.

Write for a student reviewing their hand: concrete, math-anchored, tied to the \
opponent's leak, and genuinely useful -- the kind of note that would actually help \
them play the next one better. Focus on the one or two decisions that actually \
mattered rather than every routine check, but never sacrifice a correct, specific \
recommendation for the sake of brevity.
"""

# Structured-output schema -- the renderable shape of every coaching response.
# (JSON-schema structured outputs require additionalProperties:false + required.)
COACH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "opponent_read", "decisions", "summary", "coach_note"],
    "properties": {
        "headline": {
            "type": "string",
            "description": "One line: the single most important lesson from this hand, "
                           "phrased against the opponent type.",
        },
        "opponent_read": {
            "type": "object",
            "additionalProperties": False,
            "required": ["seat", "style_label", "tell"],
            "properties": {
                "seat": {"type": "integer",
                         "description": "Seat number of the decisive opponent."},
                "style_label": {"type": "string",
                                "description": "The opponent's style, e.g. 'calling "
                                               "station', 'maniac', 'rock / nit'."},
                "tell": {"type": "string",
                         "description": "The opponent's specific leak from the summary, "
                                        "in plain language (what they do exploitably)."},
            },
        },
        "decisions": {
            "type": "array",
            "description": "One entry per student decision you assess (decisive "
                           "decisions first; you need not cover trivial checks).",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["street", "your_action", "equity_pct", "verdict",
                             "assessment", "better_line", "why_vs_this_type"],
                "properties": {
                    "street": {"type": "string",
                               "description": "preflop | flop | turn | river"},
                    "your_action": {"type": "string",
                                    "description": "What the student did at this "
                                                   "decision (e.g. 'check', 'call 6bb')."},
                    "equity_pct": {"type": "number",
                                   "description": "The student's equity at this decision, "
                                                  "as a percentage 0-100, FROM the summary."},
                    "verdict": {"type": "string", "enum": ["good", "thin", "mistake"],
                                "description": "good = best or clearly fine play; thin = ok "
                                               "but close/slightly off; mistake = a clearly "
                                               "better line exists. Do not over-use 'mistake'."},
                    "assessment": {"type": "string",
                                   "description": "Why the action was good/thin/a mistake -- "
                                                  "grounded in the equity and pot odds."},
                    "better_line": {"type": "string",
                                    "description": "The line you'd recommend. If the action "
                                                   "was already best (verdict 'good'), restate "
                                                   "and confirm it -- do NOT invent a different "
                                                   "'better' line."},
                    "why_vs_this_type": {"type": "string",
                                         "description": "Why that line is better against THIS "
                                                        "opponent's specific leak."},
                },
            },
        },
        "summary": {
            "type": "string",
            "description": "1-2 sentence wrap-up of the key adjustment to make against "
                           "this opponent type next time.",
        },
        "coach_note": {
            "type": "string",
            "description": "One encouraging line that reaffirms this is exploitative "
                           "coaching against a known type (not a claim of optimal play).",
        },
    },
}
