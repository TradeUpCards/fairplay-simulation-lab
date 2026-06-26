import { useState } from 'react'
import { Header, type ViewMode } from './components/Header'
import { OperatorNav, type OperatorView } from './components/OperatorNav'
import { Simulator } from './views/Simulator'
import { PitBossConsole } from './views/PitBossConsole'
import { PlayerLobby } from './views/PlayerLobby'
import { EvalPanel } from './views/EvalPanel'
import { TrainingTable } from './views/TrainingTable'
import './styles.css'

/**
 * Two audiences, two surfaces (the load-bearing player/operator wall, made
 * spatial): Operator is the dark "back of house" instrument room — console,
 * simulator, eval. Player is the warm "front of house" lobby. The header toggle
 * switches between them. Inside operator, a sub-nav walks the demo spine one
 * view at a time (Console → Simulator → Eval) instead of stacking all three.
 */
export function App() {
  const [mode, setMode] = useState<ViewMode>('operator')
  const [operatorView, setOperatorView] = useState<OperatorView>('console')

  // mode scrim — a warm vignette over the carpet for the player floor, a cooler
  // one for the operator console; both layered on a darkening wash.
  const scrim =
    mode === 'player'
      ? 'bg-[radial-gradient(140%_100%_at_50%_-20%,rgba(82,63,40,0.34),transparent_55%),rgba(9,7,4,0.5)]'
      : mode === 'training'
        ? 'bg-[radial-gradient(150%_100%_at_50%_-15%,rgba(47,143,91,0.2),transparent_55%),rgba(9,8,5,0.55)]'
        : 'bg-[radial-gradient(150%_100%_at_50%_-15%,rgba(62,76,68,0.22),transparent_55%),rgba(10,9,7,0.5)]'

  return (
    <div className={`min-h-screen ${scrim}`}>
      <Header mode={mode} onModeChange={setMode} />
      {mode === 'operator' ? (
        <main className="mx-auto max-w-[1360px] px-6 pb-12 pt-7">
          <OperatorNav view={operatorView} onViewChange={setOperatorView} />
          <div>
            {operatorView === 'console' && <PitBossConsole />}
            {operatorView === 'simulator' && <Simulator />}
            {operatorView === 'eval' && <EvalPanel />}
          </div>
        </main>
      ) : mode === 'training' ? (
        <main className="mx-auto max-w-[1360px] px-6 pb-12 pt-8">
          <TrainingTable />
        </main>
      ) : (
        <main className="mx-auto max-w-[1360px] px-6 pb-12 pt-8">
          <PlayerLobby />
        </main>
      )}
    </div>
  )
}
