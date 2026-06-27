import type { ReactNode } from 'react'
import type { SweepCell, SweepDataset } from '../data/types'
import {
  advantage,
  cellKey,
  heatColor,
  maxAbsAdvantage,
  policyLabel,
  BASELINE_POLICY,
} from '../lib/dashboard'

const signed = (v: number | null): string =>
  v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`

/**
 * Regime heatmap: table inventory (rows) × arrival rate (cols), each cell
 * coloured by FairPlay − Standard on the chosen metric (green = FairPlay ahead).
 * Per-seed win dots expose stability; clicking a cell drives the animated hero.
 */
export function RegimeHeatmap({
  dataset,
  metricKey,
  metricLabel,
  candidate,
  selectedKey,
  onSelect,
}: {
  dataset: SweepDataset
  metricKey: string
  metricLabel: string
  candidate: string
  selectedKey: string | null
  onSelect: (cell: SweepCell) => void
}) {
  const rows = dataset.table_axis
  const cols = dataset.rate_axis
  const candLabel = policyLabel(candidate)
  const maxAbs = maxAbsAdvantage(dataset, metricKey, candidate)
  const cellAt = (tables: number, rate: number) =>
    dataset.cells.find((c) => c.tables === tables && c.rate === rate)

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="m-0 text-[0.95rem] text-text">Regime heatmap</h3>
        <span className="text-[0.78rem] text-muted">
          {candLabel} − Standard · <span className="text-text">{metricLabel}</span> · click a cell
        </span>
      </div>

      <div
        className="grid gap-1.5"
        style={{ gridTemplateColumns: `auto repeat(${cols.length}, minmax(96px, 1fr))` }}
      >
        {/* header row: corner + rate labels */}
        <div className="px-2 py-1 font-mono text-[0.62rem] uppercase tracking-[0.12em] text-faint self-end">
          tables ↓ · joins/hr →
        </div>
        {cols.map((rate) => (
          <div
            key={`h-${rate}`}
            className="px-2 py-1 text-center font-mono text-[0.72rem] text-muted"
          >
            {rate}/hr
          </div>
        ))}

        {rows.map((tables) => (
          <ReactRowFragment key={`row-${tables}`}>
            <div className="flex items-center px-2 font-mono text-[0.72rem] text-muted">
              {tables}
            </div>
            {cols.map((rate) => {
              const cell = cellAt(tables, rate)
              if (!cell) {
                return (
                  <div
                    key={`c-${tables}-${rate}`}
                    className="rounded-md border border-dashed border-line/60 py-4 text-center text-[0.7rem] text-faint"
                  >
                    —
                  </div>
                )
              }
              const delta = advantage(cell, metricKey, candidate)
              const selected = cellKey(cell) === selectedKey
              const stab = cell.stability[candidate]?.[metricKey]
              return (
                <button
                  key={`c-${tables}-${rate}`}
                  type="button"
                  onClick={() => onSelect(cell)}
                  aria-pressed={selected}
                  className={`flex flex-col items-center justify-center gap-1 rounded-md border px-2 py-3 transition-[border-color] ${
                    selected
                      ? 'border-brass ring-1 ring-brass'
                      : 'border-line hover:border-[#3a4757]'
                  }`}
                  style={{ backgroundColor: heatColor(delta, maxAbs) }}
                  title={`${tables} tables · ${rate}/hr · ${candLabel}−Standard ${signed(delta)} ${metricLabel}`}
                >
                  <span className="text-[1.05rem] font-semibold tabular-nums text-text">
                    {signed(delta)}
                  </span>
                  {stab && (
                    <span className="flex items-center gap-1" aria-label={`${stab.wins} of ${stab.n} seeds favour FairPlay`}>
                      {Object.entries(stab.deltas).map(([seed, d]) => (
                        <span
                          key={seed}
                          className="inline-block h-[5px] w-[5px] rounded-full"
                          style={{ backgroundColor: d > 0 ? '#7bd88f' : '#c95d5d' }}
                        />
                      ))}
                    </span>
                  )}
                </button>
              )
            })}
          </ReactRowFragment>
        ))}
      </div>

      <p className="mt-2 text-[0.72rem] text-muted">
        Cell value is {candLabel} minus the <span className="text-text">{BASELINE_POLICY}</span> baseline
        (seed-averaged). Dots are per-seed wins (green) / losses (red). Colour scales with magnitude.
      </p>
    </div>
  )
}

/** Grid children must be flat (the row label + its cells sit in one grid), so a
 * row is just a fragment of siblings — this names that intent. */
function ReactRowFragment({ children }: { children: ReactNode }) {
  return <>{children}</>
}
