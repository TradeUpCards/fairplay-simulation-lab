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
    <figure className="m-0">
      <figcaption className="mb-1 text-[0.8rem] text-muted">{metricLabel} — 8-hour divergence</figcaption>
      <svg
        className="h-auto w-full max-w-[420px] rounded-lg border border-line bg-surface-2"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${metricLabel} divergence, Standard vs FairPlay`}
      >
        <line
          className="stroke-1 stroke-[#4a5466] [stroke-dasharray:3_3]"
          x1={markerX}
          x2={markerX}
          y1={PAD / 2}
          y2={H - PAD}
        />
        <polyline
          data-testid="line-standard"
          className="stroke-2 stroke-[#d98c5f]"
          fill="none"
          points={points(standard)}
        />
        <polyline
          data-testid="line-fairplay"
          className="stroke-2 stroke-[#5fb0d9]"
          fill="none"
          points={points(fairplay)}
        />
        {hours.map((h) => (
          <text
            key={h}
            data-testid="hour-tick"
            className="fill-faint text-[9px]"
            x={x(h)}
            y={H - PAD / 3}
            textAnchor="middle"
          >
            {h}
          </text>
        ))}
      </svg>
      <div className="mt-[0.4rem] flex items-center gap-[0.4rem] text-[0.78rem] text-muted">
        <span className="ml-[0.6rem] inline-block h-[0.7rem] w-[0.7rem] rounded-xs bg-[#d98c5f]" aria-hidden="true" />{' '}
        Standard
        <span className="ml-[0.6rem] inline-block h-[0.7rem] w-[0.7rem] rounded-xs bg-[#5fb0d9]" aria-hidden="true" />{' '}
        FairPlay
      </div>
    </figure>
  )
}
