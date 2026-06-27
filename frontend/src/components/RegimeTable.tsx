import type { SweepCell, SweepDataset } from '../data/types'
import { cellKey, colorOf, policyLabel, toCsv } from '../lib/dashboard'

const DISPLAY_KEYS = [
  'total_paid_seat_hours',
  'vulnerable_paid_seat_hours',
  'break_count',
  'wait_balk_count',
  'forming_seat_count',
  'formation_activation_count',
  'final_active_tables',
]

const fmt = (v: number | null, unit: string): string =>
  v == null ? '—' : unit === 'hrs' ? v.toFixed(1) : v.toFixed(v % 1 === 0 ? 0 : 1)

function downloadCsv(dataset: SweepDataset): void {
  const blob = new Blob([toCsv(dataset)], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `room-sweep-${dataset.id}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

/** Seed-averaged means per regime × policy. Rows are grouped by cell; the
 * selected cell is highlighted and clicking any row selects its regime. */
export function RegimeTable({
  dataset,
  selectedKey,
  onSelect,
}: {
  dataset: SweepDataset
  selectedKey: string | null
  onSelect: (cell: SweepCell) => void
}) {
  const metrics = dataset.metrics.filter((m) => DISPLAY_KEYS.includes(m.key))
  const ordered = [...metrics].sort(
    (a, b) => DISPLAY_KEYS.indexOf(a.key) - DISPLAY_KEYS.indexOf(b.key),
  )

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="m-0 text-[0.95rem] text-text">Per-regime metrics</h3>
        <button
          type="button"
          onClick={() => downloadCsv(dataset)}
          className="rounded-md border border-line bg-surface px-2.5 py-1 text-[0.74rem] text-muted hover:border-brass hover:text-text"
        >
          ↓ Download CSV
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full border-collapse text-[0.8rem]">
          <thead>
            <tr className="bg-surface-2 text-left text-muted">
              <th className="px-3 py-2 font-medium">Regime</th>
              <th className="px-3 py-2 font-medium">Policy</th>
              {ordered.map((m) => (
                <th key={m.key} className="px-3 py-2 text-right font-medium" title={m.label}>
                  {m.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataset.cells.map((cell) => {
              const selected = cellKey(cell) === selectedKey
              return dataset.policies.map((policy, pi) => (
                <tr
                  key={`${cellKey(cell)}-${policy}`}
                  onClick={() => onSelect(cell)}
                  className={`cursor-pointer border-t border-line/70 hover:bg-surface-2 ${
                    selected ? 'bg-[rgba(199,154,75,0.08)]' : ''
                  }`}
                >
                  <td className="whitespace-nowrap px-3 py-1.5 text-muted">
                    {pi === 0 ? `${cell.tables}t · ${cell.rate}/hr` : ''}
                  </td>
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
                  {ordered.map((m) => (
                    <td key={m.key} className="px-3 py-1.5 text-right tabular-nums text-text">
                      {fmt(cell.means[policy]?.[m.key] ?? null, m.unit)}
                    </td>
                  ))}
                </tr>
              ))
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
