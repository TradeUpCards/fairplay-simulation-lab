import { useEffect, useState } from 'react'
import { Slide } from '../Slide'
import { LobbySidecar } from '../../components/LobbySidecar'
import { loadLobbySequence } from '../../data/shim'
import type { OperatorTableDetail } from '../../data/types'
import type { SlideDef } from '../types'

/**
 * Live slide — the actual lobby curtain (LobbySidecar) for T-05 in its wide,
 * expanded pit-boss view (the same panel that grows when you open it on the
 * page). Interactive: flip Player ↔ Pit-boss, read the health terms, seats, PTL
 * heat, and reason codes — all real, from the frozen scores.
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
      <div className="flex h-full min-h-0 flex-col gap-3">
        <p className="m-0 max-w-[86ch] text-[1.05rem] leading-snug text-muted">
          The pit-boss view reveals what the player can&apos;t see — table health and its terms,
          who&apos;s seated, each seat&apos;s <span className="text-text">propensity-to-leave</span> heat,
          and the reason codes. All from the frozen scores, no LLM.{' '}
          <span className="text-text">Flip Player ↔ Pit-boss — it&apos;s live.</span>
        </p>
        <div className="min-h-0 flex-1">
          {detail ? (
            <LobbySidecar
              detail={detail}
              pitboss={pitboss}
              onPitbossChange={setPitboss}
              expanded
              onClose={() => {}}
            />
          ) : (
            <div className="flex h-full items-center justify-center rounded-md border border-dashed border-line text-[0.85rem] text-faint">
              loading T-05…
            </div>
          )}
        </div>
      </div>
    </Slide>
  )
}

export const tableSlide: SlideDef = {
  id: 'table',
  label: 'The table',
  Component: TableSlide,
}
