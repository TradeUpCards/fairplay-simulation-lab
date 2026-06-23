import { useState } from 'react'
import type { IntegrityAssessment, IntegrityBand, ReasonCode } from '../data/types'
import { humanize } from '../lib/evals'

// integrity-band chip palette (the `tone` is the colour trio over a shared box)
const INTEGRITY_BAND: Record<IntegrityBand, { label: string; tone: string }> = {
  low: { label: 'Low', tone: 'border-[#2f6a8a] bg-[#1a2c3a] text-[#8fd0ef]' },
  neutral: { label: 'Neutral', tone: 'border-[#2f6a8a] bg-[#1a2c3a] text-[#8fd0ef]' },
  high: { label: 'High', tone: 'border-[#b3455a] bg-[#3a1a1f] text-[#ff9b9b]' },
  manual_review: { label: 'Manual review', tone: 'border-[#8a5f2f] bg-[#3a2a1a] text-[#efc28f]' },
}

// the case's 3px left edge, coloured by band severity
const BAND_BORDER: Record<IntegrityBand, string> = {
  low: 'border-l-[#2f6a8a]',
  neutral: 'border-l-[#2f6a8a]',
  high: 'border-l-[#b3455a]',
  manual_review: 'border-l-[#8a5f2f]',
}

const ACTION_LABEL: Record<string, string> = {
  monitor: 'Keep monitoring',
  hold_for_pitboss_review: 'Hold seat for pit-boss review',
  route_to_bot_review_queue: 'Route to bot-review queue',
}

// Operator actions per PRD §5 — never "ban", never auto-executed.
const OPERATOR_ACTIONS = ['accept', 'override', 'monitor', 'suppress', 'escalate'] as const
const OP_LABEL: Record<(typeof OPERATOR_ACTIONS)[number], string> = {
  accept: 'Accept recommendation',
  override: 'Override',
  monitor: 'Monitor',
  suppress: 'Suppress table for player',
  escalate: 'Escalate to review',
}

function BandChip({ band }: { band: IntegrityBand }) {
  const meta = INTEGRITY_BAND[band]
  return (
    <span className={`rounded-full border px-2 py-[0.12rem] text-[0.72rem] ${meta.tone}`}>
      {meta.label}
    </span>
  )
}

function Finding({ reason, muted = false }: { reason: ReasonCode; muted?: boolean }) {
  return (
    <div className={`mb-2${muted ? ' opacity-75' : ''}`}>
      <span className="text-[0.74rem] font-semibold text-[#b8c0cf]">{humanize(reason.code)}</span>
      <p className="m-0 mt-[0.1rem] text-[0.8rem] text-[#9aa2b3]">{reason.detail}</p>
    </div>
  )
}

/**
 * Folded integrity case for a flagged table. Hard guardrails made structural:
 * counter-evidence renders NEXT TO the signal families (never hidden); the
 * framing is uncertainty, not accusation; `recommended_action` is offered as a
 * choice the operator confirms — never auto-executed, never a ban. A neutral/low
 * band reads as "monitor, not escalated" (the household false-positive beat).
 */
export function IntegrityCase({ assessment }: { assessment: IntegrityAssessment }) {
  const [decision, setDecision] = useState<(typeof OPERATOR_ACTIONS)[number] | null>(null)
  const escalated = assessment.band === 'high' || assessment.band === 'manual_review'

  return (
    <article
      className={`rounded-[10px] border border-l-[3px] border-line bg-surface px-[0.95rem] py-[0.85rem] ${BAND_BORDER[assessment.band]}`}
      data-testid="integrity-case"
      data-band={assessment.band}
      aria-label={`integrity case ${assessment.group_id}`}
    >
      <header className="flex flex-wrap items-center gap-[0.6rem]">
        <span className="font-bold">{assessment.group_id}</span>
        <span className="text-[0.82rem] text-[#9aa2b3]">{humanize(assessment.group_kind)}</span>
        <BandChip band={assessment.band} />
        <span className="text-[0.74rem] text-faint">{assessment.convergence_count} converging</span>
      </header>

      <p className="my-2 text-[0.82rem] italic text-[#c3c9d6]" role="note">
        {escalated
          ? 'Elevated for review — not a determination that anyone cheated. A human decides.'
          : 'Monitor only — not escalated. Signals do not converge enough to act.'}
      </p>

      <div className="grid grid-cols-2 gap-4 max-[560px]:grid-cols-1">
        <section aria-label="signal families">
          <h4 className="m-0 mb-[0.4rem] text-[0.8rem] text-muted">
            Signal families ({assessment.signal_families.length})
          </h4>
          {assessment.signal_families.map((s) => (
            <Finding key={s.code} reason={s} />
          ))}
          {assessment.corroborating.length > 0 && (
            <div>
              <h5 className="mb-[0.3rem] mt-2 text-[0.72rem] font-semibold text-faint">
                Corroborating — context, not counted toward the band
              </h5>
              {assessment.corroborating.map((c) => (
                <Finding key={c.code} reason={c} muted />
              ))}
            </div>
          )}
        </section>

        <aside className="border-l-2 border-l-[#2f6a8a] pl-3" aria-label="counter-evidence">
          <h4 className="m-0 mb-[0.4rem] text-[0.8rem] text-muted">Counter-evidence</h4>
          {assessment.counter_evidence.length > 0 ? (
            assessment.counter_evidence.map((c) => <Finding key={c.code} reason={c} />)
          ) : (
            <p className="m-0 text-[0.8rem] text-muted">
              No exculpatory counter-evidence — {assessment.signal_families.length} signal families
              converge.
            </p>
          )}
        </aside>
      </div>

      {assessment.note && (
        <p className="mt-[0.6rem] border-t border-dashed border-line pt-2 text-[0.78rem] text-muted">
          {assessment.note}
        </p>
      )}

      <div className="mt-[0.7rem]">
        <p className="m-0 mb-[0.4rem] text-[0.85rem]">
          Recommended:{' '}
          <strong>{ACTION_LABEL[assessment.recommended_action] ?? humanize(assessment.recommended_action)}</strong>
        </p>
        <div className="flex flex-wrap gap-[0.4rem]">
          {OPERATOR_ACTIONS.map((action) => (
            <button
              key={action}
              type="button"
              className={action === 'accept' ? 'border-[#2f7d4a] bg-[#16341f] text-[#8be3a7]' : undefined}
              onClick={() => setDecision(action)}
            >
              {OP_LABEL[action]}
            </button>
          ))}
        </div>
        {decision && (
          <p className="mt-2 text-[0.8rem] text-[#8be3a7]" role="status" data-testid="operator-decision">
            Operator decision: <strong>{OP_LABEL[decision]}</strong> · logged for review (no automatic
            action taken)
          </p>
        )}
      </div>
    </article>
  )
}
