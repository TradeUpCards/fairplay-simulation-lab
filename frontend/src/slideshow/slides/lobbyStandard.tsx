import { useEffect } from 'react'
import { Slide } from '../Slide'
import { FitToBox } from '../FitToBox'
import { LobbyBoard } from '../../components/LobbyBoard'
import { lobbyStore } from '../../state/lobbyStore'
import type { SlideDef } from '../types'

/**
 * Live slide — the real lobby board locked to Scene 1 (Standard only) at step 1:
 * a normal cash-game lobby, the status quo before FairPlay enters the story. The
 * curtain CTA is hidden (locked), so it stays on the Standard view; clicking a
 * table still previews who's seated (player-safe).
 */
function LobbyStandardSlide() {
  useEffect(() => {
    lobbyStore.setRevealed(false) // Scene 1 — Standard only
    lobbyStore.setStep(0) // step 1/4
    lobbyStore.setSelected(null)
  }, [])

  return (
    <Slide>
      {/* Whole body in one FitToBox canvas → scales as a unit, zoom-independent. */}
      <div className="flex h-full min-h-0 flex-col">
        <FitToBox width={1500}>
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-0.5">
              <span className="font-mono text-[0.9rem] uppercase tracking-[0.26em] text-brass">
                Player floor
              </span>
              <h2 className="m-0 text-[2rem] font-bold leading-tight tracking-[-0.01em] text-text">
                A normal cash-game lobby
              </h2>
              <span className="text-[1.15rem] text-muted">
                How every site sorts the floor today — fullest tables first. Click a table to see
                who&apos;s seated.
              </span>
            </div>
            <div className="px-3 pb-2 pt-1">
              <LobbyBoard locked />
            </div>
          </div>
        </FitToBox>
      </div>
    </Slide>
  )
}

export const lobbyStandardSlide: SlideDef = {
  id: 'lobby-standard',
  label: 'The lobby today',
  Component: LobbyStandardSlide,
  wide: true,
}
