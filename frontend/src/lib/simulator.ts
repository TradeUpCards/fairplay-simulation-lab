/**
 * Pure simulator math — kept out of the components so the lever/outcome logic is
 * unit-testable on its own (origin AE1 hinges on the two endpoints).
 */
import type { RoomMetricsHour } from '../data/types'

/** Numeric KPI keys on an hour row (everything except `hour` and `hour_note`). */
export type NumericHourKey = Exclude<keyof RoomMetricsHour, 'hour' | 'hour_note'>

export const lerp = (a: number, b: number, t: number): number => a + (b - a) * t

/**
 * Lever-blended ("projected") KPI between the two frozen endpoints. At 0%
 * adherence this is exactly the Standard value; at 100% exactly FairPlay
 * (R3). Mid-lever values are an illustrative interpolation, not a re-simulation.
 */
export function projectMetric(
  standard: number,
  fairplay: number,
  adherencePct: number,
  integer = true,
): number {
  const value = lerp(standard, fairplay, adherencePct / 100)
  return integer ? Math.round(value) : value
}

export type IntegrityOutcome = 'cluster_forms' | 'seat_held'

/**
 * The integrity half of the lever (R5): low adherence lets the cluster's 3rd
 * seat fill at T-11; high adherence holds it for review. 0% → forms, 100% →
 * held; the flip sits at the midpoint for the illustrative middle.
 */
export function integrityOutcome(adherencePct: number): IntegrityOutcome {
  return adherencePct >= 50 ? 'seat_held' : 'cluster_forms'
}

export const OUTCOME_LABEL: Record<IntegrityOutcome, string> = {
  cluster_forms: 'Cluster forms at T-11 (3rd seat seated)',
  seat_held: 'Seat held for review',
}

/** Clamp the sim clock to the 1..8 window the room-metrics series covers. */
export const displayHour = (hour: number): number => Math.min(8, Math.max(1, Math.round(hour)))
