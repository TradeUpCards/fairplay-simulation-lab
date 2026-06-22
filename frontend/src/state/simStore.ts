/**
 * Sim-state store — the single source of truth for `{ path, hour, adherence }`
 * that drives every time-varying view (simulator, pit-boss index, table). A tiny
 * subscribe/notify store (no dependency) so it works with React's
 * `useSyncExternalStore` and in plain tests alike.
 *
 *  - `path`      which counterfactual is shown (standard | fairplay)
 *  - `hour`      sim clock, integer 0..8
 *  - `adherence` FairPlay-adherence lever, 0..100 (0 ≡ standard, 100 ≡ fairplay)
 */
import type { SimPath } from '../data/types'

export interface SimState {
  path: SimPath
  hour: number
  adherence: number
}

export type SimListener = (state: SimState) => void

export const HOUR_MIN = 0
export const HOUR_MAX = 8
export const ADHERENCE_MIN = 0
export const ADHERENCE_MAX = 100

const clamp = (value: number, lo: number, hi: number): number =>
  Math.min(hi, Math.max(lo, value))

const DEFAULT_STATE: SimState = { path: 'standard', hour: 0, adherence: 0 }

export interface SimStore {
  getState: () => SimState
  subscribe: (listener: SimListener) => () => void
  setPath: (path: SimPath) => void
  setHour: (hour: number) => void
  setAdherence: (adherence: number) => void
  advanceHour: () => void
  reset: () => void
}

export function createSimStore(initial?: Partial<SimState>): SimStore {
  let state: SimState = { ...DEFAULT_STATE, ...initial }
  const listeners = new Set<SimListener>()

  const set = (patch: Partial<SimState>): void => {
    state = { ...state, ...patch }
    for (const listener of listeners) listener(state)
  }

  return {
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    setPath(path) {
      set({ path })
    },
    setHour(hour) {
      set({ hour: clamp(Math.round(hour), HOUR_MIN, HOUR_MAX) })
    },
    setAdherence(adherence) {
      set({ adherence: clamp(adherence, ADHERENCE_MIN, ADHERENCE_MAX) })
    },
    advanceHour() {
      set({ hour: clamp(Math.round(state.hour) + 1, HOUR_MIN, HOUR_MAX) })
    },
    reset() {
      set({ ...DEFAULT_STATE })
    },
  }
}

/** App-wide singleton; tests use `createSimStore()` for isolation. */
export const simStore = createSimStore()
