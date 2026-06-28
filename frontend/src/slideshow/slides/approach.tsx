import { Slide, Card, Bullets, Pill } from '../Slide'
import type { SlideDef } from '../types'

function ApproachSlide() {
  return (
    <Slide kicker="Our approach" title="Route players toward healthier tables">
      <div className="flex flex-col gap-7">
        <Card brassTop>
          <div className="font-mono text-[0.78rem] uppercase tracking-[0.2em] text-muted">
            Seating score
          </div>
          <div className="mt-3 font-mono text-[1.5rem] font-bold tracking-tight text-brass">
            Rank = 0.30 · Fit + 0.40 · Health + 0.30 · ΔHealth
          </div>
          <p className="mt-3 text-[0.95rem] text-faint">
            Deterministic, no model in the decision loop — the standard policy just fills the
            most-full table; FairPlay ranks by predicted table health instead.
          </p>
        </Card>

        <Bullets
          items={[
            <>
              <span className="text-text">Fit</span> — how well the player&apos;s style matches the
              table&apos;s.
            </>,
            <>
              <span className="text-text">Health</span> — predicted survival of the recreational
              cohort (loss velocity, winnings concentration, beginner bust-rate).
            </>,
            <>
              <span className="text-text">ΔHealth</span> — the marginal effect of this player
              joining.
            </>,
            <>
              <span className="text-text">Hard gates</span> — integrity-flagged tables are removed;
              vulnerable players are only promoted into low-risk seats.
            </>,
          ]}
        />

        <div className="flex flex-wrap gap-2">
          <Pill tone="felt">Recommend</Pill>
          <Pill tone="felt">Explain</Pill>
          <Pill tone="felt">Human decides</Pill>
          <Pill>Never accuse · never auto-enforce</Pill>
        </div>
      </div>
    </Slide>
  )
}

export const approachSlide: SlideDef = {
  id: 'approach',
  label: 'Our approach',
  Component: ApproachSlide,
}
