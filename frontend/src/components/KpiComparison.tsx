import type { RoomMetricsHour } from '../data/types'
import { projectMetric, type NumericHourKey } from '../lib/simulator'

interface Kpi {
  key: NumericHourKey
  label: string
  fmt?: (n: number) => string
}

const KPIS: Kpi[] = [
  { key: 'cumulative_paid_seat_time_minutes', label: 'Paid seat-time (min)', fmt: (n) => n.toLocaleString() },
  { key: 'new_player_retention_pct', label: 'New-player retention (%)' },
  { key: 'active_healthy_tables', label: 'Healthy tables' },
  { key: 'avg_casual_session_length_minutes', label: 'Casual session (min)' },
  { key: 'early_table_breaks', label: 'Early table breaks' },
  { key: 'high_risk_seating_formations', label: 'High-risk formations' },
]

/**
 * Room KPIs for the current hour, Standard vs FairPlay side-by-side with a
 * lever-blended "Projected" column (R4). Projected equals Standard at 0%
 * adherence and FairPlay at 100% — the column is labelled illustrative because
 * mid-lever values interpolate rather than re-simulate.
 */
export function KpiComparison({
  standardRow,
  fairplayRow,
  adherence,
}: {
  standardRow: RoomMetricsHour
  fairplayRow: RoomMetricsHour
  adherence: number
}) {
  return (
    <table className="kpi-table">
      <caption>Room KPIs · Standard vs FairPlay (Projected = lever-blended, illustrative)</caption>
      <thead>
        <tr>
          <th scope="col">KPI</th>
          <th scope="col">Standard</th>
          <th scope="col">Projected</th>
          <th scope="col">FairPlay</th>
        </tr>
      </thead>
      <tbody>
        {KPIS.map((kpi) => {
          const std = standardRow[kpi.key]
          const fp = fairplayRow[kpi.key]
          const projected = projectMetric(std, fp, adherence)
          const fmt = kpi.fmt ?? ((n: number) => String(n))
          return (
            <tr key={kpi.key}>
              <th scope="row">{kpi.label}</th>
              <td data-testid={`std-${kpi.key}`}>{fmt(std)}</td>
              <td data-testid={`proj-${kpi.key}`} className="kpi-projected">{fmt(projected)}</td>
              <td data-testid={`fp-${kpi.key}`}>{fmt(fp)}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
