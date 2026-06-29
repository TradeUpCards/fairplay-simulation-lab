import { Slide, Card } from '../Slide'
import type { SlideDef } from '../types'
import chips from '../../assets/circular-poker-table-chips-transparent.png'
import clock from '../../assets/vintage-wall-clock-transparent.gif'

/**
 * "Two ways the house makes money." Rake vs seat-rental, illustrated with the
 * shared art assets instead of CSS shapes: a circular poker-table chip stack for
 * rake (a cut of every pot), and a vintage wall clock (animated GIF) for seat
 * rental — revenue that runs with time.
 */
function MoneySlide() {
  return (
    <Slide kicker="The problem · how the house makes money" title="Two ways to monetize a table">
      <div className="flex flex-col gap-7">
        <div className="grid gap-5" style={{ gridTemplateColumns: 'repeat(2, minmax(0,1fr))' }}>
          <Card>
            <div className="flex items-center gap-5">
              <img
                src={chips}
                alt=""
                aria-hidden="true"
                className="h-[120px] w-auto shrink-0 object-contain drop-shadow-[0_4px_12px_rgba(0,0,0,0.45)]"
              />
              <div>
                <div className="font-mono text-[0.8rem] uppercase tracking-[0.2em] text-muted">
                  Rake
                </div>
                <div className="mt-1 text-[1.25rem] font-semibold text-text">
                  A cut of every pot
                </div>
                <p className="mt-2 text-[0.95rem] leading-relaxed text-muted">
                  Scales with pots and stakes. A fast table can rake hard — even while it burns
                  through its recreational players.
                </p>
              </div>
            </div>
          </Card>

          <Card brassTop>
            <div className="flex items-center gap-5">
              <img
                src={clock}
                alt=""
                aria-hidden="true"
                className="h-[120px] w-auto shrink-0 object-contain drop-shadow-[0_4px_12px_rgba(0,0,0,0.45)]"
              />
              <div>
                <div className="font-mono text-[0.8rem] uppercase tracking-[0.2em] text-brass">
                  Seat rental
                </div>
                <div className="mt-1 text-[1.25rem] font-semibold text-text">
                  A charge per unit of time
                </div>
                <p className="mt-2 text-[0.95rem] leading-relaxed text-muted">
                  Scales directly with time seated. Keep more players, longer, and the meter runs.
                </p>
              </div>
            </div>
          </Card>
        </div>

        <p className="m-0 max-w-[62ch] text-[1.25rem] leading-snug text-text">
          Under a seat-rental model, the business is the duration of play. Churning hands isn&apos;t
          the goal — <span className="text-brass">retained seat-time</span> is.
        </p>
      </div>
    </Slide>
  )
}

export const moneySlide: SlideDef = {
  id: 'p-money',
  label: 'The model',
  Component: MoneySlide,
}
