import { Slide } from '../Slide'
import type { SlideDef } from '../types'

/**
 * "We needed evidence" — the simulation problem and its three groups of
 * tunable knobs. Ported from docs/learn/playsim-agentic-simulator-deck.html and
 * re-skinned to this deck's ink + brass + felt theme. Each parameter is drawn
 * as a little control-panel dial.
 */
const KNOBS: { accent: string; title: string; params: { label: string; frac: number }[] }[] = [
  {
    accent: '#5fcf8a',
    title: 'Room Dynamics',
    params: [
      { label: 'total tables', frac: 0.55 },
      { label: 'active tables', frac: 0.4 },
      { label: 'arrival rate', frac: 0.72 },
      { label: 'horizon', frac: 0.5 },
      { label: 'seeds', frac: 0.3 },
    ],
  },
  {
    accent: '#c79a4b',
    title: 'Player Behavior',
    params: [
      { label: 'formation-aware', frac: 0.66 },
      { label: 'reason-aware', frac: 0.45 },
      { label: 'wait tolerance', frac: 0.58 },
      { label: 're-seat intent', frac: 0.36 },
    ],
  },
  {
    accent: '#e0697f',
    title: 'Routing / Scoring',
    params: [
      { label: 'standard', frac: 0.5 },
      { label: 'fairplay-liveness', frac: 0.78 },
      { label: 'health floors', frac: 0.42 },
      { label: 'liveness weighting', frac: 0.6 },
    ],
  },
]

// dial geometry: a 270° sweep, pointer up at the mid value
const A0 = -135
const A1 = 135
function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const rad = (deg * Math.PI) / 180
  return [cx + r * Math.sin(rad), cy - r * Math.cos(rad)]
}
function arc(cx: number, cy: number, r: number, a0: number, a1: number): string {
  const [x0, y0] = polar(cx, cy, r, a0)
  const [x1, y1] = polar(cx, cy, r, a1)
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0
  const sweep = a1 >= a0 ? 1 : 0
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} ${sweep} ${x1.toFixed(2)} ${y1.toFixed(2)}`
}

/** A control-panel knob: a value arc + a knob face with a pointer notch. */
function Dial({ label, frac, accent }: { label: string; frac: number; accent: string }) {
  const cx = 27
  const cy = 27
  const r = 21
  const a = A0 + frac * (A1 - A0)
  const [nx0, ny0] = polar(cx, cy, 4, a)
  const [nx1, ny1] = polar(cx, cy, 12, a)
  return (
    <div className="flex flex-col items-center gap-1.5">
      <svg viewBox="0 0 54 54" className="h-14 w-14" aria-hidden="true">
        <path d={arc(cx, cy, r, A0, A1)} fill="none" stroke="#29313f" strokeWidth={3.5} strokeLinecap="round" />
        <path d={arc(cx, cy, r, A0, a)} fill="none" stroke={accent} strokeWidth={3.5} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={13} fill="#0e131c" stroke="#2c3543" strokeWidth={1} />
        <line x1={nx0} y1={ny0} x2={nx1} y2={ny1} stroke={accent} strokeWidth={2.75} strokeLinecap="round" />
      </svg>
      <span className="text-center text-[1.32rem] leading-tight text-[#c8d0de]">{label}</span>
    </div>
  )
}

function EvidenceSlide() {
  return (
    <Slide kicker="The simulation problem" title="We needed evidence">
      <div className="flex flex-col gap-8">
        <p className="m-0 max-w-[60ch] text-[1.5rem] leading-snug text-text">
          Where does <span className="text-[#5fcf8a]">FairPlay</span> beat Standard, where does it
          fail, and what to tune next?
        </p>

        <div className="grid gap-5" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
          {KNOBS.map((k) => (
            <div
              key={k.title}
              className="rounded-xl border border-line bg-surface p-6 shadow-[0_10px_24px_rgba(0,0,0,0.38)]"
              style={{ borderTop: `4px solid ${k.accent}` }}
            >
              <h3 className="m-0 text-[1.45rem] font-semibold leading-tight text-text">{k.title}</h3>
              <div className="mt-6 grid grid-cols-3 gap-x-3 gap-y-5">
                {k.params.map((p) => (
                  <Dial key={p.label} label={p.label} frac={p.frac} accent={k.accent} />
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
