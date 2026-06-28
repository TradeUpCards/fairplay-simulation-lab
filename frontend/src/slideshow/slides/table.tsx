import { useEffect, useState } from 'react'
import { Slide, Bullets } from '../Slide'
import { LobbySidecar } from '../../components/LobbySidecar'
import { loadLobbySequence } from '../../data/shim'
import type { OperatorTableDetail } from '../../data/types'
import type { SlideDef } from '../types'

/**
 * Live slide — the actual lobby curtain (LobbySidecar) for T-05, in pit-boss
 * view. Interactive: flip Player ↔ Pit-boss, see the seats, the PTL heat, the
 * health terms and reason codes — all real, from the frozen scores.
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
      <div className="grid h-full grid-cols-[1fr_24rem] items-stretch gap-8">
        <div className="flex flex-col justify-center gap-6">
          <p className="m-0 text-[1.2rem] leading-relaxed text-text">
            The pit-boss view reveals what the player can&apos;t see — straight from the scoring
            engine, no LLM.
          </p>
          <Bullets
            items={[
              <>
                Table health <span className="font-semibold text-[#e09098]">59 / 100 — fragile</span>.
              </>,
              <>
                A <span className="text-[#e3a08b]">shark</span> and grinders on a thinning,{' '}
                <span className="text-text">declining</span> table — predation + fragility.
              </>,
              <>
                Each seat&apos;s <span className="text-text">propensity to leave</span> — vulnerable
                players run <span className="text-[#e3b25f]">restless</span> here.
              </>,
              <>
                Standard says <span className="text-brass">&ldquo;it&apos;s full — join it.&rdquo;</span>{' '}
                FairPlay routes a recreational player <span className="text-[#5fcf8a]">away</span>.
              </>,
            ]}
          />
          <p className="m-0 max-w-[46ch] border-t border-dashed border-line pt-4 text-[0.9rem] text-faint">
            Flip <span className="text-text">Player ↔ Pit-boss</span> on the panel — it&apos;s live.
          </p>
        </div>

        <div className="min-h-0">
          {detail ? (
            <LobbySidecar
              detail={detail}
              pitboss={pitboss}
              onPitbossChange={setPitboss}
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
