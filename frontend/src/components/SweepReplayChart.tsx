import { useEffect, useRef, useState } from 'react'
import type { TimeseriesCell } from '../data/types'
import { colorOf, interpAt, policyLabel, formatHrMin } from '../lib/dashboard'

const W = 760
const H = 340
const PAD_L = 56
const PAD_R = 18
const PAD_T = 18
const PAD_B = 34
const DURATION_SEC = 8 // wall-clock seconds for a full horizon replay
const POLICY_ORDER = ['standard', 'fairplay', 'fairplay_liveness']

interface Series {
  policy: string
  xs: number[]
  ys: number[]
}

function lineUpTo(
  xs: number[],
  ys: number[],
  p: number,
  sx: (x: number) => number,
  sy: (y: number) => number,
): string {
  const whole = Math.floor(p)
  const pts: string[] = []
  for (let i = 0; i <= Math.min(whole, xs.length - 1); i++) {
    pts.push(`${sx(xs[i]).toFixed(1)},${sy(ys[i]).toFixed(1)}`)
  }
  if (p > whole && whole < xs.length - 1) {
    pts.push(`${sx(interpAt(xs, p)).toFixed(1)},${sy(interpAt(ys, p)).toFixed(1)}`)
  }
  return pts.join(' ')
}

/**
 * Animated Standard-vs-FairPlay replay for one regime cell: each policy's
 * cumulative trace draws out over the horizon to a moving playhead. Dependency-
 * free inline SVG (matches DivergenceChart) with a RAF clock, play/pause, scrub,
 * and a live legend. The y-domain is fixed to the full series so lines grow into
 * a stable frame rather than rescaling mid-play.
 */
export function SweepReplayChart({
  cell,
  cellId,
  metricKey,
  metricLabel,
  unit,
  autoPlay = true,
}: {
  cell: TimeseriesCell
  cellId: string
  metricKey: string
  metricLabel: string
  unit: string
  autoPlay?: boolean
}) {
  // origin-anchored series (prepend t=0, value=0) so every line starts at 0.
  const series: Series[] = POLICY_ORDER.filter((p) => cell.policies[p]).map((policy) => ({
    policy,
    xs: [0, ...cell.t_hr],
    ys: [0, ...(cell.policies[policy][metricKey] ?? cell.t_hr.map(() => 0))],
  }))

  const N = series.length ? series[0].xs.length - 1 : 0
  const xMax = series.length ? series[0].xs[series[0].xs.length - 1] : 1
  const yMax = Math.max(1, ...series.flatMap((s) => s.ys))

  const sx = (x: number) => PAD_L + (x / (xMax || 1)) * (W - PAD_L - PAD_R)
  const sy = (y: number) => H - PAD_B - (y / yMax) * (H - PAD_T - PAD_B)

  const [p, setP] = useState(0)
  const [playing, setPlaying] = useState(autoPlay)
  const pRef = useRef(0)

  // reset + (auto)play whenever the selected regime or metric changes.
  useEffect(() => {
    pRef.current = 0
    setP(0)
    setPlaying(autoPlay)
  }, [cellId, metricKey, autoPlay])

  useEffect(() => {
    if (!playing || N <= 0) return
    let raf = 0
    let last = 0
    const speed = N / DURATION_SEC
    const step = (ts: number) => {
      if (!last) last = ts
      const dt = (ts - last) / 1000
      last = ts
      let next = pRef.current + dt * speed
      if (next >= N) {
        next = N
        pRef.current = next
        setP(next)
        setPlaying(false)
        return
      }
      pRef.current = next
      setP(next)
      raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [playing, N])

  const atEnd = p >= N && N > 0
  const seek = (v: number) => {
    pRef.current = v
    setP(v)
    setPlaying(false)
  }
  const toggle = () => {
    if (atEnd) {
      pRef.current = 0
      setP(0)
    }
    setPlaying((on) => !on)
  }

  const nowHr = interpAt(series.length ? series[0].xs : [0], p)
  const fmtVal = (v: number) => (unit === 'hrs' ? v.toFixed(1) : Math.round(v).toString())
  const hourTicks = Array.from({ length: Math.floor(xMax) + 1 }, (_, i) => i)

  return (
    <figure className="m-0">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <figcaption className="font-mono text-[0.66rem] uppercase tracking-[0.16em] text-faint">
          {metricLabel} over the {Math.round(xMax)}-hour room · cumulative replay
        </figcaption>
        <span className="font-mono text-[0.72rem] text-muted" data-testid="replay-clock">
          {formatHrMin(nowHr)} / {formatHrMin(xMax)}
        </span>
      </div>

      <svg
        className="h-auto w-full rounded-lg border border-line bg-surface-2"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${metricLabel} replay, Standard vs FairPlay`}
      >
        {/* y gridlines + labels (0, mid, max) */}
        {[0, 0.5, 1].map((f) => {
          const yv = yMax * f
          return (
            <g key={f}>
              <line
                x1={PAD_L}
                x2={W - PAD_R}
                y1={sy(yv)}
                y2={sy(yv)}
                className="stroke-line"
                strokeWidth={1}
              />
              <text x={PAD_L - 8} y={sy(yv) + 3} textAnchor="end" className="fill-faint text-[10px]">
                {fmtVal(yv)}
              </text>
            </g>
          )
        })}

        {/* hour ticks */}
        {hourTicks.map((h) => (
          <text key={h} x={sx(h)} y={H - PAD_B / 3} textAnchor="middle" className="fill-faint text-[9px]">
            {h}
          </text>
        ))}

        {/* playhead */}
        {N > 0 && (
          <line
            x1={sx(nowHr)}
            x2={sx(nowHr)}
            y1={PAD_T}
            y2={H - PAD_B}
            className="stroke-[#4a5466]"
            strokeWidth={1}
            strokeDasharray="3 3"
          />
        )}

        {/* policy lines drawing up to the playhead + leading dot */}
        {series.map((s) => (
          <g key={s.policy}>
            <polyline
              data-testid={`replay-line-${s.policy}`}
              points={lineUpTo(s.xs, s.ys, p, sx, sy)}
              fill="none"
              stroke={colorOf(s.policy)}
              strokeWidth={2.25}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {N > 0 && (
              <circle cx={sx(nowHr)} cy={sy(interpAt(s.ys, p))} r={3.5} fill={colorOf(s.policy)} />
            )}
          </g>
        ))}
      </svg>

      {/* transport */}
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={toggle}
          className="rounded-md border border-line bg-surface px-3 py-1 text-[0.8rem] text-text hover:border-brass"
          aria-label={playing ? 'pause replay' : atEnd ? 'replay' : 'play replay'}
        >
          {playing ? '❚❚ Pause' : atEnd ? '↺ Replay' : '▶ Play'}
        </button>
        <input
          type="range"
          min={0}
          max={N}
          step={0.01}
          value={p}
          aria-label="scrub replay"
          className="flex-1 accent-brass"
          onChange={(e) => seek(Number(e.target.value))}
        />
      </div>

      {/* live legend with current values at the playhead */}
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[0.8rem]">
        {series.map((s) => (
          <span key={s.policy} className="inline-flex items-center gap-[0.4rem] text-muted">
            <span
              className="inline-block h-[0.7rem] w-[0.7rem] rounded-xs"
              style={{ backgroundColor: colorOf(s.policy) }}
              aria-hidden="true"
            />
            {policyLabel(s.policy)}
            <strong className="text-text">
              {fmtVal(interpAt(s.ys, p))}
              {unit === 'hrs' ? ' h' : ''}
            </strong>
          </span>
        ))}
      </div>
    </figure>
  )
}
