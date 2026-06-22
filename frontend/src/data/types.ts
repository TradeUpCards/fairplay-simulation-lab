/**
 * App-facing type surface.
 *
 * Everything in P3's Contract-2 comes straight from `contract2.d.ts` (the
 * shipped, guardrail-enforcing types — never re-author them). We add only the
 * two things Contract-2 doesn't type: the room-metrics series the simulator
 * reads, and the `SimPath` discriminant the sim-state store uses.
 */
export * from '../../contract2'

/** One hour of room KPIs in `data/room_metrics_{standard,fairplay}.json` → `hours[]`. */
export interface RoomMetricsHour {
  hour: number
  cumulative_paid_seat_time_minutes: number
  active_players: number
  active_healthy_tables: number
  new_player_retention_pct: number
  avg_casual_session_length_minutes: number
  early_table_breaks: number
  projected_eod_paid_seat_time_minutes: number
  reward_fee_ratio: number
  high_risk_seating_formations: number
  hour_note: string
}

export interface RoomMetricsMeta {
  schema_version: string
  path: SimPath
  [k: string]: unknown
}

export interface RoomMetricsFile {
  meta: RoomMetricsMeta
  hours: RoomMetricsHour[]
}

/** Which counterfactual path the simulator is showing. 0% adherence ≡ standard, 100% ≡ fairplay. */
export type SimPath = 'standard' | 'fairplay'
