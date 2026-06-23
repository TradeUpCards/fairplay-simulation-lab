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
    <section aria-label="eval panel">
      <header>
        <h2 className="m-0 text-[1.15rem]">Eval / proof</h2>
        <p className="mb-4 mt-1 text-[0.8rem] text-muted">{labels.eval_summary.eval_invariant}</p>
      </header>

      <h3 className="mb-2 mt-3 text-[0.85rem] uppercase tracking-[0.04em] text-[#8be3a7]">
        True risk — should rank highest
      </h3>
      <ol className="grid list-none gap-2 p-0">{trueRisk.map(renderCase)}</ol>

      <hr className="mb-1 mt-4 border-0 border-t-2 border-dashed border-[#3a4757]" data-testid="risk-separator" />
      <p className="m-0 mb-2 text-center text-[0.72rem] text-faint">— false-positive traps must rank below —</p>

      <h3 className="mb-2 mt-3 text-[0.85rem] uppercase tracking-[0.04em] text-[#efc28f]">
        False-positive traps — must not over-escalate
      </h3>
      <ol className="grid list-none gap-2 p-0">{traps.map(renderCase)}</ol>
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
    <li className="rounded-[9px] border border-line bg-surface px-[0.85rem] py-[0.7rem]" data-testid="eval-case">
      <div className="flex items-center gap-2">
        <span className="font-semibold">{seeded.case_id}</span>
        <span className="text-[0.85rem] text-[#9aa2b3]">{humanize(seeded.prd_label)}</span>
        {seeded.is_false_positive_trap && (
          <span className="ml-auto rounded-full border border-[#8a7a2f] bg-[#33301a] px-[0.45rem] py-[0.1rem] text-[0.68rem] uppercase tracking-[0.04em] text-[#e3d28b]">
            trap
          </span>
        )}
      </div>

      <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-[0.82rem]">
        <div className="flex gap-[0.35rem]">
          <dt className="text-muted">Expected</dt>
          <dd className="m-0">{humanize(seeded.expected_category)}</dd>
        </div>
        <div className="flex gap-[0.35rem]">
          <dt className="text-muted">Lens</dt>
          <dd className="m-0">{humanize(seeded.expected_risk_lens)}</dd>
        </div>
        <div className="flex gap-[0.35rem]">
          <dt className="text-muted">Action</dt>
          <dd className="m-0">{humanize(seeded.expected_seating_action)}</dd>
        </div>
      </dl>

      {predicted ? (
        <div className="mt-[0.6rem] border-t border-dashed border-line pt-2">
          <p className="m-0 mb-[0.4rem] text-[0.82rem]">
            <span className="text-muted">Computed:</span>{' '}
            <span
              className={`rounded-[5px] px-[0.4rem] py-[0.05rem] font-semibold ${
                agrees ? 'bg-[#16341f] text-[#8be3a7]' : 'bg-[#3a1a1f] text-[#ff9b9b]'
              }`}
              data-testid="predicted-band"
            >
              {predicted.band ?? 'n/a'}
            </span>{' '}
            <span className="text-[0.78rem] text-faint">({predicted.detail})</span>{' '}
            <span className="text-[0.78rem] text-muted" data-testid="verdict">
              {agrees ? '✓ matches expected' : '✗ mismatch'}
            </span>
          </p>
          <ul className="m-0 mt-[0.3rem] grid gap-[0.15rem] pl-[1.1rem] text-[0.78rem] text-[#9aa2b3]" aria-label="safety checks">
            {seeded.eval_checks.map((check) => (
              <li key={check} data-testid="eval-check">
                {humanize(check)}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-2 text-[0.78rem] italic text-faint">
          Expected-only — no eval packet yet (B/D/F/G pending P4).
        </p>
      )}
    </li>
  )
}
