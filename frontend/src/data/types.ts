/**
 * App-facing type surface.
 *
 * Everything in P3's Contract-2 comes straight from `contract2.d.ts` (the
 * shipped, guardrail-enforcing types — never re-author them). We add only the
 * two things Contract-2 doesn't type: the room-metrics series the simulator
 * reads, and the `SimPath` discriminant the sim-state store uses.
 */
export * from '../../contract2'
import type { Archetype, LobbyTable } from '../../contract2'

/** A seated table on the player's "My Tables" view — neutral facts, no badge. */
export type NeutralTable = Omit<LobbyTable, 'badge' | 'badge_label'>

/**
 * One selectable player for the lobby impersonator (`GET /api/players`).
 * `archetype` + `seated_count` are operator-only context for the picker — they
 * never reach a player-facing card (the player/operator wall). Optional so the
 * pre-fetch fallback option can omit them.
 */
export interface PlayerOption {
  player_id: string
  display_name: string
  archetype?: Archetype
  seated_count?: number
}

/** A player's front-of-house view (`GET /api/lobby/{id}`): recommendations + seats. */
export interface PlayerFloorData {
  player_id: string
  player_lobby: LobbyTable[]
  tables: NeutralTable[]
}

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

// ── Table roster (data/table_roster.json — P2 Contract-1) ────────────────────

export interface TableRosterEntry {
  table_id: string
  stakes: string
  game_type: string
  max_seats: number
  seated_count: number
  open_seats: number
  seated_player_ids: string[]
  running_time_min: number
  avg_pot_size_usd: number
  avg_session_length_min: number
  hands_per_hour: number
  pace_label: string
  style_volatility_label: string
  paid_seat_time_trend: string
}

export interface TableRosterFile {
  schema_version: string
  generated: string
  fixture_note?: string
  tables: TableRosterEntry[]
}

// ── Eval answer key (data/seeded_case_labels.json) ───────────────────────────
// OPERATOR-FACING ONLY — the P4 eval harness ground truth. Never bind a
// player-facing screen to this; only the operator eval panel reads it.

export type RiskLens = 'table_health' | 'integrity_risk'

export interface SeededCase {
  case_id: string
  eval_scenario: string
  prd_label: string
  prd_ref?: string
  mandatory_demo_case?: boolean
  seeded_entities: Record<string, string | string[]>
  expected_category: string
  expected_risk_lens: RiskLens
  expected_seating_action: string
  is_false_positive_trap: boolean
  pit_boss_evidence_seed?: Record<string, string | number>
  eval_checks: string[]
  counterfactual?: Record<string, string>
}

export interface EvalSummary {
  total_cases: number
  true_risk_cases: string[]
  false_positive_traps: string[]
  mandatory_demo_cases: string[]
  eval_invariant: string
}

export interface SeededCaseLabelsFile {
  meta: Record<string, unknown>
  cases: SeededCase[]
  eval_summary: EvalSummary
}

// ── Lobby sequence (data/derived/lobby_sequence.json) — demo Part 2 ───────────
// PLAYER-FACING / player-safe. One room shown across a few churn steps, ordered
// two ways (Standard = fullness; FairPlay = the router). Produced by the
// playsim → router pipeline; the same tables appear in both `standard` and
// `fairplay`, only the order differs. No scores / archetypes / risk language.

export interface LobbyRow {
  table_id: string
  stakes: string
  game_type: string
  max_seats: number
  seated_count: number
  open_seats: number
  pace_label: string
  badge: LobbyTable['badge']
  badge_label: LobbyTable['badge_label']
  /** Poker-lobby stat columns (from the room roster; player-safe). */
  avg_pot_usd?: number
  hands_per_hour?: number
  plrs_per_flop_pct?: number
}

/** One seating decision in a step (admin diagnostic — shows policy behavior). */
export interface SeatEvent {
  player_id: string
  archetype?: string | null
  action: 'sit' | 'stand'
  table_id: string | null
  occ_after?: string
}

