import { Slide, Card, Columns } from '../Slide'
import type { SlideDef } from '../types'

function EconomicsSlide() {
  return (
    <Slide kicker="How the house makes money" title="Two ways to monetize a table">
      <div className="flex flex-col gap-7">
        <Columns cols={2}>
          <Card>
            <div className="font-mono text-[0.8rem] uppercase tracking-[0.2em] text-muted">
              Rake
            </div>
            <div className="mt-2 text-[1.3rem] font-semibold text-text">A cut of every pot</div>
            <p className="mt-3 text-[1rem] leading-relaxed text-muted">
              Revenue scales with the number of pots and the stakes. Fast, aggressive tables can
              rake hard — even while they burn through recreational players.
            </p>
          </Card>
          <Card brassTop>
            <div className="font-mono text-[0.8rem] uppercase tracking-[0.2em] text-brass">
              Seat rental
            </div>
            <div className="mt-2 text-[1.3rem] font-semibold text-text">
              A charge per unit of time
            </div>
            <p className="mt-3 text-[1rem] leading-relaxed text-muted">
              Revenue scales directly with time seated. The more players you keep at the table — and
              the longer they stay — the more you earn.
            </p>
          </Card>
        </Columns>

        <p className="m-0 max-w-[60ch] text-[1.25rem] leading-snug text-text">
          Under a seat-rental model, the business is the duration of play. Churning hands isn&apos;t
          the goal — <span className="text-brass">retained seat-time</span> is.
        </p>
      </div>
    </Slide>
  )
}

export const economicsSlide: SlideDef = {
  id: 'economics',
  label: 'The model',
  Component: EconomicsSlide,
}
