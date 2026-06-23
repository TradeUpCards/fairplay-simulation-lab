import { useState } from 'react'
import type {
  ClassificationsFile,
  HealthScoresFile,
  IntegrityScoresFile,
  TableRosterFile,
} from '../data/types'
import { loadHealth, loadIntegrity, loadTableRoster, loadClassifications } from '../data/shim'
import { useResource } from '../state/useResource'
import { liveRoom, useLiveRoom, mergeHealthFile, mergeRosterFile } from '../state/liveRoom'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { SeatRing } from '../components/SeatRing'
import { IntegrityCase } from '../components/IntegrityCase'
import { TermBars } from '../components/TermBars'
import { AnimatedNumber } from '../components/AnimatedNumber'
import { LiveFloorControls } from '../components/LiveFloorControls'
import { PlayerSelectModal } from '../components/PlayerSelectModal'
import { assessmentsForTable, buildSeats, classificationIndex } from '../lib/table'
import { ptlForTable } from '../lib/ptl'
import { BAND_META } from '../lib/health'

// PTL legend keys: a coloured pip (::before) then the label
const PTL_KEY = 'inline-flex items-center gap-[0.34rem] before:h-[0.55rem] before:w-[0.55rem] before:rounded-full before:content-[\'\']'

export interface TableBundle {
  health: HealthScoresFile
  integrity: IntegrityScoresFile
  roster: TableRosterFile
  classifications: ClassificationsFile
}

export const loadTableBundle = async (): Promise<TableBundle> => ({
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
  const live = useLiveRoom()
  return (
    <ResourceBoundary state={bundle} label="table">
      {(d) => (
        <PitBossTableView
          tableId={tableId}
          health={mergeHealthFile(d.health, live)}
          integrity={d.integrity}
          roster={mergeRosterFile(d.roster, live)}
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
  const live = useLiveRoom()
  const [seatModalOpen, setSeatModalOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  // Seating mutations go through the live API; the SSE stream brings the rescored
  // table back. Surface a rejection (full table, etc.) inline.
  const run = (p: Promise<void>) => {
    setActionError(null)
    p.catch((e) => setActionError(e instanceof Error ? e.message : String(e)))
  }

  const table = roster.tables.find((t) => t.table_id === tableId)
  if (!table) return <p className="text-muted">Select a table from the list.</p>

  const healthRow = health.health_scores.find((h) => h.table_id === tableId)
  const band = healthRow ? BAND_META[healthRow.band] : null
  const assessments = assessmentsForTable(table, integrity.assessments)
  const clsIndex = classificationIndex(classifications.classifications)
  const ptl = ptlForTable(table, healthRow, clsIndex)
  const seats = buildSeats(table, clsIndex, assessments, ptl)

  // health score + seat count centred on the felt, like the card view (bigger here)
  const center =
    healthRow && band ? (
      <div className="grid justify-items-center gap-1">
        <span className="text-[3.25rem] font-bold leading-none tabular-nums text-[#f4efe6] [text-shadow:0_1px_7px_rgba(0,0,0,0.7)]">
          <AnimatedNumber value={healthRow.health} />
        </span>
        <span className="font-mono text-[0.8rem] tracking-[0.02em] text-[#d7dfd1] [text-shadow:0_1px_5px_rgba(0,0,0,0.75)]">
          {table.seated_count}/{table.max_seats} · {table.open_seats} open
        </span>
      </div>
    ) : undefined

  return (
    <section aria-label={`table ${tableId}`}>
      {/* top row mirrors the floor card: brass id · game · stakes, with the flag +
          band badge riding top-right — just larger to suit the detail panel */}
      <header className="mb-2 flex items-center gap-2">
        <span className="font-mono text-2xl font-bold tracking-[0.04em] text-brass">{table.table_id}</span>
        <span className="text-base text-text">{table.game_type}</span>
        <span className="text-sm text-muted">{table.stakes}</span>
        <span className="ml-auto mr-15 flex items-center gap-2">
          {healthRow?.integrity_candidate && (
            <span className="text-xl text-[#ff8a8a]" title="surface to review" aria-label="surface to review">
              ⚑
            </span>
          )}
          {band && (
            <span className={`rounded-full border px-3 py-1 text-[0.85rem] ${band.tone}`}>{band.label}</span>
          )}
        </span>
      </header>

      <p className="mb-3 text-[0.85rem] text-faint">
        {table.pace_label} · {table.style_volatility_label}
      </p>

      {healthRow && (
        <div className="mb-4 w-1/2">
          <TermBars terms={healthRow.terms} />
        </div>
      )}

      <div className="mb-4 mt-2">
        <SeatRing
          table={table}
          seats={seats}
          centerContent={center}
          onStand={live.connected ? (pid) => run(liveRoom.stand(pid, tableId)) : undefined}
          onSeatOpen={live.connected ? () => setSeatModalOpen(true) : undefined}
        />
        <p
          className="mt-2 flex flex-wrap items-center justify-center gap-x-[0.85rem] gap-y-[0.3rem] text-[0.74rem] text-faint"
          data-testid="ptl-legend"
        >
          Seat heat = <strong className="font-semibold text-muted">propensity to leave</strong>:
          <span className={`${PTL_KEY} before:bg-[#5fcf8a]`}>cool — staying</span>
          <span className={`${PTL_KEY} before:bg-[#e3b25f]`}>warm</span>
          <span className={`${PTL_KEY} before:bg-[#ff7b7b]`}>hot — about to bolt</span>
        </p>
        {actionError && (
          <p className="mt-2 text-center text-[0.74rem] text-[#ff7b7b]" role="alert">
            {actionError}
          </p>
        )}
      </div>

      <LiveFloorControls table={table} />

      <PlayerSelectModal
        open={seatModalOpen}
        tableId={tableId}
        tables={roster.tables}
        classifications={classifications.classifications}
        onSelect={(pid) => {
          run(liveRoom.sit(pid, tableId))
          setSeatModalOpen(false)
        }}
        onClose={() => setSeatModalOpen(false)}
      />

      {assessments.length > 0 ? (
        <div className="grid gap-3">
          {assessments.map((a) => (
            <IntegrityCase key={a.group_id} assessment={a} />
          ))}
        </div>
      ) : (
        <p
          className="my-2 rounded-lg border border-line bg-surface px-[0.85rem] py-[0.7rem] text-[0.85rem] text-[#8be3a7]"
          data-testid="no-flags"
        >
          No integrity flags — this table reads clean.
        </p>
      )}
    </section>
  )
}
