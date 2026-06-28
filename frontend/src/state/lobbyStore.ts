/**
 * Lobby-demo UI state — persists across navigation (e.g. leaving the player page
 * and coming back) because it lives module-level, not in component state. Tiny
 * subscribe/notify store, same shape as simStore, for `useSyncExternalStore`.
 *
 *  - `step`     which room-state step the side-by-side board is showing
 *  - `selected` table_id highlighted in both lobbies (click to toggle)
 *  - `diagOpen` whether the admin seat-events diagnostics are expanded (both at once)
 *  - `revealed` demo scene gate: false = Standard-only lobby (Scene 1); true =
 *               "curtain pulled back" → the side-by-side Standard vs FairPlay board.
 *  - `pitboss`  sidecar view: false = player preview (small); true = operator reveal
 *               (promotes to a wide focus panel). Resets to false on each new select.
 */
export interface LobbyUiState {
  step: number
  selected: string | null
  diagOpen: boolean
  revealed: boolean
  pitboss: boolean
}

export type LobbyListener = (state: LobbyUiState) => void

const DEFAULT_STATE: LobbyUiState = {
  step: 0,
  selected: null,
  diagOpen: false,
  revealed: false,
  pitboss: false,
}

export interface LobbyStore {
  getState: () => LobbyUiState
  subscribe: (listener: LobbyListener) => () => void
  setStep: (step: number) => void
  setSelected: (selected: string | null) => void
  toggleSelected: (id: string) => void
  toggleDiag: () => void
  setRevealed: (revealed: boolean) => void
  setPitboss: (pitboss: boolean) => void
  reset: () => void
}

export function createLobbyStore(initial?: Partial<LobbyUiState>): LobbyStore {
  let state: LobbyUiState = { ...DEFAULT_STATE, ...initial }
  const listeners = new Set<LobbyListener>()

  const set = (patch: Partial<LobbyUiState>): void => {
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
    setStep(step) {
      set({ step })
    },
    setSelected(selected) {
      set({ selected, pitboss: false })
    },
    toggleSelected(id) {
      set({ selected: state.selected === id ? null : id, pitboss: false })
    },
    toggleDiag() {
      set({ diagOpen: !state.diagOpen })
    },
    setRevealed(revealed) {
      set({ revealed })
    },
    setPitboss(pitboss) {
      set({ pitboss })
    },
    reset() {
      set({ ...DEFAULT_STATE })
    },
  }
}

export const lobbyStore = createLobbyStore()
