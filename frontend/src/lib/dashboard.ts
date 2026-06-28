/**
 * Pure helpers for the sweep dashboard — policy identity, cell lookup, regime
 * advantage/colour, default-cell selection, fractional-index interpolation for
 * the animation, and CSV export. Kept dependency-free and side-effect-free so
 * the view stays thin and these are unit-testable without a DOM.
 */
import type { SweepCell, SweepDataset, TimeseriesCell, TimeseriesDataset } from '../data/types'

export const BASELINE_POLICY = 'standard'

/** Line colours reuse the simulator's Standard(warm)/FairPlay(cool) pair; the
 * liveness arm gets a felt-green so all three read apart. */
const POLICY_COLORS: Record<string, string> = {
  standard: '#d98c5f',
  fairplay: '#8aa0b8', // plain route — not shown in the current dashboard
  fairplay_liveness: '#5fb0d9', // shown AS "FairPlay"
}
const POLICY_LABELS: Record<string, string> = {
  standard: 'Standard',
  fairplay: 'FairPlay-route',
  fairplay_liveness: 'FairPlay', // the liveness arm is the dashboard's "FairPlay"
}

export const colorOf = (policy: string): string => POLICY_COLORS[policy] ?? '#9aa2b3'
export const policyLabel = (policy: string): string =>
  POLICY_LABELS[policy] ?? policy.replace(/_/g, ' ')

// The dashboard surfaces only Standard and the liveness arm (relabelled "FairPlay").
export const CANDIDATE_POLICY = 'fairplay_liveness'
export const DISPLAY_POLICIES = ['standard', 'fairplay_liveness']

// Distinct hues so each regime's pair of lines reads apart on the multi-line chart.
export const REGIME_COLORS = [
  '#5fb0d9', '#d98c5f', '#7bd88f', '#c79a4b', '#b98cd9', '#e0697f', '#6fd0c0', '#cdbf6a',
]
export const regimeColor = (i: number): string => REGIME_COLORS[i % REGIME_COLORS.length]
export const regimeLabel = (tables: number | null, rate: number): string => `${tables}t · ${rate}/hr`

/** Metrics the heatmap can colour by (both have per-seed stability vs baseline). */
export const ADVANTAGE_METRICS = [
  { key: 'total_paid_seat_hours', label: 'Total seat-hrs' },
  { key: 'vulnerable_paid_seat_hours', label: 'Vulnerable seat-hrs' },
] as const

/**
 * Descriptive terminal-departure buckets for the per-regime context panel.
 * NOT a comparison metric: counts are flat across routing arms (FairPlay's edge
 * is session duration, not who leaves), so this characterises the room rather
 * than ranking the policy. `cohortKey` is the vulnerable-player subset of each.
 */
export const DEPARTURE_BUCKETS = [
  {
    key: 'left_satisfied_count',
    cohortKey: 'cohort_left_satisfied_count',
    label: 'Left satisfied',
    hint: 'planned exit — hit a profit target or time budget',
  },
  {
    key: 'left_damaged_count',
    cohortKey: 'cohort_left_damaged_count',
    label: 'Left tilted / busted',
    hint: 'left after a losing, tilted session',
  },
  {
    key: 'couldnt_seat_count',
    cohortKey: 'cohort_couldnt_seat_count',
    label: 'Couldn’t seat',
    hint: 'never seated or gave up waiting — only fires when the room is saturated',
  },
] as const

/** Chart metrics (the animation can also show the live active-table count). */
export const CHART_METRICS = [
  { key: 'total_paid_seat_hours', label: 'Total paid seat-hrs', unit: 'hrs' },
  { key: 'vulnerable_paid_seat_hours', label: 'Vulnerable seat-hrs', unit: 'hrs' },
  { key: 'active_tables', label: 'Active tables', unit: '' },
] as const

export const cellKey = (cell: { tables: number | null; rate: number }): string =>
  `${cell.tables}|${cell.rate}`

