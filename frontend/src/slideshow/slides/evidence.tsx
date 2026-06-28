import { Slide } from '../Slide'
import type { SlideDef } from '../types'

/**
 * "We needed evidence" — the simulation problem and its three knob groups.
 * Ported from docs/learn/playsim-agentic-simulator-deck.html, re-skinned from
 * that deck's light/teal look to this deck's ink + brass + felt theme.
 */
const KNOBS: { accent: string; title: string; desc: string; chips: string[] }[] = [
  {
    accent: '#5fcf8a',
    title: 'Room Dynamics',
    desc: 'Controls the shape of the poker room and how much demand enters the room.',
    chips: ['total tables', 'active tables', 'arrival rate', 'horizon', 'seeds'],
  },
  {
    accent: '#c79a4b',
    title: 'Player Behavior',
    desc: 'Controls how players respond to thin tables, bad fit, waits, exits, and re-seat opportunities.',
    chips: ['formation-aware', 'reason-aware', 'wait tolerance', 're-seat intent'],
  },
  {
    accent: '#e0697f',
    title: 'Routing / Scoring',
    desc: 'Controls the policy comparison and any named scorer variants that remain outside production defaults.',
    chips: ['standard', 'fairplay-liveness', 'health floors', 'liveness weighting'],
  },
]

function EvidenceSlide() {
  return (
    <Slide kicker="The simulation problem" title="We needed evidence">
      <div className="flex flex-col gap-8">
        <p className="m-0 max-w-[60ch] text-[1.5rem] leading-snug text-text">
          Under which assumptions does <span className="text-[#5fcf8a]">FairPlay-liveness</span> beat
          Standard, where does it fail, and what should we tune next?
        </p>

        <div className="grid gap-5" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
          {KNOBS.map((k) => (
            <div
              key={k.title}
              className="rounded-xl border border-line bg-surface p-6 shadow-[0_10px_24px_rgba(0,0,0,0.38)]"
              style={{ borderTop: `4px solid ${k.accent}` }}
            >
              <h3 className="m-0 text-[1.45rem] font-semibold leading-tight text-text">{k.title}</h3>
              <p className="mt-3 text-[1.02rem] leading-relaxed text-[#c8d0de]">{k.desc}</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {k.chips.map((c) => (
                  <span
                    key={c}
                    className="rounded-full border border-line bg-surface-2 px-3 py-1 text-[0.85rem] tracking-wide text-muted"
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Slide>
  )
}

export const evidenceSlide: SlideDef = {
  id: 'why-simulate',
  label: 'Why simulate',
  Component: EvidenceSlide,
}
