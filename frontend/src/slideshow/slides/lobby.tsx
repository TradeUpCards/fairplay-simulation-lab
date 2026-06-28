import { useEffect } from 'react'
import { Slide } from '../Slide'
import { LobbyBoard } from '../../components/LobbyBoard'
import { lobbyStore } from '../../state/lobbyStore'
import type { SlideDef } from '../types'

/**
 * Live slide — the real Standard-vs-FairPlay lobby board, preset to step 2
 * ("After activity 1") with the curtain pulled back. Fully interactive: the
 * presenter can step the churn, flip Standard-only, and click T-05 to open the
 * curtain. The board is scaled to fit the slide stage.
 */
function LobbySlide() {
  useEffect(() => {
    lobbyStore.setRevealed(true)
    lobbyStore.setStep(1) // "After activity 1" → the header reads step 2/4
    lobbyStore.setSelected(null)
  }, [])

  return (
    <Slide kicker="Player floor" title="Same table, opposite verdict">
      <div className="flex h-full min-h-0 flex-col gap-3">
        <p className="m-0 max-w-[82ch] text-[1.05rem] leading-snug text-muted">
          One room, seated by two policies. <span className="font-semibold text-brass">Standard</span>{' '}
          ranks <span className="font-semibold text-text">T-05</span> at{' '}
          <span className="text-text">#3</span> (it&apos;s full); <span className="font-semibold text-[#5fcf8a]">FairPlay</span>{' '}
          buries it dead-last among open tables. Step the churn, or click a table to pull back the curtain.
        </p>
        <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-line bg-[#0b0e13]">
          <div className="origin-top-left scale-[0.62]" style={{ width: '161.3%', height: '161.3%' }}>
            <div className="p-5">
              <LobbyBoard />
            </div>
          </div>
        </div>
      </div>
    </Slide>
  )
}

export const lobbySlide: SlideDef = {
  id: 'lobby',
  label: 'Player lobby',
  Component: LobbySlide,
}
