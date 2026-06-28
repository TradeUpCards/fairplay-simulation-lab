import { useEffect } from 'react'

/**
 * Lets a staged slide step through its own internal stages with the deck's
 * arrow keys, before the shell moves to the next/previous slide.
 *
 * It listens in the CAPTURE phase, so it runs ahead of the shell's bubble-phase
 * handler in `views/Slideshow.tsx`. When there's a stage left to reveal it
 * consumes the key (`stopImmediatePropagation`); otherwise it does nothing and
 * the key falls through to the shell unchanged — so on the last stage the next
 * → advances to the next slide exactly as before, and non-staged slides are
 * completely unaffected. The shell is never touched, so deck navigation can't
 * regress.
 *
 * Only ArrowRight / ArrowLeft are intercepted; Space, PageUp/Down, Home, End
 * keep their shell behaviour.
 */
export function useStageKeys(stage: number, total: number, setStage: (n: number) => void): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' && stage < total - 1) {
        e.preventDefault()
        e.stopImmediatePropagation()
        setStage(stage + 1)
      } else if (e.key === 'ArrowLeft' && stage > 0) {
        e.preventDefault()
        e.stopImmediatePropagation()
        setStage(stage - 1)
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [stage, total, setStage])
}
