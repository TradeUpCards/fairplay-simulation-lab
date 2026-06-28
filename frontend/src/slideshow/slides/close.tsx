import { Slide, Pill } from '../Slide'
import type { SlideDef } from '../types'

function CloseSlide() {
  return (
    <Slide center>
      <div className="flex flex-col gap-8">
        <h2 className="m-0 text-[3rem] font-bold leading-[1.05] tracking-[-0.01em] text-text">
          Recommend. Explain.
          <br />
          Human decides.
        </h2>

        <div className="flex flex-wrap items-center gap-2 text-[0.95rem]">
          <Pill tone="brass">Lobby recommendation</Pill>
          <span className="text-faint">→</span>
          <Pill tone="brass">Pit-boss review / override</Pill>
          <span className="text-faint">→</span>
          <Pill tone="brass">Standard-vs-FairPlay simulation</Pill>
          <span className="text-faint">→</span>
          <Pill tone="brass">Eval evidence</Pill>
        </div>

        <p className="m-0 max-w-[58ch] text-[1.25rem] leading-snug text-muted">
          Healthier tables keep recreational players in their seats longer — and that&apos;s the
          revenue. The system finds the risk and explains it; the operator makes the call.
        </p>

        <p className="m-0 flex items-center gap-[0.55rem] font-mono text-[0.72rem] uppercase tracking-[0.22em] text-faint">
          <span className="h-2 w-2 rounded-full bg-felt shadow-[0_0_0_3px_rgba(47,143,91,0.18)]" />
          Synthetic data · responsible-use modeling
        </p>
      </div>
    </Slide>
  )
}

export const closeSlide: SlideDef = {
  id: 'close',
  label: 'Close',
  Component: CloseSlide,
}
