import { Slide } from '../Slide'
import type { SlideDef } from '../types'

/**
 * The market slide — an animated "chip chart": online-poker revenue climbing from
 * today ($6B, 2025) to the 2034 projection ($20B) as an ascending ramp of poker-
 * chip stacks (each chip ≈ $1B). The stacks rise left-to-right and the tallest —
 * the $20B destination — is brass; the rest are white. The CAGR growth metric is
 * overlaid above the ramp. Pure CSS keyframes, scoped under `.icz`, so the stacks
 * rebuild every time the slide is shown.
 */
type Col = { count: number; variant: 'brass' | 'white'; value?: string; year?: string }
const STACKS: Col[] = [
  { count: 6, variant: 'white', value: '$6B', year: '2025 — today' },
  { count: 8, variant: 'white' },
  { count: 11, variant: 'white' },
  { count: 14, variant: 'white' },
  { count: 17, variant: 'white' },
  { count: 20, variant: 'brass', value: '$20B', year: '2034 — projected' },
]

const CSS = `
.icz .chartWrap { display:flex; justify-content:center; }
.icz .chart { position:relative; display:inline-flex; align-items:flex-end; gap:1.6rem; }
.icz .col { display:flex; flex-direction:column; align-items:center; }
.icz .stack { display:flex; flex-direction:column; align-items:center; }
.icz .value { margin-bottom:0.6rem; }
.icz .year { min-height:1.4rem; margin-top:0.8rem; }
.icz .cagr { position:absolute; left:0; top:0; display:flex; flex-direction:column; align-items:flex-start; gap:0.45rem; }
.icz .chip {
  position:relative; width:90px; height:24px; border-radius:50%; margin-top:-14px;
  border:1px solid var(--rim); background:var(--face);
  box-shadow:0 2px 0 var(--side), 0 5px 8px rgba(0,0,0,0.45);
  animation:iczDrop .5s cubic-bezier(.2,1.05,.4,1) backwards;
}
.icz .chip:first-child { margin-top:0; }
.icz .chip::before {
  content:''; position:absolute; inset:0; border-radius:50%;
  background:repeating-conic-gradient(from 0deg, rgba(0,0,0,0.16) 0 9deg, transparent 9deg 24deg);
}
.icz .chip::after {
  content:''; position:absolute; inset:5px 26px; border-radius:50%; border:1px dashed var(--ring);
}
.icz .chip.brass { --face:radial-gradient(ellipse at 50% 36%, #ecc77c, #bd8a3c 58%, #8a6326); --rim:#6f521f; --side:#7a5a26; --ring:rgba(255,243,214,0.55); }
.icz .chip.white { --face:radial-gradient(ellipse at 50% 36%, #ffffff, #e2e5ec 58%, #b7bdc9); --rim:#9aa0ad; --side:#aeb4c0; --ring:rgba(90,98,112,0.5); }
@keyframes iczDrop { from { transform:translateY(-28px); opacity:0; } to { transform:translateY(0); opacity:1; } }
@media (prefers-reduced-motion: reduce){ .icz .chip { animation:none; } }
`

function ChipStack({
  count,
  variant,
  baseDelay = 0,
}: {
  count: number
  variant: 'brass' | 'white'
  baseDelay?: number
}) {
  return (
    <div className="stack" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <span
          key={i}
          className={`chip ${variant}`}
          // top chip paints over lower ones; build bottom-to-top
          style={{ zIndex: count - i, animationDelay: `${baseDelay + (count - 1 - i) * 0.06}s` }}
        />
      ))}
    </div>
  )
}

function IndustrySlide() {
  return (
    <Slide
      kicker="The market"
      title="Online poker is a multi-billion-dollar business — and growing"
    >
      <div className="icz flex flex-col">
        <style>{CSS}</style>

        <div className="chartWrap">
          <div className="chart">
            <div className="cagr">
              <span className="text-[2rem] leading-none text-brass">↗</span>
              <span className="rounded-full border border-brass/40 bg-surface-2 px-3.5 py-1.5 font-mono text-[0.95rem] font-semibold tracking-wider text-brass">
                12–15% CAGR
              </span>
            </div>

            {STACKS.map((s, idx) => (
              <div key={idx} className="col">
                {s.value && (
                  <div
                    className={`value font-mono text-[2.1rem] font-bold leading-none ${
                      s.variant === 'brass' ? 'text-brass' : 'text-text'
                    }`}
                  >
                    {s.value}
                  </div>
                )}
                <ChipStack count={s.count} variant={s.variant} baseDelay={idx * 0.12} />
                <div className="year text-[1rem] text-text">{s.year ?? ''}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Slide>
  )
}

export const industrySlide: SlideDef = {
  id: 'industry',
  label: 'The market',
  Component: IndustrySlide,
}
