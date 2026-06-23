import type {
  ClassificationsFile,
  HealthScore,
  IntegrityScoresFile,
  TableRosterEntry,
} from '../data/types'
import { assessmentsForTable, buildSeats, classificationIndex } from '../lib/table'
import { ptlForTable } from '../lib/ptl'
import { BAND_META } from '../lib/health'
import { AnimatedNumber } from './AnimatedNumber'
import { SeatRing } from './SeatRing'

/**
 * A pit table rendered as a physical "table tag" card on the carpet — deliberately
 * chromed (deep-felt panel, brass edge, drop shadow), unlike the player lobby's
 * chrome-free table images. The body is the actual table with its players seated
 * around the rim; the health score + seat count sit in the middle of the felt
 * (hover the score for the breakdown), the band badge rides the top-right, and
 * table + game live top-left. Clicking opens the detail drawer.
 */
export function TableCard({
  table,
  health,
  classifications,
  integrity,
  active,
  onOpen,
}: {
  table: TableRosterEntry
  health?: HealthScore
  classifications: ClassificationsFile
  integrity: IntegrityScoresFile
  active: boolean
  onOpen: () => void
}) {
  const band = health ? BAND_META[health.band] : null
  const clsIndex = classificationIndex(classifications.classifications)
  const assessments = assessmentsForTable(table, integrity.assessments)
  const ptl = ptlForTable(table, health, clsIndex)
  const seats = buildSeats(table, clsIndex, assessments, ptl)
  const flagged = Boolean(health?.integrity_candidate)

  const center =
    health && band ? (
      <div className="tc-center">
        <span className="tc-health">
          <AnimatedNumber value={health.health} />
          <span className="tc-tip" role="tooltip">
            <strong>{band.label}</strong>
            <span>Health {health.health.toFixed(0)} = 100 − penalties</span>
            <span className="tc-tip-terms">
              pred {health.terms.P_pred.toFixed(0)} · frag {health.terms.P_frag.toFixed(0)} · clus{' '}
              {health.terms.P_clus.toFixed(0)} · bleed {health.terms.P_bleed.toFixed(0)}
            </span>
          </span>
        </span>
        <span className="tc-occ">
          {table.seated_count}/{table.max_seats} · {table.open_seats} open
        </span>
      </div>
    ) : (
      <div className="tc-center">
        <span className="tc-health tc-health-na">—</span>
      </div>
    )

  return (
    <li className={`table-card${active ? ' is-active' : ''}${flagged ? ' is-flagged' : ''}`}>
      <button
        type="button"
        className="tc-btn"
        aria-label={`inspect table ${table.table_id}`}
        aria-pressed={active}
        onClick={onOpen}
      >
        <header className="tc-head">
          <span className="tc-id">{table.table_id}</span>
          <span className="tc-game">{table.game_type}</span>
          <span className="tc-stakes">{table.stakes}</span>
          <span className="tc-head-right">
            {flagged && (
              <span className="tc-flag" title="surface to review" aria-label="surface to review">
                ⚑
              </span>
            )}
            {band && <span className={`band-chip ${band.tone}`}>{band.label}</span>}
          </span>
        </header>

        <div className="tc-table">
          <SeatRing table={table} seats={seats} compact centerContent={center} />
        </div>
      </button>
    </li>
  )
}
