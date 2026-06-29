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
    <Slide kicker="Player floor" title="A normal cash-game lobby">
      <div className="flex h-full min-h-0 flex-col gap-2">
        <p className="m-0 text-[0.95rem] leading-snug text-muted">
          How every site sorts the floor today — fullest tables first. Click a table to see
          who&apos;s seated.
        </p>
        <FitToBox width={1500}>
          <div className="px-3 pb-2 pt-1">
            <LobbyBoard locked />
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
