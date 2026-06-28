import type { SweepCell } from '../data/types'
import { colorOf, DEPARTURE_BUCKETS, policyLabel, regimeLabel } from '../lib/dashboard'

const fmt = (v: number | null | undefined): string =>
  v == null ? '—' : v.toFixed(v % 1 === 0 ? 0 : 1)

/**
 * Descriptive per-regime departure breakdown for the selected cell. The three
 * buckets (left satisfied · left tilted/busted · couldn't seat) come straight
 * from the simulator's per-session exit reasons. Counts are flat across routing
 * arms by construction — FairPlay-liveness wins on session *duration*, not on
 * who leaves — so this panel characterises the room, it does NOT rank the
 * policy. Renders nothing until a cell carrying departure data is selected.
 */
export function DeparturesPanel({
  cell,
  policies,
}: {
  cell: SweepCell | null
  /** Which policies (and order) to show; only those carrying data appear. */
  policies: string[]
}) {
  const departures = cell?.departures
  const shown = departures ? policies.filter((p) => departures[p]) : []
  if (!cell || shown.length === 0) return null

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="m-0 text-[0.95rem] text-text">
          Where players left ·{' '}
          <span className="text-brass">{regimeLabel(cell.tables, cell.rate)}</span>
        </h3>
        <span className="text-[0.72rem] text-muted">
          Descriptive room context — counts are similar across policies (FairPlay’s edge is session
          length, not who leaves)
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full border-collapse text-[0.8rem]">
          <thead>
            <tr className="bg-surface-2 text-left text-muted">
              <th className="px-3 py-2 font-medium">Policy</th>
              {DEPARTURE_BUCKETS.map((b) => (
                <th key={b.key} className="px-3 py-2 text-right font-medium" title={b.hint}>
                  {b.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((policy) => {
              const d = departures![policy]
              return (
                <tr key={policy} className="border-t border-line/70">
                  <td className="whitespace-nowrap px-3 py-1.5">
                    <span className="inline-flex items-center gap-[0.4rem] text-text">
                      <span
                        className="inline-block h-[0.6rem] w-[0.6rem] rounded-xs"
                        style={{ backgroundColor: colorOf(policy) }}
                        aria-hidden="true"
                      />
                      {policyLabel(policy)}
                    </span>
                  </td>
                  {DEPARTURE_BUCKETS.map((b) => (
                    <td key={b.key} className="px-3 py-1.5 text-right tabular-nums text-text">
                      {fmt(d[b.key])}
                      <span className="ml-1 text-[0.7rem] text-faint">
                        ({fmt(d[b.cohortKey])} cohort)
                      </span>
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[0.7rem] leading-relaxed text-faint">
        Terminal site-departures only (mid-session table moves are excluded); “cohort” is the
        vulnerable-player subset of each bucket. Seed-averaged counts.
      </p>
    </div>
  )
}
