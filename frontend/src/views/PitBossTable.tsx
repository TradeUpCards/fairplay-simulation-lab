import type {
  ClassificationsFile,
  HealthScoresFile,
  IntegrityScoresFile,
  TableRosterFile,
} from '../data/types'
import { loadHealth, loadIntegrity, loadTableRoster, loadClassifications } from '../data/shim'
import { useResource } from '../state/useResource'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { SeatRing } from '../components/SeatRing'
import { IntegrityCase } from '../components/IntegrityCase'
import { TermBars } from '../components/TermBars'
import { assessmentsForTable, buildSeats, classificationIndex } from '../lib/table'
import { BAND_META } from '../lib/health'

interface TableBundle {
  health: HealthScoresFile
  integrity: IntegrityScoresFile
  roster: TableRosterFile
  classifications: ClassificationsFile
}

const loadTableBundle = async (): Promise<TableBundle> => ({
  health: await loadHealth(),
  integrity: await loadIntegrity(),
  roster: await loadTableRoster(),
  classifications: await loadClassifications(),
})

/**
 * Pit-boss table detail (operator-only). The seat-ring shows composition + PTL
 * heat (stubbed pending U2); vitals show health/band/terms; and any integrity
 * group with a member seated here folds in inline — escalated or not — so the
 * "we looked and chose not to escalate" story (the household) is as visible as
 * the true cluster.
 */
export function PitBossTable({ tableId }: { tableId: string }) {
  const bundle = useResource(loadTableBundle, (d) => d.roster.tables.length === 0)
  return (
    <ResourceBoundary state={bundle} label="table">
      {(d) => (
        <PitBossTableView
          tableId={tableId}
          health={d.health}
          integrity={d.integrity}
          roster={d.roster}
          classifications={d.classifications}
        />
      )}
    </ResourceBoundary>
  )
}

export function PitBossTableView({
  tableId,
  health,
  integrity,
  roster,
  classifications,
}: {
  tableId: string
} & TableBundle) {
  const table = roster.tables.find((t) => t.table_id === tableId)
  if (!table) return <p className="rb-empty">Select a table from the list.</p>

  const healthRow = health.health_scores.find((h) => h.table_id === tableId)
  const band = healthRow ? BAND_META[healthRow.band] : null
  const assessments = assessmentsForTable(table, integrity.assessments)
  const seats = buildSeats(table, classificationIndex(classifications.classifications), assessments)

  return (
    <section className="pit-table" aria-label={`table ${tableId}`}>
      <header className="pt-head">
        <h2>
          {table.table_id} <span className="pt-stakes">{table.stakes} · {table.game_type}</span>
        </h2>
        <span className="pt-pace">
          {table.pace_label} · {table.style_volatility_label}
        </span>
      </header>

      {healthRow && band && (
        <div className="pt-vitals">
          <div className="pt-health-headline">
            <span className="pt-health-num">{healthRow.health.toFixed(0)}</span>
            <span className={`band-chip ${band.tone}`}>{band.label}</span>
            {healthRow.integrity_candidate && <span className="review-flag">⚑ Surface to review</span>}
          </div>
          <TermBars terms={healthRow.terms} />
        </div>
      )}

      <div className="pt-ring-wrap">
        <SeatRing table={table} seats={seats} />
        <p className="ptl-legend" data-testid="ptl-legend">
          Seat heat = propensity to leave — <em>pending U2 (PTL not yet computed)</em>
        </p>
      </div>

      {assessments.length > 0 ? (
        <div className="pt-cases">
          {assessments.map((a) => (
            <IntegrityCase key={a.group_id} assessment={a} />
          ))}
        </div>
      ) : (
        <p className="pt-no-flags" data-testid="no-flags">
          No integrity flags — this table reads clean.
        </p>
      )}
    </section>
  )
}
