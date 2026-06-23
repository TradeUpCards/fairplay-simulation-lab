import type {
  ClassificationsFile,
  HealthScore,
  IntegrityScoresFile,
  TableRosterEntry,
} from '../data/types'
import { assessmentsForTable, buildSeats, classificationIndex } from '../lib/table'
import { ptlForTable } from '../lib/ptl'
import { BAND_CHIP, BAND_META } from '../lib/health'
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

  // health score (or em-dash) centred on the felt; hover the number for the
  // penalty-term breakdown in a tooltip.
  const healthBase =
    'text-[1.95rem] font-bold leading-none tabular-nums [text-shadow:0_1px_7px_rgba(0,0,0,0.7)]'
  const center =
    health && band ? (
      <div className="grid justify-items-center gap-[0.12rem]">
        <span className={`group relative cursor-help text-[#f4efe6] ${healthBase}`}>
          <AnimatedNumber value={health.health} />
          <span
            className="pointer-events-none invisible absolute bottom-[calc(100%+0.55rem)] left-1/2 z-6 grid w-max max-w-[270px] -translate-x-1/2 translate-y-1 gap-[0.22rem] rounded-lg border border-line bg-[rgba(8,10,14,0.97)] px-[0.7rem] py-2 text-center text-[0.68rem] font-normal leading-[1.35] text-text opacity-0 shadow-[0_10px_24px_rgba(0,0,0,0.5)] transition-[opacity,transform] duration-140 text-shadow-none group-hover:visible group-hover:translate-y-0 group-hover:opacity-100"
            role="tooltip"
          >
            <strong className="text-brass">{band.label}</strong>
            <span>Health {health.health.toFixed(0)} = 100 − penalties</span>
            <span className="font-mono text-muted">
              pred {health.terms.P_pred.toFixed(0)} · frag {health.terms.P_frag.toFixed(0)} · clus{' '}
              {health.terms.P_clus.toFixed(0)} · bleed {health.terms.P_bleed.toFixed(0)}
            </span>
          </span>
        </span>
        <span className="font-mono text-[0.64rem] tracking-[0.02em] text-[#d7dfd1] [text-shadow:0_1px_5px_rgba(0,0,0,0.75)]">
          {table.seated_count}/{table.max_seats} · {table.open_seats} open
        </span>
      </div>
    ) : (
      <div className="grid justify-items-center gap-[0.12rem]">
        <span className={`text-[#d6cfc2] ${healthBase}`}>—</span>
      </div>
    )

  // card chrome: deep-felt panel, brass top-edge, drop shadow. Brass edge turns
  // red when flagged; the whole edge + a brass ring when active (drawer open).
  const btnState = active
    ? 'border-brass shadow-[0_0_0_2px_var(--color-brass),0_18px_34px_rgba(0,0,0,0.55)] hover:-translate-y-[3px]'
    : flagged
      ? 'border-line border-t-[#b3455a] hover:-translate-y-[3px] hover:shadow-[0_16px_32px_rgba(0,0,0,0.5)]'
      : 'border-line border-t-brass-soft hover:-translate-y-[3px] hover:border-t-brass hover:shadow-[0_16px_32px_rgba(0,0,0,0.5)]'

  return (
    <li className="flex list-none">
      <button
        type="button"
        className={`flex w-full flex-1 cursor-pointer flex-col rounded-xl border border-t-2 bg-[linear-gradient(180deg,rgba(13,58,39,0.96),rgba(6,31,21,0.975))] px-4 pb-4 pt-[0.85rem] text-left text-text shadow-[0_10px_24px_rgba(0,0,0,0.38)] transition-[transform,box-shadow,border-color] duration-180 motion-reduce:transition-none ${btnState}`}
        aria-label={`inspect table ${table.table_id}`}
        aria-pressed={active}
        onClick={onOpen}
      >
        <header className="mb-[0.4rem] flex items-center gap-[0.45rem]">
          <span className="font-mono text-[1.05rem] font-bold tracking-[0.04em] text-brass">
            {table.table_id}
          </span>
          <span className="text-[0.8rem] text-text">{table.game_type}</span>
          <span className="text-[0.72rem] text-muted">{table.stakes}</span>
          <span className="ml-auto flex items-center gap-[0.4rem]">
            {flagged && (
              <span className="text-[0.9rem] text-[#ff8a8a]" title="surface to review" aria-label="surface to review">
                ⚑
              </span>
            )}
            {band && <span className={`${BAND_CHIP} ${band.tone}`}>{band.label}</span>}
          </span>
        </header>

        <div className="mt-[0.1rem] flex flex-1 items-center justify-center">
          <SeatRing table={table} seats={seats} compact centerContent={center} />
        </div>
      </button>
    </li>
  )
}
