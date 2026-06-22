import { useState } from 'react'
import { Header, type ViewMode } from './components/Header'
import { Simulator } from './views/Simulator'
import { PitBossConsole } from './views/PitBossConsole'
import { PlayerLobby } from './views/PlayerLobby'
import { EvalPanel } from './views/EvalPanel'
import './styles.css'

/**
 * Two audiences, two surfaces (the load-bearing player/operator wall, made
 * spatial): Operator is the dark "back of house" instrument room — console,
 * simulator, eval. Player is the warm "front of house" lobby. The header toggle
 * switches between them.
 */
export function App() {
  const [mode, setMode] = useState<ViewMode>('operator')

  return (
    <div className={`app ${mode === 'player' ? 'is-player' : 'is-operator'}`}>
      <Header mode={mode} onModeChange={setMode} />
      {mode === 'operator' ? (
        <main className="app-main">
          <Simulator />
          <PitBossConsole />
          <EvalPanel />
        </main>
      ) : (
        <main className="app-main">
          <PlayerLobby />
        </main>
      )}
    </div>
  )
}
