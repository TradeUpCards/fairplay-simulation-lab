/**
 * Pure table-health helpers for the operator console — kept out of the view so
 * the ranking is unit-testable and provably data-driven (not hard-coded order).
 */
import type { HealthBand } from '../data/types'

export const BAND_META: Record<HealthBand, { label: string; tone: string; range: string }> = {
  healthy: { label: 'Healthy', tone: 'band-healthy', range: '70–100' },
  fragile: { label: 'Fragile', tone: 'band-fragile', range: '50–69' },
  beginner_unfriendly: { label: 'Beginner-unfriendly', tone: 'band-beginner', range: '30–49' },
  collapsed: { label: 'Collapsed', tone: 'band-collapsed', range: '0–29' },
}

/**
 * Healthiest-first. Generic over `{ health }` so tests can drive it with plain
 * objects; production passes `HealthScore[]`. A stable sort keeps ties in input
 * order, so the ordering is deterministic.
 */
export function rankTables<T extends { health: number }>(scores: readonly T[]): T[] {
  return [...scores].sort((a, b) => b.health - a.health)
}

/** Penalty-term caps (contract2.d.ts), used to scale the per-term mini-bars. */
export const TERM_CAP = { P_pred: 45, P_frag: 25, P_clus: 30, P_bleed: 20 } as const
export type TermKey = keyof typeof TERM_CAP
