/**
 * Pure table-health helpers for the operator console — kept out of the view so
 * the ranking is unit-testable and provably data-driven (not hard-coded order).
 */
import type { HealthBand } from '../data/types'

/** Shared chip box (size/shape); `tone` supplies the band's colour trio. */
export const BAND_CHIP = 'rounded-full border px-2 py-[0.15rem] text-[0.72rem]'

export const BAND_META: Record<HealthBand, { label: string; tone: string; range: string }> = {
  healthy: { label: 'Healthy', tone: 'border-[#2f7d4a] bg-[#16341f] text-[#8be3a7]', range: '70–100' },
  fragile: { label: 'Fragile', tone: 'border-[#8a7a2f] bg-[#33301a] text-[#e3d28b]', range: '50–69' },
  beginner_unfriendly: {
    label: 'Beginner-unfriendly',
    tone: 'border-[#8a5f2f] bg-[#3a2a1a] text-[#efc28f]',
    range: '30–49',
  },
  collapsed: { label: 'Collapsed', tone: 'border-[#8a2f3f] bg-[#3a1a1f] text-[#ef8f9b]', range: '0–29' },
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
