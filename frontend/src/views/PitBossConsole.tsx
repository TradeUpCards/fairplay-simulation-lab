import { useState } from 'react'
import type { HealthScore } from '../data/types'
import { useResource } from '../state/useResource'
import { useLiveRoom, mergeHealthFile, mergeRosterFile } from '../state/liveRoom'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { TableCard } from '../components/TableCard'
import { TableDrawer } from '../components/TableDrawer'
import { loadTableBundle, PitBossTableView } from './PitBossTable'

/**
 * The pit-boss floor: a grid of table cards on the carpet. Cards are ordered for
 * triage — integrity-flagged tables first, then unhealthiest — so the problems
 * sit top-left. Clicking a card opens the detail drawer (seat-ring, vitals,
 * integrity case, stand/sit) over the right 2/3 while the grid collapses to a
 * left rail with the active card highlighted. Health + rosters are live-merged,
 * so a stand/sit in the drawer updates the cards behind it in real time.
 */
export function PitBossConsole() {
  const bundle = useResource(loadTableBundle, (d) => d.roster.tables.length === 0)
  const live = useLiveRoom()
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <ResourceBoundary state={bundle} label="floor">
      {(d) => {
        const health = mergeHealthFile(d.health, live)
        const roster = mergeRosterFile(d.roster, live)
        const healthById = new Map<string, HealthScore>(
          health.health_scores.map((h) => [h.table_id, h]),
        )
        const tables = [...roster.tables].sort((a, b) => {
          const ha = healthById.get(a.table_id)
          const hb = healthById.get(b.table_id)
          const flagDelta = Number(hb?.integrity_candidate ?? false) - Number(ha?.integrity_candidate ?? false)
          if (flagDelta !== 0) return flagDelta
          return (ha?.health ?? Infinity) - (hb?.health ?? Infinity)
        })

        return (
          <section className="relative" aria-label="pit boss floor">
            <header className="mb-5">
              <h2 className="m-0 text-[1.35rem] tracking-[0.01em]">The floor</h2>
              <p className="mt-1 text-[0.78rem] text-muted">
                {roster.tables.length} tables · needs-attention first · click a table to inspect &amp; control
              </p>
            </header>

            {/* grid collapses to a left rail when the drawer takes the right 2/3 */}
            <ul
              className={`grid gap-[1.1rem] transition-[max-width] duration-360 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                selected ? 'max-w-[30%] grid-cols-1' : 'grid-cols-3 max-[900px]:grid-cols-2'
              }`}
            >
              {tables.map((t) => (
                <TableCard
                  key={t.table_id}
                  table={t}
                  health={healthById.get(t.table_id)}
                  classifications={d.classifications}
                  integrity={d.integrity}
                  active={selected === t.table_id}
                  onOpen={() => setSelected(t.table_id)}
                />
              ))}
            </ul>

            <TableDrawer open={selected !== null} onClose={() => setSelected(null)}>
              {selected && (
                <PitBossTableView
                  tableId={selected}
                  health={health}
                  integrity={d.integrity}
                  roster={roster}
                  classifications={d.classifications}
                />
              )}
            </TableDrawer>
          </section>
        )
      }}
    </ResourceBoundary>
  )
}
