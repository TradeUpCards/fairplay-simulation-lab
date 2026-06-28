/**
 * Live standings for the replay chart. Rows are rendered in a STABLE DOM order
 * (keyed by line id) and positioned by their current rank via `translateY`, so a
 * rank swap animates the row sliding past its neighbour (CSS transition) instead
 * of React re-ordering the list. The current leader carries the crown — it moves
 * with the lead as the race re-ranks, and stays on the winner at the finish.
 */
export interface StandingRow {
  id: string
  /** Policy label, e.g. "FairPlay". */
  label: string
  /** Regime label, e.g. "50t · 20/hr". */
  sublabel: string
  color: string
  value: number
  /** 0-based current rank (0 = leader). */
  rank: number
}

export const STANDINGS_ROW_H = 56

export function Standings({ rows, unit }: { rows: StandingRow[]; unit: string }) {
  const fmt = (v: number) => (unit === 'hrs' ? v.toFixed(0) : Math.round(v).toString())
  const suffix = unit === 'hrs' ? 'h' : ''

  return (
    <div>
      <h3 className="m-0 mb-3 text-right font-mono text-[0.62rem] uppercase tracking-[0.16em] text-faint">
        Live standings
      </h3>
      <div className="relative" style={{ height: Math.max(rows.length, 1) * STANDINGS_ROW_H }}>
        {rows.map((r) => {
          const leader = r.rank === 0
          return (
            <div
              key={r.id}
              data-testid={`standing-${r.id}`}
              data-rank={r.rank}
              className={`absolute inset-x-0 flex items-center gap-2.5 rounded-lg border px-3 ${
                leader
                  ? 'border-brass/60 bg-[rgba(199,154,75,0.09)] shadow-[0_0_0_1px_rgba(199,154,75,0.18)]'
                  : 'border-line bg-surface-2'
              }`}
              style={{
                height: STANDINGS_ROW_H - 8,
                transform: `translateY(${r.rank * STANDINGS_ROW_H}px)`,
                transition: 'transform .5s cubic-bezier(.3,.8,.2,1)',
              }}
            >
              <span className="w-4 text-right font-mono text-[0.72rem] text-faint">
                {r.rank + 1}
              </span>
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{
                  backgroundColor: r.color,
                  boxShadow: `0 0 8px ${r.color}`,
                }}
                aria-hidden="true"
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[0.82rem] font-semibold text-text">
                  {r.label}
                </span>
                <span className="block truncate text-[0.68rem] text-faint">{r.sublabel}</span>
              </span>
              <span
                className={`font-mono text-[1rem] font-bold tabular-nums ${leader ? 'text-brass' : 'text-text'}`}
              >
                {fmt(r.value)}
                <span className="ml-0.5 text-[0.7rem] text-muted">{suffix}</span>
              </span>
              <span
                className={`w-4 text-[0.95rem] transition-opacity duration-300 ${leader ? 'opacity-100' : 'opacity-0'}`}
                aria-hidden="true"
              >
                👑
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
