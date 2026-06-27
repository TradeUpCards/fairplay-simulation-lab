/**
 * Data layer — the ONE place the app reads P3's frozen Contract-2.
 *
 * Each `loadX()` is async and returns a `contract2.d.ts` shape. Today it resolves
 * a build-time JSON import (so the bundle opens with no API server — origin
 * R21); swapping to a live `fetch()` later (FastAPI) changes only these bodies,
 * never the call sites (R20). Views never branch on transport.
 *
 * Trust boundary: `data/derived/*.json` and `data/room_metrics_*.json` are
 * frozen P3 outputs, validated offline by `scripts/validate_*.py`. We assert
 * their shape once here rather than re-validating at runtime.
 */
import type {
  ClassificationsFile,
  IntegrityScoresFile,
  HealthScoresFile,
  SeatingScoresFile,
  RouterLobbyFile,
  RoomMetricsFile,
  RoomSweepFile,
  RoomTimeseriesFile,
  SeededCaseLabelsFile,
  TableRosterFile,
  SimPath,
} from './types'

import classificationsRaw from '@data/derived/classifications.json'
import integrityRaw from '@data/derived/integrity_scores.json'
import healthRaw from '@data/derived/health_scores.json'
import seatingRaw from '@data/derived/seating_scores.json'
import routerRaw from '@data/derived/router_lobby.json'
import roomStandardRaw from '@data/room_metrics_standard.json'
import roomFairplayRaw from '@data/room_metrics_fairplay.json'
import roomSweepRaw from '@data/room_sweep.json'
import roomTimeseriesRaw from '@data/room_timeseries.json'
import seededCasesRaw from '@data/seeded_case_labels.json'
import tableRosterRaw from '@data/table_roster.json'

/** Assert a frozen JSON artifact into its Contract-2 type at the trust boundary. */
const asType = <T>(raw: unknown): T => raw as T

export async function loadClassifications(): Promise<ClassificationsFile> {
  return asType(classificationsRaw)
}

export async function loadIntegrity(): Promise<IntegrityScoresFile> {
  return asType(integrityRaw)
}

export async function loadHealth(): Promise<HealthScoresFile> {
  return asType(healthRaw)
}

export async function loadSeating(): Promise<SeatingScoresFile> {
  return asType(seatingRaw)
}

export async function loadRouterLobby(): Promise<RouterLobbyFile> {
  return asType(routerRaw)
}

export async function loadRoomMetrics(path: SimPath): Promise<RoomMetricsFile> {
  return asType(path === 'fairplay' ? roomFairplayRaw : roomStandardRaw)
}

/** Normalized regime sweep (heatmap + data table) for the /dashboard route. */
export async function loadRoomSweep(): Promise<RoomSweepFile> {
  return asType(roomSweepRaw)
}

/** Per-cell, seed-averaged time-series for the dashboard's animated hero chart. */
export async function loadRoomTimeseries(): Promise<RoomTimeseriesFile> {
  return asType(roomTimeseriesRaw)
}

/** OPERATOR-ONLY eval answer key — never load this from a player-facing screen. */
export async function loadSeededCases(): Promise<SeededCaseLabelsFile> {
  return asType(seededCasesRaw)
}

/** Table roster (P2 Contract-1) — composition for the pit-boss seat-ring. Operator-side. */
export async function loadTableRoster(): Promise<TableRosterFile> {
  return asType(tableRosterRaw)
}

// Re-export the shared load-state helper so views import the data layer in one place.
export { safeLoad } from './loadState'
export type { LoadState } from './loadState'
