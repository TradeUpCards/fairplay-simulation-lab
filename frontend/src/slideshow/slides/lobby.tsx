import { useEffect, useRef } from 'react'
import { Slide } from '../Slide'
import { FitToBox } from '../FitToBox'
import { LobbyBoard } from '../../components/LobbyBoard'
import { lobbyStore, type LobbyUiState } from '../../state/lobbyStore'
import type { SlideDef } from '../types'

/**
 * The in-slide story beats, walked by the deck's → arrow (← reverses). Each beat
 * is the FULL board state at that point, so stepping forward/back is deterministic:
 *   0 · arrive — step 1/4, both rooms identical
 *   1 · run the room — step 2/4, the rooms diverge
 *   2 · open "how each policy seated this round" (seat-events drawer)
 *   3 · close that drawer
 *   4 · select T-05 (player preview in the sidecar)
 *   5 · flip the sidecar to Pit-boss view on T-05
 * After beat 5, → falls through to the next slide; before beat 0, ← falls through.
 */
type Beat = Pick<LobbyUiState, 'step' | 'selected' | 'pitboss' | 'diagOpen'>
const BEATS: Beat[] = [
  { step: 0, selected: null, pitboss: false, diagOpen: false },
  { step: 1, selected: null, pitboss: false, diagOpen: false },
  { step: 1, selected: null, pitboss: false, diagOpen: true },
  { step: 1, selected: null, pitboss: false, diagOpen: false },
  { step: 1, selected: 'LR-05', pitboss: false, diagOpen: false },
  { step: 1, selected: 'LR-05', pitboss: true, diagOpen: false },
]

function applyBeat(b: Beat) {
  lobbyStore.setRevealed(true)
  lobbyStore.setStep(b.step)
  lobbyStore.setSelected(b.selected) // also resets pitboss → set it after
  lobbyStore.setPitboss(b.pitboss)
  lobbyStore.setDiag(b.diagOpen)
}

/**
 * Live slide — the real Standard-vs-FairPlay lobby board, curtain up and locked
 * (no manual controls). The deck's → arrow walks the story beats above before
 * moving on to the next slide (← reverses). Auto-scaled as large as the slide
 * allows; click T-05 to pull back the curtain.
 */
function LobbySlide() {
  const beat = useRef(0)

  useEffect(() => {
    beat.current = 0
    applyBeat(BEATS[0])
  }, [])

  // Capture the deck's arrow keys: walk the in-slide beats first, then let the
  // event through so the slideshow advances to / from the neighbouring slide.
  // Capture phase + stopImmediatePropagation pre-empts Slideshow's own window
  // keydown listener only when we actually consume the key.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const next = e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' '
      const prev = e.key === 'ArrowLeft' || e.key === 'PageUp'
      if (next && beat.current < BEATS.length - 1) {
        beat.current += 1
        applyBeat(BEATS[beat.current])
        e.preventDefault()
        e.stopImmediatePropagation()
      } else if (prev && beat.current > 0) {
        beat.current -= 1
        applyBeat(BEATS[beat.current])
        e.preventDefault()
        e.stopImmediatePropagation()
      }
      // otherwise: leave the event for the slideshow (change slides)
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [])

  return (
    <Slide kicker="Player floor" title="Same table, opposite verdict">
      <div className="flex h-full min-h-0 flex-col gap-2">
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