/** Find the time-series cell matching a regime by numeric identity (the JSON key
 * uses Python float formatting like "50|40.0", so don't string-compare keys). */
export function findTimeseriesCell(
  ts: TimeseriesDataset | undefined,
  tables: number | null,
  rate: number,
): TimeseriesCell | undefined {
  if (!ts) return undefined
  return Object.values(ts.cells).find((c) => c.tables === tables && c.rate === rate)
}

/** FairPlay − Standard on one metric for a cell (the heatmap's signed value). */
export function advantage(
  cell: SweepCell,
  metricKey: string,
  candidate = 'fairplay',
  baseline = BASELINE_POLICY,
): number | null {
  const cand = cell.means[candidate]?.[metricKey]
  const base = cell.means[baseline]?.[metricKey]
  if (cand == null || base == null) return null
  return Math.round((cand - base) * 1000) / 1000
}

/** Non-baseline policies a cell can be scored against (the heatmap candidates). */
export function candidatePolicies(dataset: SweepDataset): string[] {
  return dataset.policies.filter((p) => p !== BASELINE_POLICY)
}

/** Largest |advantage| across a dataset's cells — the heatmap colour-scale max. */
export function maxAbsAdvantage(
  dataset: SweepDataset,
  metricKey: string,
  candidate = 'fairplay',
): number {
  let m = 0
  for (const cell of dataset.cells) {
    const d = advantage(cell, metricKey, candidate)
    if (d != null) m = Math.max(m, Math.abs(d))
  }
  return m
}

/** Green = FairPlay ahead, red = behind; alpha scales with magnitude. */
export function heatColor(delta: number | null, maxAbs: number): string {
  if (delta == null || maxAbs === 0) return 'rgba(120,130,150,0.10)'
  const t = Math.max(-1, Math.min(1, delta / maxAbs))
  const alpha = (0.14 + 0.5 * Math.abs(t)).toFixed(3)
  return t >= 0 ? `rgba(95,176,121,${alpha})` : `rgba(201,93,93,${alpha})`
}

/** Default the hero to the most candidate-favourable regime (the cell with the
 * largest positive advantage on the metric); fall back to the first cell. */
export function pickDefaultCell(
  dataset: SweepDataset,
  metricKey: string,
  candidate = 'fairplay',
): SweepCell | undefined {
  if (dataset.cells.length === 0) return undefined
  let best = dataset.cells[0]
  let bestDelta = advantage(best, metricKey, candidate) ?? -Infinity
  for (const cell of dataset.cells) {
    const d = advantage(cell, metricKey, candidate)
    if (d != null && d > bestDelta) {
      best = cell
      bestDelta = d
    }
  }
  return best
}

/** Value of a series at a fractional index p (linear interp). Empty → 0. */
export function interpAt(arr: number[], p: number): number {
  if (arr.length === 0) return 0
  if (p <= 0) return arr[0]
  if (p >= arr.length - 1) return arr[arr.length - 1]
  const i = Math.floor(p)
  const frac = p - i
  return arr[i] + (arr[i + 1] - arr[i]) * frac
}

export const formatHrMin = (hours: number): string => {
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return m === 0 ? `${h}h` : `${h}h ${String(m).padStart(2, '0')}m`
}

/** A small, dependency-free CSV of the dataset's per-seed runs for download. */
export function toCsv(dataset: SweepDataset): string {
  const cols = ['tables', 'rate', 'policy', 'seed', ...dataset.metrics.map((m) => m.key)]
  const rows: string[] = [cols.join(',')]
  for (const cell of dataset.cells) {
    for (const run of cell.runs) {
      const line = [
        cell.tables ?? '',
        cell.rate,
        run.policy,
        run.seed,
        ...dataset.metrics.map((m) => run[m.key] ?? ''),
      ]
      rows.push(line.join(','))
    }
  }
  return rows.join('\n')
}
