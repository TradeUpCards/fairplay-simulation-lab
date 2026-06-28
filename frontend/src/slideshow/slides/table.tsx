import { Slide, Placeholder } from '../Slide'
import type { SlideDef } from '../types'

function TableSlide() {
  return (
    <Slide kicker="2 · Zoom in" title="Focus on a single table">
      <div className="flex h-full flex-col gap-5">
        <p className="m-0 max-w-[64ch] text-[1.15rem] leading-relaxed text-muted">
          On the pit-boss console, the same table reads very differently: a{' '}
          <span className="text-text">seat ring</span> with each player&apos;s{' '}
          <span className="text-text">propensity-to-leave</span> heat, a composite{' '}
          <span className="text-text">health score</span>, and any integrity flags — operator-only.
        </p>
        {/* COLLEAGUE: drop the live pit-boss table view (SeatRing + health score)
            or a screenshot here. Components: src/views/PitBossTable.tsx,
            src/components/SeatRing.tsx. */}
        <Placeholder title="Pit-boss table view">
          Seat ring · health score · propensity-to-leave heat. Swap this for the live{' '}
          <code>PitBossTable</code> / <code>SeatRing</code> or a screenshot.
        </Placeholder>
      </div>
    </Slide>
  )
}

export const tableSlide: SlideDef = {
  id: 'table',
  label: 'The table',
  Component: TableSlide,
}
