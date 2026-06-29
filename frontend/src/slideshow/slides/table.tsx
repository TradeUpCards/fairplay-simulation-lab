import { useEffect, useState } from 'react'
import { Slide } from '../Slide'
import { FitToBox } from '../FitToBox'
import { LobbySidecar } from '../../components/LobbySidecar'
import { loadLobbySequence } from '../../data/shim'
import type { HealthBand, OperatorTableDetail } from '../../data/types'
import { BAND_META, BAND_TEXT } from '../../lib/health'
import type { SlideDef } from '../types'

const BANDS: HealthBand[] = ['healthy', 'fragile', 'beginner_unfriendly', 'collapsed']

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
      {/* Whole body (title + pit-boss curtain) in one FitToBox canvas → scales as a
          unit, zoom-independent. */}
      <div className="relative flex h-full min-h-0 flex-col">
        <FitToBox width={1480}>
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-0.5">
              <span className="font-mono text-[0.9rem] uppercase tracking-[0.26em] text-brass">
                Pull back the curtain
              </span>
              <h2 className="m-0 text-[2rem] font-bold leading-tight tracking-[-0.01em] text-text">
                Why FairPlay buries it
              </h2>
              <span className="text-[1.15rem] text-muted">
                health terms, who&apos;s seated, each seat&apos;s{' '}
                <span className="text-text">propensity-to-leave</span> heat, reason codes — frozen
                scores, no LLM. <span className="text-text">Flip Player ↔ Pit-boss; it&apos;s live.</span>
              </span>
            </div>
            {detail ? (
              <LobbySidecar
                detail={detail}
                pitboss={pitboss}
                onPitbossChange={setPitboss}
                expanded
                onClose={() => {}}
                analysisFooter={<HealthFormula />}
              />
            ) : (
              <div className="flex h-[24rem] items-center justify-center rounded-md border border-dashed border-line text-[1rem] text-faint">
                loading T-05…
              </div>
            )}
          </div>
        </FitToBox>
      </div>
    </Slide>
  )
}

/** How table health is scored — a compact, color-coded formula callout that fills
 *  the empty space at the bottom of the curtain's analysis column. */
function HealthFormula() {
  return (
    <div className="rounded-xl border border-brass/40 bg-[rgba(255,255,255,0.02)] px-4 py-3">
      <div className="mb-1.5 font-mono text-[0.66rem] uppercase tracking-[0.24em] text-brass">
        How table health is scored
      </div>
      <div className="font-mono text-[1.02rem] leading-relaxed text-text">
        <span className="font-bold text-[#8be3a7]">Health</span> = 100 −{' '}
        <span className="text-[#e3a08b]">Predation</span> −{' '}
        <span className="text-[#e3a08b]">Fragility</span> −{' '}
        <span className="text-[#e3a08b]">Cluster</span> −{' '}
        <span className="text-[#e3a08b]">Bleed</span>
      </div>
      <div className="mt-1.5 font-mono text-[0.72rem] text-muted">
        penalty caps 45 · 25 · 30 · 20 — higher = riskier for recreational players
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-[#23262d] pt-2 font-mono text-[0.72rem]">
        {BANDS.map((b) => (
          <span key={b} className="flex items-center gap-1.5">
            <span className={`text-[0.7rem] ${BAND_TEXT[b]}`}>●</span>
            <span className="text-text">{BAND_META[b].label}</span>
            <span className="text-faint">{BAND_META[b].range}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

export const tableSlide: SlideDef = {
  id: 'table',
  label: 'The table',
  Component: TableSlide,
  wide: true,
}
