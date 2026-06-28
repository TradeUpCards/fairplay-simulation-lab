import { useState } from 'react'
import { Slide } from '../Slide'
import { useStageKeys } from '../useStageKeys'
import type { SlideDef } from '../types'

/**
 * "One iteration becomes the prompt for the next one." — the agentic
 * experiment loop. Ported from docs/learn/playsim-agentic-simulator-deck.html.
 * The original advanced through the four loop steps with the deck's Next
 * button; here the slide owns that staged reveal locally (slides are
 * components, so they can hold state) and is re-skinned to the ink/brass/felt
 * theme. ← / → still move between slides; the in-slide control steps the loop.
 */
const ARCH: { title: string; body: string }[] = [
  {
    title: 'Experiment spec',
    body: `{
  "policies": ["standard", "fairplay_liveness"],
  "sweep": {"tables": [4], "arrival_rate_per_hour": [60,72,84]},
  "max_sim_runs_per_experiment": 12
}`,
  },
  {
    title: 'Report finding',
    body: `FairPlay-liveness wins 1/3 cells.
Formation activates at high arrival pressure,
but vulnerable seat-hours decline.`,
  },
  {
    title: 'Next spec proposal',
    body: `Replicate the least-negative high-pressure cell
across more seeds before changing scoring.`,
  },
]

const STEPS: { title: string; desc: string }[] = [
  { title: 'LLM planner', desc: 'Reads prior results and proposes a bounded JSON experiment spec.' },
  {
    title: 'Validator',
    desc: 'Rejects unsupported knobs, oversized sweeps, and invalid policy comparisons.',
  },
  {
    title: 'Deterministic workers',
    desc: 'Run Standard and FairPlay-liveness against the same seeded demand stream.',
  },
  {
    title: 'Evaluator + report',
    desc: 'Aggregates seat-hours, vulnerable seat-hours, demand drop, exits, and formation metrics.',
  },
]

const STAGE_LABELS = ['Run Sweep', 'Evaluate', 'Plan Next', 'Replay']

function AgenticSlide() {
  const [stage, setStage] = useState(0)
  const advance = () => setStage((s) => (s >= STEPS.length - 1 ? 0 : s + 1))
  // → / ← step through the loop stages before the deck moves on
  useStageKeys(stage, STEPS.length, setStage)

  return (
    <Slide kicker="Agentic loop architecture" title="One iteration becomes the prompt for the next one.">
      <div className="flex flex-col gap-6">
        <div className="grid gap-6" style={{ gridTemplateColumns: 'minmax(0,0.82fr) minmax(0,1.18fr)' }}>
          {/* left: the artifacts that flow around the loop */}
          <div className="flex flex-col gap-3">
            {ARCH.map((a) => (
              <div key={a.title} className="rounded-xl border border-line bg-surface p-4">
                <div className="font-mono text-[0.72rem] uppercase tracking-[0.18em] text-brass">
                  {a.title}
                </div>
                <pre className="m-0 mt-2 whitespace-pre-wrap font-mono text-[0.78rem] leading-snug text-[#c8d0de]">
                  {a.body}
                </pre>
              </div>
            ))}
          </div>

          {/* right: the four-step loop, revealed one at a time */}
          <div className="flex flex-col gap-2.5">
            {STEPS.map((step, i) => {
              const revealed = i <= stage
              const active = i === stage
              return (
                <div
                  key={step.title}
                  className="flex items-start gap-4 rounded-xl border p-4 transition-all duration-300"
                  style={{
                    opacity: revealed ? 1 : 0.32,
                    transform: revealed ? 'translateY(0)' : 'translateY(8px)',
                    borderColor: active ? 'rgba(95,207,138,0.5)' : 'var(--color-line)',
                    background: active ? 'rgba(95,207,138,0.08)' : 'var(--color-surface)',
                  }}
                >
                  <span
                    className="mt-0.5 grid h-8 w-8 flex-none place-items-center rounded-full font-mono text-[0.85rem] font-bold"
                    style={{
                      background: active ? '#2f8f5b' : '#1d2531',
                      color: active ? '#eafff3' : '#8b93a7',
                    }}
                  >
                    {i + 1}
                  </span>
                  <div>
                    <h3 className="m-0 text-[1.25rem] font-semibold leading-tight text-text">
                      {step.title}
                    </h3>
                    <p className="mt-1 text-[1rem] leading-snug text-[#c8d0de]">{step.desc}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <StageControl
          label={STAGE_LABELS[stage]}
          stage={stage}
          total={STEPS.length}
          onAdvance={advance}
        />
      </div>
    </Slide>
  )
}

/** In-slide staged-reveal control: an action button + progress dots. */
export function StageControl({
  label,
  stage,
  total,
  onAdvance,
}: {
  label: string
  stage: number
  total: number
  onAdvance: () => void
}) {
  return (
    <div className="flex items-center gap-4">
      <button
        type="button"
        onClick={onAdvance}
        className="rounded-full border border-brass bg-[rgba(199,154,75,0.12)] px-5 py-2 text-[0.95rem] font-semibold text-brass transition-colors hover:bg-[rgba(199,154,75,0.22)]"
      >
        {label} →
      </button>
      <div className="flex gap-1.5" aria-hidden="true">
        {Array.from({ length: total }, (_, i) => (
          <span
            key={i}
            className="h-[0.45rem] w-[0.45rem] rounded-full transition-colors"
            style={{ background: i <= stage ? '#c79a4b' : '#3a4757' }}
          />
        ))}
      </div>
    </div>
  )
}

export const agenticSlide: SlideDef = {
  id: 'agentic-loop',
  label: 'Agentic loop',
  Component: AgenticSlide,
}
