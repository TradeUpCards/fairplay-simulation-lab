import { useEffect } from 'react'
import { Slide } from '../Slide'
import { FitToBox } from '../FitToBox'
import { LobbyBoard } from '../../components/LobbyBoard'
import { lobbyStore } from '../../state/lobbyStore'
import type { SlideDef } from '../types'

/** Steps the slide shows: lobby step 0 ("step 1/4", rooms identical) → step 1
 *  ("step 2/4", rooms diverge). The slideshow's right/left arrow walks these two
 *  in-slide first, then falls through to normal slide navigation. */
const MAX_SLIDE_STEP = 1

/**
 * Live slide — the real Standard-vs-FairPlay lobby board, curtain up and locked
 * (no manual controls). It starts at step 1 and the deck's → arrow advances the
 * room to step 2 before moving on to the next slide (← reverses). Auto-scaled as
 * large as the slide allows; click T-05 to pull back the curtain.
 */
function LobbySlide() {
  useEffect(() => {
    lobbyStore.setRevealed(true)
    lobbyStore.setStep(0) // start at "step 1/4" — both rooms identical
    lobbyStore.setSelected(null)
  }, [])

  // Capture the deck's arrow keys: walk the room's two steps in-slide first, then
  // let the event through so the slideshow advances to / from the neighbouring
  // slide. Capture phase + stopImmediatePropagation pre-empts Slideshow's own
  // window keydown listener only when we actually consume the key.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const step = lobbyStore.getState().step
      const next = e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' '
      const prev = e.key === 'ArrowLeft' || e.key === 'PageUp'
      if (next && step < MAX_SLIDE_STEP) {
        lobbyStore.setStep(step + 1)
        e.preventDefault()
        e.stopImmediatePropagation()
      } else if (prev && step > 0) {
        lobbyStore.setStep(step - 1)
        e.preventDefault()
        e.stopImmediatePropagation()
      }
      // otherwise: leave the event for the slideshow (change slides)
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
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
          open tables. Press <span className="text-text">→</span> to run the room, or click a table to
          pull back the curtain.
        </p>
        <FitToBox width={1900}>
          <div className="px-3 pb-2 pt-1">
            <LobbyBoard locked />
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
  wide: true,
}
