import { Header } from './components/Header'
import { Simulator } from './views/Simulator'
import { PitBossConsole } from './views/PitBossConsole'
import { PlayerLobby } from './views/PlayerLobby'
import { EvalPanel } from './views/EvalPanel'
import './styles.css'

export function App() {
  return (
    <div className="app">
      <Header />
      <main className="app-main">
        <Simulator />
        <PitBossConsole />
        <PlayerLobby />
        <EvalPanel />
      </main>
    </div>
  )
}
