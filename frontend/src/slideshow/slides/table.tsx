import { useEffect, useRef, useState } from 'react'
import { Slide } from '../Slide'
import { LobbySidecar } from '../../components/LobbySidecar'
import { loadLobbySequence } from '../../data/shim'
import type { OperatorTableDetail } from '../../data/types'
import type { SlideDef } from '../types'

/**
 * Scale a fixed-size block down to fit the available box (height + width), so the
 * whole thing shows at once — never scrolls, never clips. CSS transforms don't
 * change layout size, so scrollHeight/Width report the natural (unscaled) size.
 */
function FitToBox({ width, children }: { width: number; children: React.ReactNode }) {
  const outer = useRef<HTMLDivElement>(null)
  const inner = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0)

  useEffect(() => {
    const fit = () => {
      const o = outer.current
      const i = inner.current
      if (!o || !i) return
      const s = Math.min(1, o.clientHeight / i.scrollHeight, o.clientWidth / i.scrollWidth)
      setScale(s > 0 ? s : 1)
    }
    fit()
    const ro = new ResizeObserver(fit)
    if (outer.current) ro.observe(outer.current)
    if (inner.current) ro.observe(inner.current)
    return () => ro.disconnect()
  }, [])

  return (
    <div ref={outer} className="relative min-h-0 flex-1 overflow-hidden">
      <div className="absolute inset-x-0 top-0 flex justify-center">
        <div
          ref={inner}
          className="origin-top"
          style={{ width, transform: `scale(${scale})`, visibility: scale ? 'visible' : 'hidden' }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}

/**
 * Live slide — the actual lobby curtain (LobbySidecar) for T-05 in its wide,
 * expanded pit-boss view (the panel that grows when you open it on the page),
 * auto-scaled to fit the slide. Interactive: flip Player ↔ Pit-boss.
 */
function TableSlide() {
  const [detail, setDetail] = useState<OperatorTableDetail | null>(null)
  const [pitboss, setPitboss] = useState(true)

  useEffect(() => {
    let alive = true
    loadLobbySequence()
      .then((seq) => {
        if (!alive) return
        const step = seq.steps[1] ?? seq.steps[0]
        setDetail(step?.op_detail?.['LR-05'] ?? null)
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  return (
    <Slide kicker="Pull back the curtain" title="Why FairPlay buries it">
      <div className="flex h-full min-h-0 flex-col gap-2">
        <p className="m-0 max-w-[92ch] text-[0.98rem] leading-snug text-muted">
          What the player can&apos;t see — health terms, who&apos;s seated, each seat&apos;s{' '}
          <span className="text-text">propensity-to-leave</span> heat, and the reason codes. From the
          frozen scores, no LLM. <span className="text-text">Flip Player ↔ Pit-boss — it&apos;s live.</span>
        </p>
        {detail ? (
          <FitToBox width={1060}>
            <LobbySidecar
              detail={detail}
              pitboss={pitboss}
              onPitbossChange={setPitboss}
              expanded
              onClose={() => {}}
            />
          </FitToBox>
        ) : (
          <div className="flex min-h-0 flex-1 items-center justify-center rounded-md border border-dashed border-line text-[0.85rem] text-faint">
            loading T-05…
          </div>
        )}
      </div>
    </Slide>
  )
}

export const tableSlide: SlideDef = {
  id: 'table',
  label: 'The table',
  Component: TableSlide,
}
