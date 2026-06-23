/**
 * Pure helpers for the pit-boss table view: seat-ring geometry, per-seat
 * composition, and table→integrity-group resolution. Kept out of the components
 * so the layout and the flag/heat logic are unit-testable.
 */
import type {
  Archetype,
  Classification,
  IntegrityAssessment,
  TableRosterEntry,
} from '../data/types'
import type { PtlResult } from './ptl'

export const ARCHETYPE_LABEL: Record<Archetype, string> = {
  new: 'New',
  recreational: 'Recreational',
  regular: 'Regular',
  grinder: 'Grinder',
  aggressive_predatory: 'Aggressive',
  promo_hunter: 'Promo hunter',
  shared_device_household: 'Household',
  cluster_member: 'Cluster',
  healthy_anchor: 'Anchor',
  bot_like: 'Bot-like',
}

/** PTL heat band. `pending` = U2 not wired yet (neutral); the rest are the plan's thresholds. */
export type PtlTone = 'pending' | 'cool' | 'warm' | 'hot'

export function ptlTone(ptl: number | null | undefined): PtlTone {
  if (ptl == null) return 'pending'
  if (ptl >= 0.7) return 'hot'
  if (ptl >= 0.4) return 'warm'
  return 'cool'
}

export interface SeatInfo {
  index: number
  playerId: string | null
  archetype: Archetype | null
  /** reason_codes[0].detail — the "why this label", surfaced on hover. */
  archetypeWhy?: string
  /** Integrity group this seat's player belongs to, if any (drives the flag ring). */
  flaggedGroupId: string | null
  /** Per-seat PTL 0–1, or null when no PTL was supplied (rendered neutral/pending). */
  ptl: number | null
  /** PTL reason headline (`reason_codes[0].detail`) — the "why this heat", surfaced on hover. */
  ptlWhy?: string
  leftPct: number
  topPct: number
}

/** Even seat positions around an ellipse; seat 0 at bottom-center, going around. */
export function seatPositions(maxSeats: number): { leftPct: number; topPct: number }[] {
  const positions: { leftPct: number; topPct: number }[] = []
  for (let i = 0; i < maxSeats; i += 1) {
    const angle = (Math.PI * 2 * i) / maxSeats + Math.PI / 2
    positions.push({
      leftPct: 50 + 42 * Math.cos(angle),
      topPct: 50 + 40 * Math.sin(angle),
    })
  }
  return positions
}

/** Build one SeatInfo per max seat: occupied seats first (by roster order), then open seats. */
export function buildSeats(
  table: TableRosterEntry,
  classifications: Map<string, Classification>,
  assessments: IntegrityAssessment[],
  ptlByPlayer?: Map<string, PtlResult>,
): SeatInfo[] {
  const memberToGroup = new Map<string, string>()
  for (const a of assessments) {
    for (const m of a.member_ids) memberToGroup.set(m, a.group_id)
  }

  return seatPositions(table.max_seats).map((pos, i) => {
    const playerId = table.seated_player_ids[i] ?? null
    const cls = playerId ? classifications.get(playerId) : undefined
    const ptlResult = playerId ? ptlByPlayer?.get(playerId) : undefined
    return {
      index: i,
      playerId,
      archetype: cls?.archetype ?? null,
      archetypeWhy: cls?.reason_codes[0]?.detail,
      flaggedGroupId: playerId ? memberToGroup.get(playerId) ?? null : null,
      ptl: ptlResult?.ptl ?? null,
      ptlWhy: ptlResult?.reason_codes[0]?.detail,
      leftPct: pos.leftPct,
      topPct: pos.topPct,
    }
  })
}

/** Integrity groups with at least one member seated at this table. */
export function assessmentsForTable(
  table: TableRosterEntry,
  integrity: IntegrityAssessment[],
): IntegrityAssessment[] {
  const seated = new Set(table.seated_player_ids)
  return integrity.filter((a) => a.member_ids.some((m) => seated.has(m)))
}

/** Index classifications by player_id for O(1) seat lookups. */
export function classificationIndex(classifications: Classification[]): Map<string, Classification> {
  return new Map(classifications.map((c) => [c.player_id, c]))
}
