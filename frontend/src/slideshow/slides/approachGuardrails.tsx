import { useState } from 'react'
import { Slide, Pill } from '../Slide'
import { StageControl } from './agentic'
import { useStageKeys } from '../useStageKeys'
import type { SlideDef } from '../types'

/**
 * "Recommend → Explain → Human decides." The guardrail posture that sits over the
 * whole system, revealed one beat at a time (same staged reveal as the agentic
 * slide). The AI never detects and never enforces — it explains an evidence
 * packet and hands the call to a human. Closes Dean's approach section.
 */
const STEPS: { icon: string; title: string; body: string }[] = [
  {
    icon: '①',
    title: 'Recommend',
    body: 'Structured scoring surfaces the risk and proposes a seat — or flags a table for review.',
  },
  {
    icon: '②',
    title: 'Explain',
    body: 'The AI Investigator gets an evidence packet only — never raw data — and explains it, with uncertainty and counter-evidence.',
  },
  {
    icon: '③',
    title: 'Human decides',
    body: 'The operator accepts, overrides, or monitors. Nothing is automatic; the model never pulls the lever.',
  },
]

const GUARDRAILS = [
  'Never accuses',
  'Never auto-enforces',
  'Surfaces counter-evidence',
  'Uncertainty language',
  'Health risk ≠ integrity risk',
]

function GuardrailsSlide() {
  const [stage, setStage] = useState(0)
  useStageKeys(stage, STEPS.length, setStage)

  return (
    <Slide kicker="Our approach · the posture" title="Recommend. Explain. Human decides.">
      <div className="flex flex-col gap-8">
        <div
          className="grid items-stretch gap-3"
          style={{ gridTemplateColumns: 'repeat(3, minmax(0,1fr))' }}
        >
          {STEPS.map((s, i) => {
            const revealed = i <= stage
            const active = i === stage
            return (
              <div
                key={s.title}
                className="rounded-xl border p-5 transition-all duration-300"
                style={{
                  opacity: revealed ? 1 : 0.28,
                  transform: revealed ? 'translateY(0)' : 'translateY(10px)',
                  borderColor: active ? 'rgba(199,154,75,0.55)' : 'var(--color-line)',
                  background: active ? 'rgba(199,154,75,0.08)' : 'var(--color-surface)',
                }}
              >
                <div className="font-mono text-[1.4rem] text-brass">{s.icon}</div>
                <h3 className="m-0 mt-2 text-[1.3rem] font-semibold leading-tight text-text">
                  {s.title}
                </h3>
                <p className="mt-2 text-[0.98rem] leading-snug text-muted">{s.body}</p>
              </div>
            )
          })}
        </div>

        <div className="flex flex-col gap-3">
          <div className="font-mono text-[0.72rem] uppercase tracking-[0.2em] text-muted">
            The guardrails that always hold
          </div>
          <div className="flex flex-wrap gap-2">
            {GUARDRAILS.map((g) => (
              <Pill
                key={g}
                tone={g === 'Never accuses' || g === 'Never auto-enforces' ? 'brass' : 'neutral'}
              >
                {g}
              </Pill>
            ))}
          </div>
          <p className="m-0 max-w-[64ch] text-[1.05rem] leading-snug text-text">
            &ldquo;Elevated for review,&rdquo; never &ldquo;this player cheated.&rdquo; The bet:
            healthier tables keep players seated longer — and a human always stays in the loop.
          </p>
        </div>

        <StageControl
          label={stage >= STEPS.length - 1 ? 'Replay' : 'Next step'}
          stage={stage}
          total={STEPS.length}
          onAdvance={() => setStage((s) => (s >= STEPS.length - 1 ? 0 : s + 1))}
        />
      </div>
    </Slide>
  )
}

export const guardrailsSlide: SlideDef = {
  id: 'a-guardrails',
  label: 'Guardrails',
  Component: GuardrailsSlide,
}
