import { useCallback, useEffect, useState } from 'react'
import logo from '../assets/fairplay-iq-logo-brass.svg'
import { navigate } from '../state/route'
import { SLIDES } from '../slideshow/slides'

/**
 * The presentation deck — a full-screen surface (no app header/scrim) that
 * walks the FairPlay IQ pitch one slide at a time.
 *
 * Navigation: ← / → (also Space, PageUp/Down) move between slides, Home / End
 * jump to the ends, Esc exits back to the app. The current slide is mirrored to
 * the URL (`#/slideshow/3`) so a refresh or a shared link lands on the same page.
 *
 * The slides themselves live in `src/slideshow/slides/` — this file is only the
 * frame. See `src/slideshow/README.md` to add one.
 */
const clamp = (n: number, max: number) => Math.min(Math.max(n, 0), Math.max(max, 0))

function initialIndex(count: number): number {
  const match = window.location.hash.match(/^#\/?slideshow\/(\d+)/)
  if (!match) return 0
  return clamp(parseInt(match[1], 10) - 1, count - 1)
}

export function Slideshow() {
  const count = SLIDES.length
  const [current, setCurrent] = useState(() => initialIndex(count))

  const go = useCallback((next: number) => setCurrent(clamp(next, count - 1)), [count])

  // Keep the URL in sync without polluting browser history (replace, not push).
  useEffect(() => {
    window.history.replaceState(null, '', `#/slideshow/${current + 1}`)
  }, [current])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowRight':
        case 'PageDown':
        case ' ':
          e.preventDefault()
          setCurrent((c) => clamp(c + 1, count - 1))
          break
        case 'ArrowLeft':
        case 'PageUp':
          e.preventDefault()
          setCurrent((c) => clamp(c - 1, count - 1))
          break
        case 'Home':
          e.preventDefault()
          setCurrent(0)
          break
        case 'End':
          e.preventDefault()
          setCurrent(count - 1)
          break
        case 'Escape':
          navigate('home')
          break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [count])

  // Follow external hash changes — a deep link opened (or edited) while the deck
  // is already mounted should jump to that slide. Our own replaceState above
  // doesn't fire hashchange, so this never loops.
  useEffect(() => {
    const onHash = () => {
      const match = window.location.hash.match(/^#\/?slideshow\/(\d+)/)
      if (match) setCurrent(clamp(parseInt(match[1], 10) - 1, count - 1))
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [count])

  if (count === 0) {
    return (
      <div className="fixed inset-0 z-[100] grid place-items-center bg-[#0d0a07] text-muted">
        No slides yet — add one in <code className="px-1 font-mono">src/slideshow/slides/</code>.
      </div>
    )
  }

  const slide = SLIDES[current]
  const Body = slide.Component

  return (
    <div className="fixed inset-0 z-[100] flex flex-col bg-[radial-gradient(150%_100%_at_50%_-10%,rgba(62,76,68,0.22),transparent_55%),#0a0d0f]">
      {/* top rail */}
      <div className="flex items-center justify-between border-b border-line px-7 py-3">
        <div className="flex items-center gap-[0.8rem]">
          <img className="block h-[26px] w-auto" src={logo} alt="FairPlay IQ" />
          <span className="h-[20px] w-px bg-brass-soft" aria-hidden="true" />
          <span className="font-mono text-[0.68rem] uppercase tracking-[0.24em] text-muted">
            {slide.label ?? 'Simulation Lab'}
          </span>
        </div>
        <button
          type="button"
          onClick={() => navigate('home')}
          className="rounded-full border border-line bg-surface-2 px-[0.85rem] py-[0.3rem] text-[0.7rem] tracking-wider text-muted hover:text-text"
        >
          Exit ⎋
        </button>
      </div>

      {/* stage */}
      <main className="flex min-h-0 flex-1 items-stretch justify-center overflow-y-auto px-10 py-10">
        <div className="flex w-full max-w-[1080px] py-2">
          <Body key={slide.id} />
        </div>
      </main>

      {/* progress bar */}
      <div className="h-[3px] w-full bg-[rgba(255,255,255,0.05)]">
        <div
          className="h-full bg-brass transition-[width] duration-300"
          style={{ width: `${((current + 1) / count) * 100}%` }}
        />
      </div>

      {/* bottom rail */}
      <div className="flex items-center justify-between border-t border-line px-7 py-3">
        <button
          type="button"
          onClick={() => go(current - 1)}
          disabled={current === 0}
          aria-label="Previous slide"
          className="rounded-full border border-line bg-surface-2 px-4 py-[0.3rem] text-[0.9rem] text-muted hover:text-text disabled:opacity-30"
        >
          ←
        </button>

        <div className="flex items-center gap-3">
          <div className="flex gap-[0.4rem]" role="tablist" aria-label="Slides">
            {SLIDES.map((s, i) => (
              <button
                key={s.id}
                type="button"
                role="tab"
                aria-selected={i === current}
                aria-label={`Go to slide ${i + 1}${s.label ? `: ${s.label}` : ''}`}
                onClick={() => go(i)}
                className={`h-[0.45rem] w-[0.45rem] rounded-full transition-colors ${
                  i === current ? 'bg-brass' : 'bg-[#3a4757] hover:bg-[#566173]'
                }`}
              />
            ))}
          </div>
          <span className="font-mono text-[0.72rem] tabular-nums text-faint">
            {current + 1} / {count}
          </span>
        </div>

        <button
          type="button"
          onClick={() => go(current + 1)}
          disabled={current === count - 1}
          aria-label="Next slide"
          className="rounded-full border border-line bg-surface-2 px-4 py-[0.3rem] text-[0.9rem] text-muted hover:text-text disabled:opacity-30"
        >
          →
        </button>
      </div>
    </div>
  )
}
