/**
 * Live-room store — the optional bridge to the FastAPI scoring service.
 *
 * When the API is reachable it seeds from `GET /api/pit` and then subscribes to
 * `GET /api/stream` (SSE), patching each table's health + roster as `score_update`
 * events arrive. When it is NOT reachable (no server, or a test environment with
 * no `fetch`/`EventSource`), it simply stays `connected: false` and every consumer
 * falls back to the frozen static JSON — so the app still runs with no backend
 * (origin R21). Nothing here computes scores; the server (the scoring engine) does.
 *
 * Mirrors the tiny subscribe/notify shape of `simStore` so it plugs into
 * `useSyncExternalStore`.
 */
import { useSyncExternalStore } from 'react'
import type { HealthScore, HealthScoresFile, TableRosterEntry, TableRosterFile } from '../data/types'

const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? 'http://localhost:8000'

export interface LiveRoomState {
  /** True once a snapshot or an event has been received from the API. */
  connected: boolean
  healthById: Map<string, HealthScore>
  tableById: Map<string, TableRosterEntry>
  /** The most recently updated table (drives the "just changed" flash). */
  lastUpdated: { tableId: string; at: number } | null
}

type Listener = () => void

let state: LiveRoomState = {
  connected: false,
  healthById: new Map(),
  tableById: new Map(),
  lastUpdated: null,
}
const listeners = new Set<Listener>()
let started = false
let source: EventSource | null = null

function emit(patch: Partial<LiveRoomState>): void {
  state = { ...state, ...patch } // new top-level identity so useSyncExternalStore re-renders
  for (const l of listeners) l()
}

/** Lazily connect on first subscriber. Safe to call repeatedly. */
function ensureStarted(): void {
  if (started) return
  started = true
  // Require BOTH fetch and EventSource — this gates live mode to real browsers.
  // Node/jsdom (tests) has `fetch` but no `EventSource`, so it stays static and
  // never touches the network, keeping the suite deterministic.
  if (typeof fetch === 'undefined' || typeof EventSource === 'undefined') return

  // 1) seed the baseline from the operator snapshot
  fetch(`${API_BASE}/api/pit`)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`pit ${r.status}`))))
    .then((seed: { tables: TableRosterEntry[]; health_scores: HealthScore[] }) => {
      emit({
        connected: true,
        healthById: new Map(seed.health_scores.map((h) => [h.table_id, h])),
        tableById: new Map(seed.tables.map((t) => [t.table_id, t])),
      })
    })
    .catch(() => {
      /* API down — consumers use the static fallback */
    })

  // 2) live updates
  try {
    source = new EventSource(`${API_BASE}/api/stream`)
    source.addEventListener('score_update', (e) => {
      const d = JSON.parse((e as MessageEvent).data) as {
        table_id: string
        table: TableRosterEntry
        health: HealthScore
      }
      state.healthById.set(d.table_id, d.health)
      state.tableById.set(d.table_id, d.table)
      emit({ connected: true, lastUpdated: { tableId: d.table_id, at: Date.now() } })
    })
    // EventSource auto-reconnects on error; nothing to do but keep the static fallback meanwhile.
  } catch {
    /* no EventSource — stay static */
  }
}

async function move(path: string, body?: unknown): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error((detail as { detail?: string }).detail ?? `request failed (${res.status})`)
  }
  // The resulting score_update arrives over SSE; no need to apply the response here.
}

export const liveRoom = {
  getSnapshot: (): LiveRoomState => state,
  subscribe(listener: Listener): () => void {
    listeners.add(listener)
    ensureStarted()
    return () => {
      listeners.delete(listener)
    }
  },
  stand: (playerId: string): Promise<void> => move(`/api/players/${playerId}/stand`),
  sit: (playerId: string, tableId: string): Promise<void> =>
    move(`/api/players/${playerId}/sit`, { table_id: tableId }),
}

/** Subscribe a component to live-room state. */
export function useLiveRoom(): LiveRoomState {
  return useSyncExternalStore(liveRoom.subscribe, liveRoom.getSnapshot, liveRoom.getSnapshot)
}

/** Overlay live health onto a static score list (identity when disconnected). */
export function mergeHealthScores(scores: HealthScore[], live: LiveRoomState): HealthScore[] {
  if (!live.connected) return scores
  return scores.map((s) => live.healthById.get(s.table_id) ?? s)
}

/** Overlay live health onto a static `HealthScoresFile`. */
export function mergeHealthFile(file: HealthScoresFile, live: LiveRoomState): HealthScoresFile {
  if (!live.connected) return file
  return { ...file, health_scores: mergeHealthScores(file.health_scores, live) }
}

/** Overlay live rosters onto a static `TableRosterFile` (seat changes show on the ring). */
export function mergeRosterFile(file: TableRosterFile, live: LiveRoomState): TableRosterFile {
  if (!live.connected) return file
  return { ...file, tables: file.tables.map((t) => live.tableById.get(t.table_id) ?? t) }
}
