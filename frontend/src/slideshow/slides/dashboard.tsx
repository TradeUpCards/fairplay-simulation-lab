import { Slide, Stat, Columns, Card, Placeholder } from '../Slide'
import type { SlideDef } from '../types'

function DashboardSlide() {
  return (
    <Slide kicker="4 · Does it work?" title="An 8-hour A/B across the whole room">
      <div className="flex flex-col gap-6">
        <p className="m-0 max-w-[70ch] text-[1.1rem] leading-relaxed text-muted">
          600 synthetic players, up to 50 tables, six capacity regimes × three seeds — a closed-loop
          simulation that&apos;s fully{' '}
          <span className="text-text">deterministic and replayable</span>. Same policy seated
          everyone the standard way, then the FairPlay way.
        </p>

        <Columns cols={3}>
          <Stat value="+0.64%" label="Avg seat-hours" sub="FairPlay vs Standard" tone="felt" />
          <Stat value="+1.98%" label="Best regime" sub="50 tables · 20 joins/hr" tone="felt" />
          <Stat value="+24 hrs" label="Retained seat-time" sub="1,202 → 1,226, that regime" />
        </Columns>

        <Columns cols={2}>
          <Card>
            <p className="m-0 text-[0.98rem] leading-relaxed text-muted">
              The win is <span className="text-text">duration</span>, not departures — roughly the
              same players leave, but FairPlay keeps them seated longer through better table
              composition. No enforcement, pure routing.
            </p>
          </Card>
          {/* COLLEAGUE: embed the live replay chart here, or just switch to the
              real dashboard at #/dashboard during the talk. Component:
              src/components/SweepReplayChart.tsx (used by src/views/Dashboard.tsx). */}
          <Placeholder title="Live replay chart">
            Embed <code>SweepReplayChart</code> here, or present the real <code>#/dashboard</code>{' '}
            live.
          </Placeholder>
        </Columns>
      </div>
    </Slide>
  )
}

export const dashboardSlide: SlideDef = {
  id: 'dashboard',
  label: 'The results',
  Component: DashboardSlide,
}
