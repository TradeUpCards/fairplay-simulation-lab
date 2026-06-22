import { useState } from 'react'
import type { IntegrityAssessment, IntegrityBand, ReasonCode } from '../data/types'
import { humanize } from '../lib/evals'

const INTEGRITY_BAND: Record<IntegrityBand, { label: string; tone: string }> = {
  low: { label: 'Low', tone: 'ib-low' },
  neutral: { label: 'Neutral', tone: 'ib-neutral' },
  high: { label: 'High', tone: 'ib-high' },
  manual_review: { label: 'Manual review', tone: 'ib-manual' },
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
  return <span className={`ib-chip ${meta.tone}`}>{meta.label}</span>
}

function Finding({ reason, muted = false }: { reason: ReasonCode; muted?: boolean }) {
  return (
    <div className={`finding${muted ? ' finding-muted' : ''}`}>
      <span className="finding-code">{humanize(reason.code)}</span>
      <p className="finding-detail">{reason.detail}</p>
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
      className={`integrity-case band-${assessment.band}`}
      data-testid="integrity-case"
      data-band={assessment.band}
      aria-label={`integrity case ${assessment.group_id}`}
    >
      <header className="ic-head">
        <span className="ic-group">{assessment.group_id}</span>
        <span className="ic-kind">{humanize(assessment.group_kind)}</span>
        <BandChip band={assessment.band} />
        <span className="ic-conv">{assessment.convergence_count} converging</span>
      </header>

      <p className="ic-uncertainty" role="note">
        {escalated
          ? 'Elevated for review — not a determination that anyone cheated. A human decides.'
          : 'Monitor only — not escalated. Signals do not converge enough to act.'}
      </p>

      <div className="ic-evidence">
        <section className="ic-signals" aria-label="signal families">
          <h4>Signal families ({assessment.signal_families.length})</h4>
          {assessment.signal_families.map((s) => (
            <Finding key={s.code} reason={s} />
          ))}
          {assessment.corroborating.length > 0 && (
            <div className="ic-corroborating">
              <h5>Corroborating — context, not counted toward the band</h5>
              {assessment.corroborating.map((c) => (
                <Finding key={c.code} reason={c} muted />
              ))}
            </div>
          )}
        </section>

        <aside className="ic-counter" aria-label="counter-evidence">
          <h4>Counter-evidence</h4>
          {assessment.counter_evidence.length > 0 ? (
            assessment.counter_evidence.map((c) => <Finding key={c.code} reason={c} />)
          ) : (
            <p className="ic-counter-empty">
              No exculpatory counter-evidence — {assessment.signal_families.length} signal families
              converge.
            </p>
          )}
        </aside>
      </div>

      {assessment.note && <p className="ic-note">{assessment.note}</p>}

      <div className="ic-actions">
        <p className="ic-recommended">
          Recommended:{' '}
          <strong>{ACTION_LABEL[assessment.recommended_action] ?? humanize(assessment.recommended_action)}</strong>
        </p>
        <div className="ic-action-buttons">
          {OPERATOR_ACTIONS.map((action) => (
            <button
              key={action}
              type="button"
              className={action === 'accept' ? 'op-primary' : undefined}
              onClick={() => setDecision(action)}
            >
              {OP_LABEL[action]}
            </button>
          ))}
        </div>
        {decision && (
          <p className="ic-decision" role="status" data-testid="operator-decision">
            Operator decision: <strong>{OP_LABEL[decision]}</strong> · logged for review (no automatic
            action taken)
          </p>
        )}
      </div>
    </article>
  )
}
