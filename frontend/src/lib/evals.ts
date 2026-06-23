/**
 * Pure eval-panel logic: resolve each seeded case's *computed* score from the
 * frozen score files, judge it against the answer key's *expected* category, and
 * rank true-risk cases above false-positive traps. Kept out of the view so the
 * "does the engine agree with ground truth" measurement is unit-testable.
 */
import type {
  EvalSummary,
  HealthScoresFile,
  IntegrityScoresFile,
  SeededCase,
} from '../data/types'

export interface Predicted {
  lens: SeededCase['expected_risk_lens']
  /** The computed band, or null when the case's entity isn't scored. */
  band: string | null
  /** Human detail for the cell, e.g. "health 38 · T-22" or "cluster CL-001 · convergence 3". */
  detail: string
}

const GROUP_KEYS = ['cluster_id', 'household_id', 'group_id', 'overlap_id', 'account_group'] as const

function groupId(entities: SeededCase['seeded_entities']): string | undefined {
  for (const key of GROUP_KEYS) {
    const value = entities[key]
    if (typeof value === 'string') return value
  }
  return undefined
}

/** Look up the engine's computed score for a case in the appropriate score file. */
export function resolvePredicted(
  c: SeededCase,
  health: HealthScoresFile,
  integrity: IntegrityScoresFile,
): Predicted {
  if (c.expected_risk_lens === 'table_health') {
    const tableId = typeof c.seeded_entities.seeded_table_label === 'string'
      ? c.seeded_entities.seeded_table_label
      : ''
    const row = health.health_scores.find((h) => h.table_id === tableId)
    return row
      ? { lens: 'table_health', band: row.band, detail: `health ${row.health.toFixed(0)} · ${tableId}` }
      : { lens: 'table_health', band: null, detail: tableId ? `${tableId} not scored` : 'no table seeded' }
  }

  const gid = groupId(c.seeded_entities)
  const assessment = integrity.assessments.find((a) => a.group_id === gid)
  return assessment
    ? {
        lens: 'integrity_risk',
        band: assessment.band,
        detail: `${assessment.group_kind} ${assessment.group_id} · convergence ${assessment.convergence_count}`,
      }
    : { lens: 'integrity_risk', band: null, detail: gid ? `${gid} not scored` : 'no group seeded' }
}

/**
 * Which computed bands satisfy each expected category. Operator-facing semantic
 * map: a `high` integrity band satisfies "integrity_review"; a `neutral`/`low`
 * band satisfies a "monitor" expectation (not escalated); a `beginner_unfriendly`
 * health band matches its like-named category.
 */
const SATISFIES: Record<string, string[]> = {
  beginner_unfriendly: ['beginner_unfriendly'],
  integrity_review: ['high', 'manual_review'],
  monitor_low: ['neutral', 'low'],
  monitor_low_medium: ['neutral', 'low'],
  room_health_concern: ['fragile', 'beginner_unfriendly'],
}

export function satisfiesExpected(expectedCategory: string, band: string | null): boolean {
  if (!band) return false
  return SATISFIES[expectedCategory]?.includes(band) ?? false
}

/** Split into true-risk-first then traps, preserving each list's order in the summary. */
export function splitByRisk(
  cases: SeededCase[],
  summary: EvalSummary,
): { trueRisk: SeededCase[]; traps: SeededCase[] } {
  const byId = new Map(cases.map((c) => [c.case_id, c]))
  const pick = (ids: string[]) => ids.map((id) => byId.get(id)).filter((c): c is SeededCase => Boolean(c))
  return { trueRisk: pick(summary.true_risk_cases), traps: pick(summary.false_positive_traps) }
}

/** Readable label from a snake_case key/check string. */
export function humanize(text: string): string {
  return text.replace(/_/g, ' ')
}
