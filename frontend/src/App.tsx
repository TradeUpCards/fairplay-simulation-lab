import { useSyncExternalStore } from 'react'
import { simStore } from './state/simStore'
import { useResource } from './state/useResource'
import { loadHealth, loadRouterLobby } from './data/shim'
import { ResourceBoundary } from './components/ResourceBoundary'
import { Simulator } from './views/Simulator'
import { PitBossIndex } from './views/PitBossIndex'
import { PlayerLobby } from './views/PlayerLobby'
import './styles.css'

function useSimState() {
  return useSyncExternalStore(simStore.subscribe, simStore.getState, simStore.getState)
}

/**
 * U1 shell. Not a real view — it exists to prove the scaffold wires together:
 * the sim-state store drives interactive controls, and the typed data layer
 * loads frozen Contract-2 through the shared ResourceBoundary. The real views
 * (simulator, pit-boss, lobby, eval) land in U3–U7.
 */
export function App() {
  const sim = useSimState()
  const health = useResource(loadHealth, (d) => d.health_scores.length === 0)
  const router = useResource(loadRouterLobby, (d) => d.routed.length === 0)

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>FairPlay — Simulation Lab</h1>
        <p className="subtitle">U1 · typed data layer + sim-state store</p>
      </header>

      <section className="sim-controls" aria-label="sim state">
        <span>path <strong>{sim.path}</strong></span>
        <span>hour <strong>{sim.hour}</strong> / {8}</span>
        <span>adherence <strong>{sim.adherence}%</strong></span>
        <div className="btns">
          <button onClick={() => simStore.advanceHour()}>Advance hour</button>
          <button onClick={() => simStore.setPath(sim.path === 'standard' ? 'fairplay' : 'standard')}>
            Toggle path
          </button>
          <button onClick={() => simStore.setAdherence(sim.adherence >= ADHERENCE_STEP_MAX ? 0 : sim.adherence + 25)}>
            Lever +25%
          </button>
          <button onClick={() => simStore.reset()}>Reset</button>
        </div>
      </section>

      <section className="data-status">
        <ResourceBoundary state={health} label="table health">
          {(d) => (
            <p>
              Loaded <strong>{d.health_scores.length}</strong> table-health scores
              {' '}· {d.meta.contract}
            </p>
          )}
        </ResourceBoundary>
        <ResourceBoundary state={router} label="routing">
          {(d) => (
            <p>
              Loaded routing for <strong>{d.routed.length}</strong> player(s).
            </p>
          )}
        </ResourceBoundary>
      </section>

      <Simulator />
      <PitBossIndex />
      <PlayerLobby />
    </main>
  )
}

const ADHERENCE_STEP_MAX = 100
