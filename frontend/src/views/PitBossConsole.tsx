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
          <section className={`pit-floor${selected ? ' has-selection' : ''}`} aria-label="pit boss floor">
            <header className="floor-head">
              <h2>The floor</h2>
              <p className="floor-sub">
                {roster.tables.length} tables · needs-attention first · click a table to inspect &amp; control
              </p>
            </header>

            <ul className="table-grid">
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
