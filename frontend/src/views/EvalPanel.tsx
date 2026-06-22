import type {
  HealthScoresFile,
  IntegrityScoresFile,
  SeededCase,
  SeededCaseLabelsFile,
} from '../data/types'
import { loadSeededCases, loadHealth, loadIntegrity } from '../data/shim'
import { useResource } from '../state/useResource'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { resolvePredicted, satisfiesExpected, splitByRisk, humanize } from '../lib/evals'

interface EvalBundle {
  labels: SeededCaseLabelsFile
  health: HealthScoresFile
  integrity: IntegrityScoresFile
}

const loadEvalBundle = async (): Promise<EvalBundle> => ({
  labels: await loadSeededCases(),
  health: await loadHealth(),
  integrity: await loadIntegrity(),
})

/**
 * Eval / proof panel (operator-only — binds the answer key, never a player
 * screen). Shows expected-vs-computed for the three mandatory demo cases
 * (A/C/E), expected-only for the rest, and ranks true-risk cases above
 * false-positive traps with a visible separator — the eval invariant made
 * visible (R16/R15).
 */
export function EvalPanel() {
  const bundle = useResource(loadEvalBundle, (d) => d.labels.cases.length === 0)
  return (
    <ResourceBoundary state={bundle} label="eval cases">
      {(data) => <EvalPanelView bundle={data} />}
    </ResourceBoundary>
  )
}

export function EvalPanelView({ bundle }: { bundle: EvalBundle }) {
  const { labels, health, integrity } = bundle
  const { trueRisk, traps } = splitByRisk(labels.cases, labels.eval_summary)
  const mandatory = new Set(labels.eval_summary.mandatory_demo_cases)

  const renderCase = (c: SeededCase) => (
    <CaseCard
      key={c.case_id}
      seeded={c}
      health={health}
      integrity={integrity}
      hasPacket={mandatory.has(c.case_id)}
    />
  )

  return (
    <section className="eval-panel" aria-label="eval panel">
      <header className="eval-header">
        <h2>Eval / proof</h2>
        <p className="eval-invariant">{labels.eval_summary.eval_invariant}</p>
      </header>

      <h3 className="eval-group-title true-risk">True risk — should rank highest</h3>
      <ol className="eval-list">{trueRisk.map(renderCase)}</ol>

      <hr className="risk-separator" data-testid="risk-separator" />
      <p className="separator-label">— false-positive traps must rank below —</p>

      <h3 className="eval-group-title traps">False-positive traps — must not over-escalate</h3>
      <ol className="eval-list">{traps.map(renderCase)}</ol>
    </section>
  )
}

function CaseCard({
  seeded,
  health,
  integrity,
  hasPacket,
}: {
  seeded: SeededCase
  health: HealthScoresFile
  integrity: IntegrityScoresFile
  hasPacket: boolean
}) {
  const predicted = hasPacket ? resolvePredicted(seeded, health, integrity) : null
  const agrees = predicted ? satisfiesExpected(seeded.expected_category, predicted.band) : false

  return (
    <li className="eval-case" data-testid="eval-case">
      <div className="eval-case-head">
        <span className="case-id">{seeded.case_id}</span>
        <span className="case-label">{humanize(seeded.prd_label)}</span>
        {seeded.is_false_positive_trap && <span className="trap-chip">trap</span>}
      </div>

      <dl className="eval-expected">
        <div>
          <dt>Expected</dt>
          <dd>{humanize(seeded.expected_category)}</dd>
        </div>
        <div>
          <dt>Lens</dt>
          <dd>{humanize(seeded.expected_risk_lens)}</dd>
        </div>
        <div>
          <dt>Action</dt>
          <dd>{humanize(seeded.expected_seating_action)}</dd>
        </div>
      </dl>

      {predicted ? (
        <div className="eval-predicted">
          <p className="predicted-line">
            <span className="predicted-label">Computed:</span>{' '}
            <span className={`predicted-band ${agrees ? 'agree' : 'disagree'}`} data-testid="predicted-band">
              {predicted.band ?? 'n/a'}
            </span>{' '}
            <span className="predicted-detail">({predicted.detail})</span>{' '}
            <span className="verdict" data-testid="verdict">
              {agrees ? '✓ matches expected' : '✗ mismatch'}
            </span>
          </p>
          <ul className="eval-checks" aria-label="safety checks">
            {seeded.eval_checks.map((check) => (
              <li key={check} data-testid="eval-check">
                {humanize(check)}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="eval-pending">Expected-only — no eval packet yet (B/D/F/G pending P4).</p>
      )}
    </li>
  )
}
