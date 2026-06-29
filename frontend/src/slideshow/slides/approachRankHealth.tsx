import { useState } from 'react'
import { Slide } from '../Slide'
import { StageControl } from './agentic'
import { useStageKeys } from '../useStageKeys'
import type { SlideDef } from '../types'

/**
 * "Rank by health, not fullness." Dean's thesis, shown as an animated re-sort:
 * the same lobby starts ordered the standard way (fullest first), then FairPlay
 * re-ranks by table health — the rows glide to their new positions (the same
 * translateY re-rank the live Standings board uses). Staged: → flips the sort.
 */
type Tbl = { id: string; seated: number; max: number; health: number; band: 'healthy' | 'fragile' }

const TABLES: Tbl[] = [
  { id: 'T-24', seated: 6, max: 6, health: 100, band: 'healthy' },
  { id: 'T-33', seated: 5, max: 6, health: 63, band: 'fragile' },
  { id: 'T-19', seated: 5, max: 6, health: 95, band: 'healthy' },
  { id: 'T-05', seated: 4, max: 6, health: 59, band: 'fragile' },
  { id: 'T-17', seated: 4, max: 6, health: 90, band: 'healthy' },
]

const byFullness = [...TABLES].sort((a, b) => b.seated - a.seated).map((t) => t.id)
const byHealth = [...TABLES].sort((a, b) => b.health - a.health).map((t) => t.id)

const BAND_TONE: Record<Tbl['band'], string> = {
  healthy: 'border-[#2f7d4a] bg-[#16341f] text-[#8be3a7]',
  fragile: 'border-[#8a7a2f] bg-[#33301a] text-[#e3d28b]',
}

const ROW = 4.8 // rem per row, drives the translateY re-rank

function RankHealthSlide() {
  const [stage, setStage] = useState(0)
  useStageKeys(stage, 2, setStage)
  const order = stage === 0 ? byFullness : byHealth

  return (
    <Slide kicker="Our approach" title="Rank by health, not fullness.">
      <div className="flex flex-col gap-6">
        <p className="m-0 max-w-[72ch] text-[1.1rem] leading-relaxed text-muted">
          {stage === 0 ? (
            <>
              Standard seating sorts the lobby by <span className="text-text">how full</span> a
              table is — and points you at the busiest one.
            </>
          ) : (
            <>
              FairPlay re-ranks by <span className="text-brass">table health</span>: the healthiest
              tables rise, the predator pile-ups sink. Same room, different order.
            </>
          )}
        </p>

        <div className="relative" style={{ height: `${TABLES.length * ROW}rem` }}>
          {TABLES.map((t) => {
            const rank = order.indexOf(t.id)
            return (
              <div
                key={t.id}
                className="absolute left-0 right-0 transition-transform duration-[600ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
                style={{ transform: `translateY(${rank * ROW}rem)`, height: `${ROW}rem` }}
              >
                <div className="mr-2 flex h-[4rem] items-center gap-4 rounded-xl border border-line bg-surface px-4">
                  <span className="grid h-7 w-7 flex-none place-items-center rounded-full bg-surface-2 font-mono text-[0.8rem] font-bold text-brass">
                    {rank + 1}
                  </span>
                  <span className="font-mono text-[1.05rem] font-bold tracking-[0.03em] text-brass">
                    {t.id}
                  </span>
                  <div className="flex gap-1" aria-hidden="true">
                    {Array.from({ length: t.max }, (_, i) => (
                      <span
                        key={i}
                        className={`h-2.5 w-2.5 rounded-full ${
                          i < t.seated ? 'bg-[#6b7283]' : 'border border-dashed border-[#3a4757]'
                        }`}
                      />
                    ))}
                  </div>
                  <span className="text-[0.8rem] text-faint">
                    {t.seated}/{t.max}
                  </span>
                  <span
                    className={`ml-auto rounded-full border px-2.5 py-0.5 text-[0.78rem] transition-opacity duration-300 ${
                      BAND_TONE[t.band]
                    } ${stage === 0 ? 'opacity-0' : 'opacity-100'}`}
                  >
                    health {t.health} · {t.band}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        <StageControl
          label={stage === 0 ? 'Rank by health' : 'Replay'}
          stage={stage}
          total={2}
          onAdvance={() => setStage(stage === 0 ? 1 : 0)}
        />
      </div>
    </Slide>
  )
}

export const rankHealthSlide: SlideDef = {
  id: 'a-rank-health',
  label: 'Rank by health',
  Component: RankHealthSlide,
}
