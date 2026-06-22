import type { HealthScore, HealthScoresFile } from '../data/types'
import { loadHealth } from '../data/shim'
import { useResource } from '../state/useResource'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { BAND_META, rankTables, TERM_CAP, type TermKey } from '../lib/health'

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
export function PitBossIndex({ onSelectTable }: { onSelectTable?: (tableId: string) => void }) {
  const health = useResource(loadHealth, (d) => d.health_scores.length === 0)
  return (
    <ResourceBoundary state={health} label="table health">
      {(data: HealthScoresFile) => <PitBossIndexView scores={data.health_scores} onSelectTable={onSelectTable} />}
    </ResourceBoundary>
  )
}

/** Pure render from already-loaded scores — what the unit tests drive. */
export function PitBossIndexView({
  scores,
  onSelectTable,
}: {
  scores: HealthScore[]
  onSelectTable?: (tableId: string) => void
}) {
  const ranked = rankTables(scores)
  return (
    <section className="pit-index" aria-label="pit boss table index">
      <header className="pit-index-header">
        <h2>Tables — healthiest first</h2>
        <p className="pit-index-note">Ranked on the current health snapshot · per-hour re-rank pending P3 series</p>
      </header>
      <ol className="pit-list">
        {ranked.map((table, i) => (
          <PitRow key={table.table_id} rank={i + 1} table={table} onSelect={onSelectTable} />
        ))}
      </ol>
    </section>
  )
}

function PitRow({
  rank,
  table,
  onSelect,
}: {
  rank: number
  table: HealthScore
  onSelect?: (tableId: string) => void
}) {
  const band = BAND_META[table.band]
  const why = table.reason_codes[0]?.detail
  return (
    <li className="pit-row">
      <button
        type="button"
        className="pit-row-main"
        aria-label={`open table ${table.table_id}`}
        onClick={() => onSelect?.(table.table_id)}
      >
        <span className="pit-rank">#{rank}</span>
        <span className="pit-table-id">{table.table_id}</span>
        <span className="pit-health">{table.health.toFixed(0)}</span>
        <span className={`band-chip ${band.tone}`}>{band.label}</span>
        {table.integrity_candidate && (
          <span className="review-flag" data-testid="review-flag">
            ⚑ Surface to review
          </span>
        )}
      </button>

      <div className="pit-terms" aria-label="penalty terms">
        {TERMS.map(({ key, label }) => (
          <span className="term" key={key}>
            <span className="term-label">{label}</span>
            <span className="term-bar">
              <span className="term-fill" style={{ width: `${(table.terms[key] / TERM_CAP[key]) * 100}%` }} />
            </span>
            <span className="term-val">{table.terms[key]}</span>
          </span>
        ))}
      </div>

      {why && <p className="pit-why">{why}</p>}
    </li>
  )
}
