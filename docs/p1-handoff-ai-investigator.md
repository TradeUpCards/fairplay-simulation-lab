# P1 Handoff — wiring the AI Investigator into the pit-boss UI

**To:** P1 (frontend / product flow).
**From:** P3 / P4 (this checkout).
**TL;DR:** the AI Investigator (P4) now exists and its output is **frozen JSON** in
`data/derived/`. Your job is to render it in the **pit-boss case detail** (and the
eval panel) using the exact `data/derived/*.json` import pattern you already use.
**No API key, no live call, no backend** — it's static JSON like the other derived
files. This is the demo's headline moment: *the AI builds the case; the human judges it.*

---

## What's new — two derived files

| File | What it is | Produced by |
|---|---|---|
| `data/derived/case_summaries.json` | One AI-written case summary per seeded case (A–G) — the "AI summary" the PRD pit-boss console calls for. | P4 AI Investigator |
| `data/derived/case_evals.json` | Per-case, per-criterion pass/fail grading those summaries (grounded · no-overclaiming · human-action · counter-evidence · lens · outcome). | P4 eval rubric |

Both are **operator-facing only** — same trust boundary as `integrity_scores.json`.
**Never** surface any of this in the player lobby.

---

## `case_summaries.json` shape

```jsonc
{
  "meta": { "model": "claude-opus-4-8", "count": 7, "any_guardrail_violation": false, ... },
  "summaries": [
    {
      "case_id": "CASE-C",
      "case_type": "integrity_risk",          // table_health_risk | integrity_risk | promo_abuse | bot_account
      "model": "claude-opus-4-8",
      "stop_reason": "end_turn",
      "guardrail_violations": [],               // always [] for a shippable summary
      "summary": {
        "headline": "Elevated for review — possible coordinated cluster (CL-001)",
        "assessment": "Four convergent signals across cluster CL-001 …",
        "key_signals": ["shared device link", "session-timing correlation 0.88", …],
        "counter_evidence": "No single signal alone proves coordination …",
        "uncertainty": "Simulated fields on synthetic data — not real device telemetry …",
        "recommended_action": "Hold for pit-boss review: a human should examine …",
        "reviewer_note": "I cannot and do not conclude wrongdoing — a human decides."
      }
    }
    // … 7 total: CASE-A … CASE-G
  ]
}
```

`summary` is **always these 7 fields** (enforced by a JSON schema + a guardrail
gate at build time), so you can render them with a fixed layout. If
`summary` is `null` (model refused — won't happen for these 7), fall back to the
structured scorecard.

## `case_evals.json` shape

```jsonc
{
  "eval_summary": { "total": 7, "passed": 7,
    "by_criterion": { "grounded_no_hallucinated_entities": "7/7", "outcome_aligned": "7/7", … } },
  "evals": [
    { "case_id": "CASE-C", "prd_scenario": "C", "passed": true,
      "criteria": { "grounded_no_hallucinated_entities": {"pass": true, "detail": "…"}, … } }
  ]
}
```

---

## How to wire it (your existing pattern)

You already import derived JSON at build time in `frontend/src/data/shim.ts`. Add
two more the same way:

```ts
// frontend/src/data/shim.ts
import caseSummariesRaw from '@data/derived/case_summaries.json'
import caseEvalsRaw     from '@data/derived/case_evals.json'

export async function loadCaseSummaries(): Promise<CaseSummariesFile> {
  return caseSummariesRaw as CaseSummariesFile
}
export async function loadCaseEvals(): Promise<CaseEvalsFile> {
  return caseEvalsRaw as CaseEvalsFile
}
```

Add the types alongside your other `*File` types (`frontend/src/data/types.ts`):

```ts
export interface CaseSummary {
  headline: string
  assessment: string
  key_signals: string[]
  counter_evidence: string
  uncertainty: string
  recommended_action: string
  reviewer_note: string
}
export interface CaseSummaryRow {
  case_id: string
  case_type: 'table_health_risk' | 'integrity_risk' | 'promo_abuse' | 'bot_account'
  summary: CaseSummary | null
  guardrail_violations: string[]
}
export interface CaseSummariesFile { meta: Record<string, unknown>; summaries: CaseSummaryRow[] }
// CaseEvalsFile: { eval_summary: {...}; evals: Array<{case_id; passed; criteria: Record<string,{pass:boolean;detail:string}>}> }
```

### Joining a summary to the case the operator is looking at

A summary is keyed by `case_id` (`CASE-A … CASE-G`). Your case detail is keyed by
a table or group (e.g. integrity case `CL-001`, table `T-22`). Join through
`seeded_case_labels.json` (you already load it via `loadSeededCases`):

```
seeded case CASE-C  →  seeded_entities.cluster_id === "CL-001"   (the integrity group you're showing)
                    →  case_summaries["CASE-C"].summary
```

So: from the group/table on screen → find the seeded case whose `seeded_entities`
contains it → look up the summary by that `case_id`. (Equivalently, each summary's
`subjects.entities` in the packet carries the same IDs if you prefer matching there.)

---

## Where to render it

1. **Pit-boss case detail** (`IntegrityCase.tsx` / `PitBossTable.tsx`) — add an
   **"AI summary"** block. Suggested layout, top to bottom:
   - `headline` (the neutral one-liner — this is the case title)
   - `assessment` (the paragraph)
   - `key_signals` (chips/list)
   - `counter_evidence` (own block, visually distinct — this is load-bearing for the thesis)
   - `uncertainty` (muted caption)
   - `recommended_action` (call-to-action, but advisory)
   - `reviewer_note` (small footer, always visible)
2. **Eval panel** (`EvalPanel.tsx`) — add rows from `case_evals.json`: per case, the
   6 criteria pass/fail + the overall. This is the "is the AI trustworthy?" beat.

---

## Guardrail framing — please keep these (they're the whole point)

- **Label it as an AI summary and as advice.** It recommends; the operator decides.
  Keep the existing operator actions (accept / override / monitor / suppress /
  escalate). The summary's `recommended_action` is a suggestion, not a button.
- **Always render `counter_evidence`, `uncertainty`, and `reviewer_note`** — don't
  collapse the summary to just the headline. Surfacing counter-evidence and
  deferring to a human is the demonstrable safety story.
- **Never render any of this in the player lobby.** Operator console only.
- The summaries already contain **no raw player data and no verdict/enforcement
  language** (guardrail-gated), so you can render the text verbatim.

---

## Regenerating (FYI — you don't need to)

The summaries are frozen. If P3/P4 ever needs to regenerate them (e.g. after a
packet change), it's `ANTHROPIC_API_KEY=… python backend/scripts/build_summaries.py`
then `python backend/scripts/build_evals.py` — both rewrite the `data/derived/*.json`
you import. You consume the committed output; you never call the model.

Questions → ping P3/P4.
