import type { RoomMetricsFile } from '../data/types'
import type { NumericHourKey } from '../lib/simulator'

const W = 320
const H = 150
const PAD = 28

/**
 * Lightweight inline-SVG line chart of one KPI across hours 1–8 for both paths,
 * with a marker at the current sim hour. Deliberately dependency-free; a richer
 * chart lib (Recharts/visx) is the deferred implementation choice in the plan.
 */
export function DivergenceChart({
  standard,
  fairplay,
  metricKey,
  metricLabel,
  currentHour,
}: {
  standard: RoomMetricsFile
  fairplay: RoomMetricsFile
  metricKey: NumericHourKey
  metricLabel: string
  currentHour: number
}) {
  const hours = standard.hours.map((h) => h.hour)
  const hMin = hours[0]
  const hMax = hours[hours.length - 1]
  const values = [...standard.hours, ...fairplay.hours].map((h) => h[metricKey])
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1

  const plotW = W - PAD * 2
  const plotH = H - PAD * 2
  const x = (hour: number) => PAD + ((hour - hMin) / (hMax - hMin || 1)) * plotW
  const y = (v: number) => H - PAD - ((v - min) / span) * plotH

  const points = (file: RoomMetricsFile) =>
    file.hours.map((h) => `${x(h.hour).toFixed(1)},${y(h[metricKey]).toFixed(1)}`).join(' ')

  const markerHour = Math.min(hMax, Math.max(hMin, currentHour))
  const markerX = x(markerHour)

  return (
    <figure className="divergence">
      <figcaption>{metricLabel} — 8-hour divergence</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${metricLabel} divergence, Standard vs FairPlay`}>
        <line className="chart-marker" x1={markerX} x2={markerX} y1={PAD / 2} y2={H - PAD} />
        <polyline data-testid="line-standard" className="line-standard" fill="none" points={points(standard)} />
        <polyline data-testid="line-fairplay" className="line-fairplay" fill="none" points={points(fairplay)} />
        {hours.map((h) => (
          <text key={h} data-testid="hour-tick" className="hour-tick" x={x(h)} y={H - PAD / 3} textAnchor="middle">
            {h}
          </text>
        ))}
      </svg>
      <div className="chart-legend">
        <span className="swatch sw-standard" aria-hidden="true" /> Standard
        <span className="swatch sw-fairplay" aria-hidden="true" /> FairPlay
      </div>
    </figure>
  )
}
