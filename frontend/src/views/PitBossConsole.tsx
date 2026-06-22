import { useState } from 'react'
import { PitBossIndex } from './PitBossIndex'
import { PitBossTable } from './PitBossTable'

/**
 * The operator console: the ranked table index on the left, the selected
 * table's detail on the right. Clicking a row in the index drives the detail
 * (the lobby→pit-boss→detail click path). Defaults to T-11 so the demo opens on
 * the flagged cluster.
 */
export function PitBossConsole() {
  const [selected, setSelected] = useState('T-11')
  return (
    <section className="pit-console" aria-label="pit boss console">
      <h2 className="pit-console-title">Pit-boss console</h2>
      <div className="pit-console-grid">
        <div className="pit-console-list">
          <PitBossIndex onSelectTable={setSelected} selectedTableId={selected} />
        </div>
        <div className="pit-console-detail">
          <PitBossTable tableId={selected} />
        </div>
      </div>
    </section>
  )
}
