import pokerTable from '../../assets/poker-table.png'
import { SeatAvatar, seatPositions } from '../../components/tableArt'
import { Slide } from '../Slide'
import type { SlideDef } from '../types'

/**
 * "A table can run all night and still empty out." The emotional core of the
 * problem: two real felt tables side by side (same poker-table art + seat ring as
 * the rest of the app). The healthy one holds its seats with a felt-green pulse;
 * the predatory one bleeds — the recreational seats go hot, then leave, on a loop.
 * Pure CSS keyframes, scoped under `.pd`, so it replays whenever the slide shows.
 */
type Anim = 'stay' | 'l1' | 'l2' | 'l3'
type Seat = { arch: string; anim: Anim; hot?: boolean }

const HEALTHY: Seat[] = [
  { arch: 'healthy_anchor', anim: 'stay' },
  { arch: 'recreational', anim: 'stay' },
  { arch: 'regular', anim: 'stay' },
  { arch: 'new', anim: 'stay' },
  { arch: 'recreational', anim: 'stay' },
  { arch: 'grinder', anim: 'stay' },
]

const PREDATORY: Seat[] = [
  { arch: 'recreational', anim: 'l1', hot: true },
  { arch: 'aggressive_predatory', anim: 'stay' },
  { arch: 'regular', anim: 'l2' },
  { arch: 'aggressive_predatory', anim: 'stay' },
  { arch: 'recreational', anim: 'l3', hot: true },
  { arch: 'grinder', anim: 'stay' },
]

const POS = seatPositions(6, 50, 44)

const CSS = `
.pd .seat { animation-duration:9s; animation-iteration-count:infinite; animation-timing-function:ease-in-out; }
.pd .seat.l1 { animation-name:pdL1; }
.pd .seat.l2 { animation-name:pdL2; }
.pd .seat.l3 { animation-name:pdL3; }
@keyframes pdL1 { 0%,22%{opacity:1;transform:translate(-50%,-50%) scale(1);} 32%,95%{opacity:0;transform:translate(-50%,-50%) scale(.35);} 100%{opacity:1;transform:translate(-50%,-50%) scale(1);} }
@keyframes pdL2 { 0%,42%{opacity:1;transform:translate(-50%,-50%) scale(1);} 52%,95%{opacity:0;transform:translate(-50%,-50%) scale(.35);} 100%{opacity:1;transform:translate(-50%,-50%) scale(1);} }
@keyframes pdL3 { 0%,60%{opacity:1;transform:translate(-50%,-50%) scale(1);} 70%,95%{opacity:0;transform:translate(-50%,-50%) scale(.35);} 100%{opacity:1;transform:translate(-50%,-50%) scale(1);} }
.pd .hot { border-radius:50%; animation:pdHot 9s ease-in-out infinite; }
@keyframes pdHot { 0%,12%{box-shadow:0 0 0 0 rgba(255,123,123,0);} 18%,28%{box-shadow:0 0 0 4px rgba(255,123,123,0.6);} 34%,100%{box-shadow:0 0 0 0 rgba(255,123,123,0);} }
@media (prefers-reduced-motion: reduce){ .pd .seat,.pd .hot{ animation:none !important; } }
`

function FeltTable({ seats }: { seats: Seat[] }) {
  return (
    <div className="relative mx-auto aspect-3/2 w-[19rem] max-w-full">
      <img
        src={pokerTable}
        className="absolute inset-0 h-full w-full rounded-[14px] object-cover"
        alt=""
        aria-hidden="true"
      />
      {POS.map((p, i) => {
        const s = seats[i]
        return (
          <div
            key={i}
            className={`seat ${s.anim} absolute -translate-x-1/2 -translate-y-1/2`}
            style={{ left: p.left, top: p.top }}
          >
            <div className={s.hot ? 'hot' : ''}>
              <SeatAvatar archetype={s.arch} label={`pd-${i}-${s.arch}`} size="sm" />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function DecaySlide() {
  return (
    <Slide kicker="The problem · table health" title="A busy table can still empty out.">
      <div className="pd flex flex-col gap-7">
        <style>{CSS}</style>
        <div className="grid gap-8" style={{ gridTemplateColumns: 'repeat(2, minmax(0,1fr))' }}>
          <div className="flex flex-col items-center gap-3">
            <div className="rounded-[16px] p-1 animate-live-pulse">
              <FeltTable seats={HEALTHY} />
            </div>
            <div className="text-center">
              <div className="text-[1.05rem] font-semibold text-[#8be3a7]">Healthy mix</div>
              <div className="text-[0.85rem] text-muted">players stay · seats stay full</div>
            </div>
          </div>

          <div className="flex flex-col items-center gap-3">
            <div className="rounded-[16px] p-1 ring-1 ring-[#8a3a3a]/50">
              <FeltTable seats={PREDATORY} />
            </div>
            <div className="text-center">
              <div className="text-[1.05rem] font-semibold text-[#e38b8b]">Predator pile-up</div>
              <div className="text-[0.85rem] text-muted">
                the recreational players bust and leave
              </div>
            </div>
          </div>
        </div>

        <p className="m-0 max-w-[68ch] text-[1.25rem] leading-snug text-text">
          Same hands dealt all night. One table holds its seat-hours; the other{' '}
          <span className="text-[#e38b8b]">bleeds them out</span>. The difference is{' '}
          <span className="text-brass">who&apos;s sitting there</span> — and standard seating never
          looks.
        </p>
      </div>
    </Slide>
  )
}

export const decaySlide: SlideDef = {
  id: 'p-decay',
  label: 'Table decay',
  Component: DecaySlide,
}
