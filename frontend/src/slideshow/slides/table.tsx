import { useEffect, useState } from 'react'
import { Slide } from '../Slide'
import { FitToBox } from '../FitToBox'
import { LobbySidecar } from '../../components/LobbySidecar'
import { loadLobbySequence } from '../../data/shim'
import type { OperatorTableDetail } from '../../data/types'
import type { SlideDef } from '../types'

/**
 * Live slide — the actual lobby curtain (LobbySidecar) for T-05 in its wide,
 * expanded pit-boss view, auto-scaled as large as the slide allows. Interactive:
 * flip Player ↔ Pit-boss; read the health terms, seats, PTL heat, reason codes.
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
    <Slide>
      <div className="flex h-full min-h-0 flex-col gap-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <span className="font-mono text-[0.74rem] uppercase tracking-[0.26em] text-brass">
            Pull back the curtain
          </span>
          <h2 className="m-0 text-[1.7rem] font-bold leading-tight tracking-[-0.01em] text-text">
            Why FairPlay buries it
          </h2>
        </div>
        <p className="m-0 text-[0.95rem] leading-snug text-muted">
          What the player can&apos;t see — health terms, who&apos;s seated, each seat&apos;s{' '}
          <span className="text-text">propensity-to-leave</span> heat, and the reason codes. From the
          frozen scores, no LLM. <span className="text-text">Flip Player ↔ Pit-boss — it&apos;s live.</span>
        </p>
        {detail ? (
          <FitToBox width={1550}>
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
  wide: true,
}
