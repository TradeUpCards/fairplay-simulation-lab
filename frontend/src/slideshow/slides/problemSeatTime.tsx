import { useEffect, useState } from 'react'
import { Slide } from '../Slide'
import { AnimatedNumber } from '../../components/AnimatedNumber'
import type { SlideDef } from '../types'

/**
 * "The product isn't hands — it's time in the seat." Opens Jordan's problem
 * section. Reuses the app's AnimatedNumber (the "watch the score recompute"
 * counter) to tick paid seat-hours up from zero, beside a session meter that
 * fills and a stack of chips that rises — all on mount, so it replays each time
 * the slide is shown. Scoped under `.pst` so the keyframes never leak.
 */
const CSS = `
.pst .meter { position:relative; height:14px; border-radius:999px; background:#11161f; border:1px solid #232a36; overflow:hidden; }
.pst .meter > span { position:absolute; inset:0; transform-origin:left; background:linear-gradient(90deg,#2f8f5b,#5fcf8a); animation:pstFill 1.8s cubic-bezier(.22,1,.36,1) forwards; }
@keyframes pstFill { from { transform:scaleX(0); } to { transform:scaleX(1); } }
.pst .chip { transform-origin:bottom; animation:pstRise 1.3s cubic-bezier(.22,1,.36,1) backwards; }
@keyframes pstRise { from { transform:scaleY(0); opacity:0; } to { transform:scaleY(1); opacity:1; } }
@media (prefers-reduced-motion: reduce){ .pst .meter>span{ animation:none; transform:scaleX(1);} .pst .chip{ animation:none; } }
`

function CountUp({ to }: { to: number }) {
  const [v, setV] = useState(0)
  useEffect(() => {
    const id = requestAnimationFrame(() => setV(to))
    return () => cancelAnimationFrame(id)
  }, [to])
  return (
    <AnimatedNumber value={v} durationMs={1700} format={(n) => Math.round(n).toLocaleString()} />
  )
}

function SeatTimeSlide() {
  return (
    <Slide
      kicker="The problem · the business"
      title="The product isn't hands. It's time in the seat."
    >
      <div className="pst flex flex-col gap-9">
        <style>{CSS}</style>
        <div
          className="grid items-center gap-10"
          style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,0.9fr)' }}
        >
          <div>
            <div className="font-mono text-[5.2rem] font-bold leading-none text-brass">
              <CountUp to={1883} />
            </div>
            <div className="mt-2 text-[1.15rem] text-text">paid seat-hours</div>
            <div className="text-[0.9rem] text-faint">one 8-hour room · 50 tables</div>
            <div className="mt-6 flex items-center gap-3">
              <span className="font-mono text-[0.7rem] uppercase tracking-[0.2em] text-muted">
                session
              </span>
              <div className="meter w-[15rem]">
                <span />
              </div>
            </div>
          </div>

          <div className="flex h-[12rem] items-end justify-center gap-2.5">
            {[36, 58, 74, 92, 116, 142, 170].map((h, i) => (
              <span
                key={i}
                className="chip w-8 rounded-t-md bg-[linear-gradient(180deg,#d8af5e,#8a6a2f)] shadow-[0_2px_8px_rgba(0,0,0,0.4)]"
                style={{ height: `${h}px`, animationDelay: `${i * 0.12}s` }}
              />
            ))}
          </div>
        </div>

        <p className="m-0 max-w-[64ch] text-[1.3rem] leading-snug text-text">
          Operators rent seats by the minute. Revenue scales with one thing —{' '}
          <span className="text-brass">how long players stay</span>. Keep them seated, and the meter
          runs.
        </p>
      </div>
    </Slide>
  )
}

export const seatTimeSlide: SlideDef = {
  id: 'p-seat-time',
  label: 'The business',
  Component: SeatTimeSlide,
}