/**
 * OPERATOR-side per-table detail (the "pull back the curtain" view). Shown only
 * behind the curtain in the lobby demo — never in the player-facing rows.
 */
export interface OperatorTableDetail {
  table_id: string
  stakes: string
  seated_count: number
  max_seats: number
  open_seats: number
  full: boolean
  composition: { archetype: string; count: number }[]
  health?: number
  band?: string
  terms?: Record<string, number>
  reasons?: { code: string; detail: string }[]
  rank?: number
  badge?: string
  fit?: number
  delta_health?: number
  seating_risk?: string | null
}

export interface LobbyStep {
  label: string
  standard: LobbyRow[]
  fairplay: LobbyRow[]
  /** per-policy seat events that produced this step (admin diagnostic). */
  events?: { standard: SeatEvent[]; fairplay: SeatEvent[] }
  /** operator detail per table (the curtain) — keyed by table_id. */
  op_detail?: Record<string, OperatorTableDetail>
}

export interface LobbySequence {
  meta: {
    source: string
    seed?: number
    arrival_rate_per_hour?: number
    player_id?: string
    note?: string
    [k: string]: unknown
  }
  steps: LobbyStep[]
}

// ── Sweep dashboard (data/room_sweep.json — normalized regime payload) ────────
// Emitted by playsim/analysis/build_dashboard_data.py (reusing the sweep-explorer
// normalizer, so the heatmap / win-stability math lives once, in Python).

export interface SweepMetricDef {
  key: string
  label: string
  unit: string
  lower_is_better: boolean
}

/** Per-seed win record of a candidate policy vs the baseline on one metric. */
export interface SweepStability {
  wins: number
  n: number
  deltas: Record<string, number>
  mean_delta: number | null
}

export interface SweepCell {
  tables: number | null
  active_tables: number | null
  rate: number
  source_file: string
  policies: string[]
  seeds: number[]
  /** policy → metricKey → seed-averaged mean. */
  means: Record<string, Record<string, number | null>>
  /**
   * policy → departure-bucket → seed-averaged count. DESCRIPTIVE room context,
   * not a comparison metric: departure counts are flat across routing arms (the
   * FairPlay win is session duration, not who leaves). Absent on cells built
   * before the buckets existed; a policy is omitted if it carried no data.
   */
  departures?: Record<string, Record<string, number | null>>
  /** slim per-seed rows (seed, policy, + summary metric values). */
  runs: Array<Record<string, number | string>>
  /** candidate policy → metricKey → stability vs the baseline (baseline omitted). */
  stability: Record<string, Record<string, SweepStability>>
}

export interface SweepDataset {
  id: string
  label: string
  kind: 'grid' | 'single'
  config: Record<string, unknown>
  seeds: number[]
  policies: string[]
  table_axis: number[]
  rate_axis: number[]
  metrics: SweepMetricDef[]
  cells: SweepCell[]
}

export interface RoomSweepFile {
  generated_at: string
  datasets: SweepDataset[]
}

// ── Animated time-series (data/room_timeseries.json) ─────────────────────────
// Per-cell, per-policy, seed-averaged cumulative trace at the sweep's sampling
// cadence — what the animated hero chart replays. Keyed by the same cell identity
// (tables × rate) as the regime heatmap.

export interface TimeseriesCell {
  tables: number | null
  rate: number
  t_min: number[]
  t_hr: number[]
  seeds: number[]
  /** policy → metricKey → value series aligned to t_hr. */
  policies: Record<string, Record<string, number[]>>
}

export interface TimeseriesDataset {
  label: string
  interval_min: number | null
  horizon_min: number | null
  /** "<tables>|<rate>" → cell. Match by the numeric `tables`/`rate` fields. */
  cells: Record<string, TimeseriesCell>
}

export interface RoomTimeseriesFile {
  generated_at: string
  datasets: Record<string, TimeseriesDataset>
}
