import { useEffect } from 'react'
import { Slide } from '../Slide'
import { FitToBox } from '../FitToBox'
import { LobbyBoard } from '../../components/LobbyBoard'
import { lobbyStore } from '../../state/lobbyStore'
import type { SlideDef } from '../types'

/**
 * Live slide — the real Standard-vs-FairPlay lobby board, preset to step 2
 * ("After activity 1", curtain up) and auto-scaled as large as the slide allows.
 * Fully interactive: step the churn, flip Standard-only, click T-05 for the curtain.
 */
function LobbySlide() {
  useEffect(() => {
    lobbyStore.setRevealed(true)
    lobbyStore.setStep(1) // "After activity 1" → header reads step 2/4
    lobbyStore.setSelected(null)
  }, [])

  return (
    <Slide>
      <div className="flex h-full min-h-0 flex-col gap-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <span className="font-mono text-[0.74rem] uppercase tracking-[0.26em] text-brass">
            Player floor
          </span>
          <h2 className="m-0 text-[1.7rem] font-bold leading-tight tracking-[-0.01em] text-text">
            Same table, opposite verdict
          </h2>
        </div>
        <p className="m-0 text-[0.95rem] leading-snug text-muted">
          <span className="font-semibold text-brass">Standard</span> ranks{' '}
          <span className="text-text">T-05</span> at #3 (it&apos;s full);{' '}
          <span className="font-semibold text-[#5fcf8a]">FairPlay</span> buries it dead-last among
          open tables. Step the churn, or click a table to pull back the curtain.
        </p>
        <FitToBox width={1500}>
          <div className="px-3 pb-2 pt-1">
            <LobbyBoard />
          </div>
        </FitToBox>
      </div>
    </Slide>
  )
}

export const lobbySlide: SlideDef = {
  id: 'lobby',
  label: 'Player lobby',
  Component: LobbySlide,
}
