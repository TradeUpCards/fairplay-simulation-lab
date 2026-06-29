/**
 * Pure table-health helpers for the operator console — kept out of the view so
 * the ranking is unit-testable and provably data-driven (not hard-coded order).
 */
import type { HealthBand } from '../data/types'

/** Shared chip box (size/shape); `tone` supplies the band's colour trio. */
export const BAND_CHIP = 'rounded-full border px-2 py-[0.15rem] text-[0.72rem]'

/** Just the band's accent colour — for the big health score number (operator views).
 *  A clear traffic-light progression so the four bands read distinctly at a glance. */
export const BAND_TEXT: Record<HealthBand, string> = {
  healthy: 'text-[#3fd07a]', // green
  fragile: 'text-[#ffd23f]', // yellow
  beginner_unfriendly: 'text-[#ff8a3d]', // orange
  collapsed: 'text-[#ff4d4d]', // red
}

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

/** The four penalty terms, in display order. */
export const TERM_ORDER: TermKey[] = ['P_pred', 'P_frag', 'P_clus', 'P_bleed']

export interface TermMeta {
  label: string
  /** What this metric measures — the (i) tooltip copy. */
  explain: string
  /** What the current value says about *this* table — the score tooltip copy. */
  reads: (value: number) => string
}

/** value → severity bucket relative to the term's cap. */
function severity(value: number, cap: number): 'none' | 'low' | 'moderate' | 'high' {
  if (value <= 0) return 'none'
  const pct = cap > 0 ? value / cap : 0
  if (pct < 0.25) return 'low'
  if (pct < 0.6) return 'moderate'
  return 'high'
}

/** Definitions + value interpretation per term, grounded in scoring/health.py. */
export const TERM_META: Record<TermKey, TermMeta> = {
  P_pred: {
    label: 'Predation',
    explain:
      'Skill-weighted aggressors measured against the vulnerable pool at the table. One strong player among recreationals is tolerable; several — especially short-handed — compounds quickly.',
    reads: (v) =>
      `${v} of ${TERM_CAP.P_pred} — ${{
        none: 'no aggressors are leaning on this table.',
        low: 'light predatory pressure; the mix still favors recreational play.',
        moderate: 'noticeable predatory pressure on the softer seats.',
        high: 'heavy predatory pressure — strong players are dominating the vulnerable pool.',
      }[severity(v, TERM_CAP.P_pred)]}`,
  },
  P_frag: {
    label: 'Fragility',
    explain:
      'How exposed the table is to breaking up. Rises as seats empty and as paid-seat-time stalls or trends down — a thin, fading table concentrates the risk.',
    reads: (v) =>
      `${v} of ${TERM_CAP.P_frag} — ${{
        none: 'well-occupied with steady paid-seat-time.',
        low: 'mostly full; little breakage risk.',
        moderate: 'thinning out or paid-seat-time stalling.',
        high: 'short-handed and fading — at real risk of breaking up.',
      }[severity(v, TERM_CAP.P_frag)]}`,
  },
  P_clus: {
    label: 'Cluster',
    explain:
      'Active-cluster severity: the integrity band of any flagged coordination cluster seated here, scaled by the share of seats it holds. A health signal about who is seated together — not an accusation.',
    reads: (v) =>
      `${v} of ${TERM_CAP.P_clus} — ${{
        none: 'no flagged cluster is seated here.',
        low: 'a low-band cluster is present — monitor, not escalated.',
        moderate: 'a flagged cluster holds a meaningful share of the seats.',
        high: 'a high-band cluster dominates the seats — elevated for review.',
      }[severity(v, TERM_CAP.P_clus)]}`,
  },
  P_bleed: {
    label: 'Bleed',
    explain:
      'Observed recreational truncation: realized new/recreational sessions at this table that ended well below their baseline. 0 in the static snapshot — the simulator populates it as sessions play out.',
    reads: (v) =>
      `${v} of ${TERM_CAP.P_bleed} — ${{
        none: 'no observed recreational truncation (expected in the static snapshot).',
        low: 'minor early exits among recreational players.',
        moderate: 'recreational sessions ending notably short.',
        high: 'recreational players bleeding out early — poor retention.',
      }[severity(v, TERM_CAP.P_bleed)]}`,
  },
}
