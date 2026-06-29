import type { HealthScore, HealthScoresFile } from '../data/types'
import { loadHealth } from '../data/shim'
import { useResource } from '../state/useResource'
import { useLiveRoom, mergeHealthScores } from '../state/liveRoom'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { BAND_CHIP, BAND_META, BAND_TEXT, rankTables, TERM_CAP, type TermKey } from '../lib/health'

// "surface to review" pill — shared with the table-detail header
export const REVIEW_FLAG =
  'ml-auto rounded-full border border-[#b3455a] bg-[#3a1a1f] px-[0.55rem] py-[0.15rem] text-[0.72rem] font-semibold text-[#ff9b9b]'

const TERMS: { key: TermKey; label: string }[] = [
  { key: 'P_pred', label: 'pred' },
  { key: 'P_frag', label: 'frag' },
  { key: 'P_clus', label: 'clus' },
  { key: 'P_bleed', label: 'bleed' },
]

/**
 * Pit-boss index — the operator's table list, ranked healthiest-first off
 * `health_scores.json` (R6). This is an operator-only view, so health numbers,
 * bands, penalty terms, and the integrity flag are all allowed here (never in
 * the lobby). `integrity_candidate` raises a "surface to review" flag regardless
 * of the health number (T-11), and `reason_codes[].detail` is rendered verbatim.
 *
 * Scope note: live re-rank as the clock/lever change (R7/AE4) needs P3's
 * per-hour health series — still an open question — so this ranks the current
 * snapshot. `rankTables` re-sorts whatever it's handed, so a per-hour series
 * drops in without changing this view.
 */
export function PitBossIndex({
  onSelectTable,
  selectedTableId,
}: {
  onSelectTable?: (tableId: string) => void
  selectedTableId?: string
}) {
  const health = useResource(loadHealth, (d) => d.health_scores.length === 0)
  const live = useLiveRoom()
  return (
    <ResourceBoundary state={health} label="table health">
      {(data: HealthScoresFile) => (
        <PitBossIndexView
          scores={mergeHealthScores(data.health_scores, live)}
          onSelectTable={onSelectTable}
          selectedTableId={selectedTableId}
        />
      )}
    </ResourceBoundary>
  )
}

/** Pure render from already-loaded scores — what the unit tests drive. */
export function PitBossIndexView({
  scores,
  onSelectTable,
  selectedTableId,
}: {
  scores: HealthScore[]
  onSelectTable?: (tableId: string) => void
  selectedTableId?: string
}) {
  const ranked = rankTables(scores)
  return (
    <section className="mt-8 border-t border-line pt-6" aria-label="pit boss table index">
      <header>
        <h2 className="m-0 text-[1.15rem]">Tables — healthiest first</h2>
        <p className="mb-4 mt-[0.2rem] text-[0.78rem] text-faint">
          Ranked on the current health snapshot · per-hour re-rank pending P3 series
        </p>
      </header>
      <ol className="grid list-none gap-2 p-0">
        {ranked.map((table, i) => (
          <PitRow
            key={table.table_id}
            rank={i + 1}
            table={table}
            onSelect={onSelectTable}
            selected={table.table_id === selectedTableId}
          />
        ))}
      </ol>
    </section>
  )
}

function PitRow({
  rank,
  table,
  onSelect,
  selected = false,
}: {
  rank: number
  table: HealthScore
  onSelect?: (tableId: string) => void
  selected?: boolean
}) {
  const band = BAND_META[table.band]
  const why = table.reason_codes[0]?.detail
  return (
    <li
      data-testid="pit-row"
      className={`overflow-hidden rounded-[9px] border border-line bg-surface${
        selected ? ' [outline:2px_solid_#5f7fd9]' : ''
      }`}
    >
      <button
        type="button"
        className="flex w-full items-center gap-3 rounded-none border-none bg-transparent px-[0.8rem] py-[0.6rem] text-left hover:bg-[#1b2230]"
        aria-label={`open table ${table.table_id}`}
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect?.(table.table_id)}
      >
        <span className="min-w-[1.8rem] text-[0.8rem] tabular-nums text-faint">#{rank}</span>
        <span data-testid="pit-table-id" className="min-w-10 font-semibold">{table.table_id}</span>
        <span className={`min-w-10 text-[1.5rem] font-bold tabular-nums ${BAND_TEXT[table.band]}`}>
          {table.health.toFixed(0)}
        </span>
        <span className={`${BAND_CHIP} ${band.tone}`}>{band.label}</span>
        {table.integrity_candidate && (
          <span className={REVIEW_FLAG} data-testid="review-flag">
            ⚑ Surface to review
          </span>
        )}
      </button>

      <div className="flex flex-wrap gap-3 px-[0.8rem] pb-2 text-[0.72rem] text-muted" aria-label="penalty terms">
        {TERMS.map(({ key, label }) => (
          <span className="flex items-center gap-[0.3rem]" key={key}>
            <span>{label}</span>
            <span className="inline-block h-1.25 w-11 overflow-hidden rounded-[3px] bg-line">
              <span className="block h-full bg-[#5f7fd9]" style={{ width: `${(table.terms[key] / TERM_CAP[key]) * 100}%` }} />
            </span>
            <span className="tabular-nums text-[#c3c9d6]">{table.terms[key]}</span>
          </span>
        ))}
      </div>

      {why && <p className="m-0 px-[0.8rem] pb-[0.7rem] text-[0.8rem] text-[#9aa2b3]">{why}</p>}
    </li>
  )
}
