import t05PitBoss from '../../assets/t05-pitboss.png'
import { Slide, Bullets } from '../Slide'
import type { SlideDef } from '../types'

function TableSlide() {
  return (
    <Slide kicker="Pull back the curtain" title="Why FairPlay buries it">
      <div className="grid h-full grid-cols-[minmax(0,0.92fr)_1fr] items-center gap-8">
        <div className="grid h-full place-items-center overflow-hidden rounded-xl border border-line bg-[#0b0e13] p-2 shadow-[0_10px_24px_rgba(0,0,0,0.42)]">
          <img
            src={t05PitBoss}
            alt="Pit-boss view of T-05 — health 59 (fragile), predation and fragility bars, who's seated, why this rank"
            className="max-h-full max-w-full object-contain"
          />
        </div>
        <div className="flex flex-col gap-6">
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
                Standard says <span className="text-brass">&ldquo;it&apos;s full — join it.&rdquo;</span>{' '}
                FairPlay routes a recreational player <span className="text-[#5fcf8a]">away</span>.
              </>,
            ]}
          />
          <p className="m-0 max-w-[44ch] border-t border-dashed border-line pt-4 text-[0.92rem] text-faint">
            Reason codes are verbatim from the engine. A new player would barely move the table&apos;s
            health (ΔHealth <span className="text-[#5fcf8a]">+0.5</span>) — so it&apos;s{' '}
            <span className="text-text">seating-risk</span>, not health-delta, that protects them.
          </p>
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
