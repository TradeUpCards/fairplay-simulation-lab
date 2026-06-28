import { useEffect, useRef, useState } from 'react'
import { interpAt, formatHrMin } from '../lib/dashboard'

const W = 820
const H = 460
const PAD_L = 58
const PAD_R = 18
const PAD_T = 16
const PAD_B = 34
const DURATION_SEC = 8 // wall-clock seconds for a full horizon replay

export interface ChartLine {
  id: string
  regimeLabel: string
  tables: number | null
  rate: number
  policy: string
  policyLabel: string
  color: string
  dash: boolean
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
 * Multi-regime replay: Standard (dashed) + FairPlay (solid) for every regime,
 * colour-coded by regime, drawing out over the horizon to a moving playhead.
 * The y-axis auto-fits the *visible* lines (non-zero baseline), so toggling the
 * key down to one regime zooms in and the Standard-vs-FairPlay gap expands.
 */
export function SweepReplayChart({
  lines,
  tHr,
  metricLabel,
  unit,
  visible,
  onToggle,
  onShowAll,
  onHideAll,
  resetKey,
  autoPlay = true,
}: {
  lines: ChartLine[]
  tHr: number[]
  metricLabel: string
  unit: string
  visible: Set<string>
  onToggle: (id: string) => void
  onShowAll: () => void
  onHideAll: () => void
  resetKey: string
  autoPlay?: boolean
}) {
  const visibleLines = lines.filter((l) => visible.has(l.id))
  const N = tHr.length > 0 ? tHr.length - 1 : 0
  const xMax = tHr.length > 0 ? tHr[tHr.length - 1] : 1

  const vals = visibleLines.flatMap((l) => l.ys)
  const rawMin = vals.length ? Math.min(...vals) : 0
  const rawMax = vals.length ? Math.max(...vals) : 1
  const pad = (rawMax - rawMin) * 0.06 || Math.abs(rawMax) * 0.06 || 1
  // non-zero baseline to maximise vertical spread, but never show a negative
  // axis for non-negative (cumulative) data.
  let yMin = rawMin - pad
  if (rawMin >= 0 && yMin < 0) yMin = 0
  const yMax = rawMax + pad

  const sx = (x: number) => PAD_L + (x / (xMax || 1)) * (W - PAD_L - PAD_R)
  const sy = (y: number) => H - PAD_B - ((y - yMin) / (yMax - yMin || 1)) * (H - PAD_T - PAD_B)

  const [p, setP] = useState(0)
  const [playing, setPlaying] = useState(autoPlay)
  const pRef = useRef(0)

  // reset + (auto)play whenever the metric/dataset changes (not on toggle).
  useEffect(() => {
    pRef.current = 0
    setP(0)
    setPlaying(autoPlay)
  }, [resetKey, autoPlay])

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

  const nowHr = interpAt(tHr.length ? tHr : [0], p)
  const fmtVal = (v: number) => (unit === 'hrs' ? v.toFixed(0) : Math.round(v).toString())
  const hourTicks = Array.from({ length: Math.floor(xMax) + 1 }, (_, i) => i)

  // two-level key grouping: one row per table count (inventory), rate sub-groups inline.
  const byTables: { tables: number | null; rates: { rate: number; lines: ChartLine[] }[] }[] = []
  for (const l of lines) {
    let tg = byTables.find((t) => t.tables === l.tables)
    if (!tg) {
      tg = { tables: l.tables, rates: [] }
      byTables.push(tg)
    }
    let rg = tg.rates.find((r) => r.rate === l.rate)
    if (!rg) {
      rg = { rate: l.rate, lines: [] }
      tg.rates.push(rg)
    }
    rg.lines.push(l)
  }

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
        aria-label={`${metricLabel} replay across regimes, Standard vs FairPlay`}
      >
        {[0, 0.5, 1].map((f) => {
          const yv = yMin + (yMax - yMin) * f
          return (
            <g key={f}>
              <line x1={PAD_L} x2={W - PAD_R} y1={sy(yv)} y2={sy(yv)} className="stroke-line" strokeWidth={1} />
              <text x={PAD_L - 8} y={sy(yv) + 3} textAnchor="end" className="fill-faint text-[10px]">
                {fmtVal(yv)}
              </text>
            </g>
          )
        })}
        {hourTicks.map((h) => (
          <text key={h} x={sx(h)} y={H - PAD_B / 3} textAnchor="middle" className="fill-faint text-[9px]">
            {h}
          </text>
        ))}
        {N > 0 && visibleLines.length > 0 && (
          <line x1={sx(nowHr)} x2={sx(nowHr)} y1={PAD_T} y2={H - PAD_B} className="stroke-[#4a5466]" strokeWidth={1} strokeDasharray="3 3" />
        )}
        {visibleLines.map((l) => (
          <g key={l.id}>
            <polyline
              data-testid={`replay-line-${l.id}`}
              points={lineUpTo(tHr, l.ys, p, sx, sy)}
              fill="none"
              stroke={l.color}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              strokeDasharray={l.dash ? '5 4' : undefined}
              opacity={0.92}
            />
            {N > 0 && <circle cx={sx(nowHr)} cy={sy(interpAt(l.ys, p))} r={3} fill={l.color} />}
          </g>
        ))}
        {visibleLines.length === 0 && (
          <text x={W / 2} y={H / 2} textAnchor="middle" className="fill-muted text-[13px]">
            All lines hidden — enable some in the key below
          </text>
        )}
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

      {/* toggle key — Standard (dashed) + FairPlay (solid) per regime */}
      <div className="mt-3">
        <div className="mb-1.5 flex items-center gap-3 text-[0.72rem] text-muted">
          <span className="font-mono uppercase tracking-[0.12em] text-faint">Lines</span>
          <button type="button" onClick={onShowAll} className="rounded border border-line bg-surface px-2 py-0.5 hover:border-brass">
            Show all
          </button>
          <button type="button" onClick={onHideAll} className="rounded border border-line bg-surface px-2 py-0.5 hover:border-brass">
            Hide all
          </button>
          <span className="text-faint">solid = FairPlay · dashed = Standard</span>
        </div>
        <div className="grid gap-2">
          {byTables.map((tg) => (
            <div key={String(tg.tables)} className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
              <span className="w-[34px] shrink-0 font-mono text-[0.74rem] text-muted">{tg.tables}t</span>
              {tg.rates.map((rg) => (
                <div key={rg.rate} className="flex items-center gap-1.5">
                  <span className="font-mono text-[0.68rem] text-faint">{rg.rate}/hr</span>
                  {rg.lines.map((l) => {
                    const on = visible.has(l.id)
                    return (
                      <button
                        key={l.id}
                        type="button"
                        onClick={() => onToggle(l.id)}
                        aria-pressed={on}
                        aria-label={`${l.regimeLabel} ${l.policyLabel}`}
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[0.72rem] ${
                          on ? 'border-line text-text' : 'border-line/60 text-faint line-through'
                        }`}
                      >
                        <svg width="16" height="8" aria-hidden="true">
                          <line
                            x1="0"
                            y1="4"
                            x2="16"
                            y2="4"
                            stroke={on ? l.color : '#5b6473'}
                            strokeWidth="2"
                            strokeDasharray={l.dash ? '4 3' : undefined}
                          />
                        </svg>
                        {l.policyLabel}
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </figure>
  )
}
