import { Slide, Card, Columns } from '../Slide'
import type { SlideDef } from '../types'

/**
 * "The routing score." Dean's mechanism in one view: the weighted rank formula
 * with its three contributions filling as bars on mount, then the two hard gates
 * that sit on top (integrity removal, vulnerable-player protection). Scoped CSS
 * under `.ars`; bars animate via scaleX so they replay each time the slide shows.
 */
const CSS = `
.ars .track { position:relative; height:18px; border-radius:999px; background:#11161f; border:1px solid #232a36; overflow:hidden; }
.ars .track > span { position:absolute; inset:0; transform-origin:left; transform:scaleX(0); animation:arsFill 1s cubic-bezier(.22,1,.36,1) forwards; }
@keyframes arsFill { to { transform:scaleX(1); } }
@media (prefers-reduced-motion: reduce){ .ars .track > span { animation:none; transform:scaleX(1);} }
`

const PARTS: { label: string; weight: number; color: string; note: string }[] = [
  { label: 'Fit', weight: 0.3, color: '#c79a4b', note: 'does the player match the table style' },
  { label: 'Health', weight: 0.4, color: '#5fb0d9', note: 'predicted table health (0–100)' },
  {
    label: 'ΔHealth',
    weight: 0.3,
    color: '#5fcf8a',
    note: 'marginal effect of this player joining',
  },
]

function ScoreSlide() {
  return (
    <Slide kicker="Our approach · the score" title="One rank, two hard gates.">
      <div className="ars flex flex-col gap-7">
        <style>{CSS}</style>

        <div className="rounded-xl border border-t-2 border-t-brass border-line bg-surface p-5">
          <div className="font-mono text-[1.35rem] font-bold tracking-tight text-brass">
            Rank = 0.30·Fit + 0.40·Health + 0.30·ΔHealth
          </div>
          <div className="mt-5 flex flex-col gap-3">
            {PARTS.map((p, i) => (
              <div key={p.label} className="flex items-center gap-4">
                <span className="w-20 text-[0.95rem] font-semibold text-text">{p.label}</span>
                <div className="track flex-1" style={{ maxWidth: `${p.weight * 100 * 2.2}%` }}>
                  <span style={{ background: p.color, animationDelay: `${0.15 + i * 0.18}s` }} />
                </div>
                <span className="w-10 font-mono text-[0.85rem] text-faint">
                  {p.weight.toFixed(2)}
                </span>
                <span className="hidden flex-1 text-[0.85rem] text-muted min-[820px]:block">
                  {p.note}
                </span>
              </div>
            ))}
          </div>
        </div>

        <Columns cols={2}>
          <Card>
            <div className="flex items-center gap-2">
              <span className="text-[1.1rem]">🚫</span>
              <div className="font-mono text-[0.78rem] uppercase tracking-[0.18em] text-[#e38b8b]">
                Integrity gate
              </div>
            </div>
            <p className="mt-2 text-[0.98rem] leading-relaxed text-muted">
              A table with an active flagged cluster — collusion, shared devices — is{' '}
              <span className="text-text">removed from recommendations entirely</span>, not just
              ranked down.
            </p>
          </Card>
          <Card>
            <div className="flex items-center gap-2">
              <span className="text-[1.1rem]">🛡️</span>
              <div className="font-mono text-[0.78rem] uppercase tracking-[0.18em] text-[#8fd0ef]">
                Vulnerable-player gate
              </div>
            </div>
            <p className="mt-2 text-[0.98rem] leading-relaxed text-muted">
              A new or recreational player is only promoted toward{' '}
              <span className="text-text">low-risk seats</span>. Highest rank wins — but only past
              both gates.
            </p>
          </Card>
        </Columns>
      </div>
    </Slide>
  )
}

export const scoreSlide: SlideDef = {
  id: 'a-score',
  label: 'The routing score',
  Component: ScoreSlide,
}
