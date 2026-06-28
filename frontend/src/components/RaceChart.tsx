import { useEffect, useRef, useState } from 'react'
import { interpAt } from '../lib/dashboard'
import { runChipBurst } from '../lib/chipBurst'
import { raceSound } from '../lib/raceSound'

/**
 * Cinematic policy race for ONE regime — the dashboard's showpiece, styled to
 * match demo/fairplay-live-sim.html: a dark navy stage with felt grain, one
 * glowing emerald hero line (the liveness arm) against neutral rivals, a big
 * HUD readout, and a polished re-ranking leaderboard. Reuses the chip-burst and
 * race-sound libs already ported from the demo.
 *
 * Policies often finish within a few percent (a +2% throughput win is invisible
 * on a 0-based axis), so the chart offers three ways to surface the gap for an
 * audience: drag-a-box zoom (re-fits both axes to the box), one-click zoom
 * presets (Finish / Last 2h), and a Δ-vs-Standard mode that re-plots each line
 * as its difference from Standard (Standard becomes a flat 0 and the rivals
 * fan out on an auto-fit axis).
 */
const W = 860
const H = 430
const PAD_L = 56
const PAD_R = 20
const PAD_T = 96
const PAD_B = 34
const DURATION_SEC = 10 // wall-clock seconds for a full-horizon replay
const DRAG_MIN = 8 // px — below this a drag is treated as a click, not a zoom

// faint poker-felt grain (greyscale fractal noise), inlined so the panel needs no asset
const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")"

export interface RaceLine {
  policy: string
  label: string
  sublabel: string
  color: string
  hero: boolean
  ys: number[]
}

interface View {
  x0: number
  x1: number
  y0: number
  y1: number
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

const ROW_H = 70

export function RaceChart({
  lines,
  tHr,
  regimeLabel,
  metricLabel,
  unit,
  resetKey,
  autoPlay = false,
}: {
  lines: RaceLine[]
  tHr: number[]
  regimeLabel: string
  metricLabel: string
  unit: string
  resetKey: string
  autoPlay?: boolean
}) {
  const N = tHr.length > 0 ? tHr.length - 1 : 0
  const xMax = tHr.length > 0 ? tHr[tHr.length - 1] : 1

  // ── absolute vs Δ-vs-Standard view ──
  const [mode, setMode] = useState<'abs' | 'delta'>('abs')
  const isDelta = mode === 'delta'
  const stdYs = lines.find((l) => l.policy === 'standard')?.ys ?? []
  const displayLines: RaceLine[] =
    isDelta && stdYs.length
      ? lines.map((l) => ({ ...l, ys: l.ys.map((y, i) => y - (stdYs[i] ?? 0)) }))
      : lines

  const dvals = displayLines.flatMap((l) => l.ys)
  const dMax = dvals.length ? Math.max(...dvals) : 1
  const dMin = dvals.length ? Math.min(...dvals) : 0

  // ── zoom: a boxed data window (both axes); null = auto-fit full ──
  const [view, setView] = useState<View | null>(null)
  useEffect(() => setView(null), [resetKey]) // a new regime/metric resets the zoom
  useEffect(() => setView(null), [mode]) // switching abs/delta re-fits the axis

  // full-view y-domain: 0-based for absolute (honest scale), auto-fit for delta
  const dPad = (dMax - dMin) * 0.12
  const fullY0 = isDelta ? dMin - dPad - 1e-4 : 0
  const fullY1 = isDelta ? dMax + dPad || 1 : dMax * 1.08 || 1
  const xDom0 = view ? view.x0 : 0
  const xDom1 = view ? view.x1 : xMax
  const yDom0 = view ? view.y0 : fullY0
  const yDom1 = view ? view.y1 : fullY1

  const sx = (x: number) => PAD_L + ((x - xDom0) / (xDom1 - xDom0 || 1)) * (W - PAD_L - PAD_R)
  const sy = (y: number) =>
    H - PAD_B - ((y - yDom0) / (yDom1 - yDom0 || 1)) * (H - PAD_T - PAD_B)
  const invX = (px: number) => xDom0 + ((px - PAD_L) / (W - PAD_L - PAD_R)) * (xDom1 - xDom0)
  const invY = (py: number) => yDom0 + ((H - PAD_B - py) / (H - PAD_T - PAD_B)) * (yDom1 - yDom0)

  const [p, setP] = useState(0)
  const [playing, setPlaying] = useState(autoPlay)
  const [muted, setMuted] = useState(false)
  const pRef = useRef(0)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const chipCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const chipCancelRef = useRef<(() => void) | null>(null)
  const firedRef = useRef(false)
  const leaderRef = useRef<string | null>(null)
  const hourRef = useRef(-1)

  // ── one-click zoom presets: fit the axes to a trailing time window ──
  const idxAtHour = (h: number): number => {
    if (tHr.length === 0) return 0
    if (h <= tHr[0]) return 0
    if (h >= tHr[tHr.length - 1]) return tHr.length - 1
    for (let i = 0; i < tHr.length - 1; i++) {
      if (h >= tHr[i] && h <= tHr[i + 1]) return i + (h - tHr[i]) / (tHr[i + 1] - tHr[i])
    }
    return tHr.length - 1
  }
  const viewForWindow = (xa: number, xb: number): View => {
    let lo = Infinity
    let hi = -Infinity
    for (const l of displayLines) {
      for (const xx of [xa, xb]) {
        const v = interpAt(l.ys, idxAtHour(xx))
        lo = Math.min(lo, v)
        hi = Math.max(hi, v)
      }
      tHr.forEach((t, i) => {
        if (t >= xa && t <= xb) {
          lo = Math.min(lo, l.ys[i])
          hi = Math.max(hi, l.ys[i])
        }
      })
    }
    if (!Number.isFinite(lo)) {
      lo = 0
      hi = 1
    }
    const pad = (hi - lo) * 0.14 || Math.abs(hi) * 0.06 || 1
    return { x0: xa, x1: xb, y0: lo - pad, y1: hi + pad }
  }
  const zoomFinish = () => setView(viewForWindow(Math.max(0, xMax - 0.75), xMax))
  const zoomLast2h = () => setView(viewForWindow(Math.max(0, xMax - 2), xMax))

  // ── drag-to-zoom selection (px in the SVG's viewBox space) ──
  const [sel, setSel] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null)
  const dragRef = useRef(false)

  const toSvg = (e: React.PointerEvent): { x: number; y: number } => {
    const r = svgRef.current?.getBoundingClientRect()
    if (!r) return { x: 0, y: 0 }
    const x = ((e.clientX - r.left) / r.width) * W
    const y = ((e.clientY - r.top) / r.height) * H
    return {
      x: Math.max(PAD_L, Math.min(W - PAD_R, x)),
      y: Math.max(PAD_T, Math.min(H - PAD_B, y)),
    }
  }
  const onDown = (e: React.PointerEvent) => {
    const pt = toSvg(e)
    dragRef.current = true
    setSel({ x0: pt.x, y0: pt.y, x1: pt.x, y1: pt.y })
    ;(e.target as Element).setPointerCapture?.(e.pointerId)
  }
  const onMove = (e: React.PointerEvent) => {
    if (!dragRef.current) return
    const pt = toSvg(e)
    setSel((s) => (s ? { ...s, x1: pt.x, y1: pt.y } : s))
  }
  const onUp = () => {
    dragRef.current = false
    setSel((s) => {
      if (s && Math.abs(s.x1 - s.x0) > DRAG_MIN && Math.abs(s.y1 - s.y0) > DRAG_MIN) {
        const x0 = invX(Math.min(s.x0, s.x1))
        const x1 = invX(Math.max(s.x0, s.x1))
        const y0 = invY(Math.max(s.y0, s.y1)) // lower pixel = higher value
        const y1 = invY(Math.min(s.y0, s.y1))
        setView({ x0, x1, y0, y1 })
      }
      return null
    })
  }

  useEffect(() => {
    pRef.current = 0
    setP(0)
    setPlaying(autoPlay)
    firedRef.current = false
    leaderRef.current = null
    hourRef.current = -1
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
    raceSound.resume()
    pRef.current = v
    setP(v)
    setPlaying(false)
  }
  const toggle = () => {
    raceSound.resume()
    if (atEnd) {
      pRef.current = 0
      setP(0)
    }
    setPlaying((on) => !on)
  }
  const toggleMute = () =>
    setMuted((m) => {
      const next = !m
      raceSound.setMuted(next)
      if (!next) raceSound.resume()
      return next
    })

  const nowHr = interpAt(tHr.length ? tHr : [0], p)
  const fmtShow = (v: number) =>
    unit === 'hrs' ? (isDelta ? v.toFixed(1) : v.toFixed(0)) : Math.round(v).toString()
  const fmtAxis = (v: number) =>
    unit === 'hrs' && yDom1 - yDom0 < 20 ? v.toFixed(1) : Math.round(v).toString()
  const fmtDelta = (v: number) => (unit === 'hrs' ? v.toFixed(1) : Math.round(v).toString())

  // hour ticks within the visible x-domain
  const hourTicks: number[] = []
  for (let h = Math.ceil(xDom0 - 1e-9); h <= Math.floor(xDom1 + 1e-9); h++) hourTicks.push(h)
  if (hourTicks.length < 2) hourTicks.splice(0, hourTicks.length, xDom0, (xDom0 + xDom1) / 2, xDom1)

  // standings, ranked by displayed value at the playhead
  const ranked = displayLines
    .map((l) => ({ l, v: interpAt(l.ys, p) }))
    .sort((a, b) => b.v - a.v)
  const rankById = new Map(ranked.map((r, i) => [r.l.policy, i]))
  const heroDisplay = displayLines.find((l) => l.hero) ?? displayLines[0]
  const heroShowV = heroDisplay ? interpAt(heroDisplay.ys, p) : 0
  // the "+x% vs Standard" readout always uses absolute values, in both modes
  const heroAbs = lines.find((l) => l.hero) ?? lines[0]
  const stdAbs = lines.find((l) => l.policy === 'standard')
  const heroAbsV = heroAbs ? interpAt(heroAbs.ys, p) : 0
  const stdAbsV = stdAbs ? interpAt(stdAbs.ys, p) : 0
  const deltaAbs = heroAbsV - stdAbsV
  const pct = stdAbsV > 0 ? (deltaAbs / stdAbsV) * 100 : 0
  const ahead = deltaAbs >= 0

  // chip-burst + win chime at the finish
  useEffect(() => {
    if (atEnd && !firedRef.current && ranked.length > 0) {
      firedRef.current = true
      const top = ranked[0]
      const canvas = chipCanvasRef.current
      if (canvas) {
        chipCancelRef.current?.()
        chipCancelRef.current = runChipBurst(canvas, sx(xMax), sy(interpAt(top.l.ys, N)))
      }
      if (!muted) raceSound.win()
    }
    if (!atEnd && firedRef.current) {
      firedRef.current = false
      chipCancelRef.current?.()
      chipCancelRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atEnd])

  // soft blip on lead change + per-hour tick
  const leaderId = ranked[0]?.l.policy ?? null
  useEffect(() => {
    if (leaderId && leaderRef.current && leaderId !== leaderRef.current && playing && !muted) {
      raceSound.overtake()
    }
    leaderRef.current = leaderId
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leaderId])
  useEffect(() => {
    const hr = Math.floor(nowHr)
    if (hr !== hourRef.current) {
      if (playing && !muted && hr > 0 && hr < Math.floor(xMax)) raceSound.hour()
      hourRef.current = hr
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nowHr, playing])

  const clk = `${String(Math.floor(nowHr)).padStart(2, '0')}:${String(
    Math.round((nowHr % 1) * 60),
  ).padStart(2, '0')}`
  const zoomed = view !== null
  const plotW = W - PAD_L - PAD_R
  const plotH = H - PAD_B - PAD_T
  const showZeroLine = isDelta && yDom0 < 0 && yDom1 > 0

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-[#1b2942] p-5"
      style={{
        background:
          'radial-gradient(1100px 520px at 80% -10%, rgba(46,230,166,0.10), transparent 60%),' +
          'radial-gradient(900px 520px at 8% 115%, rgba(124,140,255,0.10), transparent 60%),' +
          'linear-gradient(160deg, #0c1322, #070b14)',
      }}
    >
      {/* felt grain */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{ backgroundImage: GRAIN, opacity: 0.05, mixBlendMode: 'soft-light' }}
      />

      <div className="relative grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0">
          <div className="relative">
            <svg
              ref={svgRef}
              className="h-auto w-full touch-none select-none"
              viewBox={`0 0 ${W} ${H}`}
              role="img"
              aria-label={`${metricLabel} race for ${regimeLabel}`}
            >
              <defs>
                <filter id="heroGlow" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur stdDeviation="4" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <clipPath id="raceClip">
                  <rect x={PAD_L} y={PAD_T} width={plotW} height={plotH} />
                </clipPath>
              </defs>

              {/* gridlines */}
              {[0, 0.25, 0.5, 0.75, 1].map((f) => {
                const yv = yDom0 + (yDom1 - yDom0) * f
                return (
                  <g key={f}>
                    <line
                      x1={PAD_L}
                      x2={W - PAD_R}
                      y1={sy(yv)}
                      y2={sy(yv)}
                      stroke="rgba(255,255,255,0.045)"
                      strokeWidth={1}
                    />
                    <text
                      x={PAD_L - 9}
                      y={sy(yv) + 3}
                      textAnchor="end"
                      fontFamily="var(--font-mono)"
                      fontSize={10}
                      fill="#5d6e8c"
                    >
                      {fmtAxis(yv)}
                    </text>
                  </g>
                )
              })}
              {/* Δ-mode zero reference (Standard's baseline) */}
              {showZeroLine && (
                <g>
                  <line
                    x1={PAD_L}
                    x2={W - PAD_R}
                    y1={sy(0)}
                    y2={sy(0)}
                    stroke="rgba(159,177,204,0.5)"
                    strokeWidth={1}
                    strokeDasharray="4 3"
                  />
                  <text x={W - PAD_R} y={sy(0) - 4} textAnchor="end" fontSize={9} fill="#9fb1cc">
                    Standard
                  </text>
                </g>
              )}
              {hourTicks.map((h, i) => (
                <text
                  key={`${h}-${i}`}
                  x={sx(h)}
                  y={H - 10}
                  textAnchor="middle"
                  fontSize={10}
                  fill="#4a5871"
                >
                  {Number.isInteger(h) ? `${h}h` : `${h.toFixed(1)}h`}
                </text>
              ))}

              {/* clipped plot: playhead + lines */}
              <g clipPath="url(#raceClip)">
                {N > 0 && p > 0 && nowHr >= xDom0 && nowHr <= xDom1 && (
                  <line
                    x1={sx(nowHr)}
                    x2={sx(nowHr)}
                    y1={PAD_T}
                    y2={H - PAD_B}
                    stroke="rgba(46,230,166,0.22)"
                    strokeWidth={1.5}
                  />
                )}
                {[...displayLines]
                  .sort((a, b) => Number(a.hero) - Number(b.hero))
                  .map((l) => (
                    <g key={l.policy}>
                      <polyline
                        data-testid={`race-line-${l.policy}`}
                        points={lineUpTo(tHr, l.ys, p, sx, sy)}
                        fill="none"
                        stroke={l.color}
                        strokeWidth={l.hero ? 3.4 : 2}
                        strokeLinejoin="round"
                        strokeLinecap="round"
                        opacity={l.hero ? 1 : 0.85}
                        filter={l.hero ? 'url(#heroGlow)' : undefined}
                      />
                      {N > 0 && nowHr >= xDom0 && nowHr <= xDom1 && (
                        <circle
                          cx={sx(nowHr)}
                          cy={sy(interpAt(l.ys, p))}
                          r={l.hero ? 5 : 3.4}
                          fill={l.hero ? '#eafff7' : '#cfe6ff'}
                          filter={l.hero ? 'url(#heroGlow)' : undefined}
                        />
                      )}
                    </g>
                  ))}
              </g>

              {/* drag-capture overlay (transparent) + live selection box */}
              <rect
                x={PAD_L}
                y={PAD_T}
                width={plotW}
                height={plotH}
                fill="transparent"
                style={{ cursor: 'crosshair' }}
                onPointerDown={onDown}
                onPointerMove={onMove}
                onPointerUp={onUp}
                onPointerLeave={onUp}
              />
              {sel && (
                <rect
                  x={Math.min(sel.x0, sel.x1)}
                  y={Math.min(sel.y0, sel.y1)}
                  width={Math.abs(sel.x1 - sel.x0)}
                  height={Math.abs(sel.y1 - sel.y0)}
                  fill="rgba(46,230,166,0.12)"
                  stroke="rgba(46,230,166,0.7)"
                  strokeWidth={1}
                  strokeDasharray="4 3"
                  pointerEvents="none"
                />
              )}
            </svg>

            <canvas
              ref={chipCanvasRef}
              width={W}
              height={H}
              className="pointer-events-none absolute inset-0 h-full w-full"
              aria-hidden="true"
            />

            {/* HUD — run clock, metric name, big hero number, delta vs Standard */}
            <div className="pointer-events-none absolute left-6 top-5">
              <div className="font-mono text-[0.7rem] tracking-[0.06em] text-[#8fa2bf]">
                RUN CLOCK · <span className="text-[#eaf1fb]">{clk}</span> /{' '}
                {String(Math.floor(xMax)).padStart(2, '0')}:00
              </div>
              <div className="mt-3 font-mono text-[0.66rem] uppercase tracking-[0.14em] text-[#5d6e8c]">
                {metricLabel}
                {isDelta ? ' · Δ vs Standard' : ''}
              </div>
              <div
                data-testid="race-score"
                className="mt-1 text-[3.1rem] font-extrabold leading-none tabular-nums text-[#2ee6a6]"
                style={{ textShadow: '0 0 34px rgba(46,230,166,0.5)' }}
              >
                {isDelta && heroShowV >= 0 ? '+' : ''}
                {fmtShow(heroShowV)}
                <span className="ml-1 text-[1.4rem] font-semibold text-[#8fa2bf]">
                  {unit === 'hrs' ? 'h' : ''}
                </span>
              </div>
              {p > 0.04 * N && (
                <div className="mt-1.5 text-[0.85rem] font-semibold text-[#8fa2bf]">
                  {ahead ? (
                    <>
                      <span className="text-[#2ee6a6]">{heroDisplay?.label} ahead</span> · +
                      {fmtDelta(deltaAbs)}
                      {unit === 'hrs' ? 'h' : ''} ({pct >= 0 ? '+' : ''}
                      {pct.toFixed(1)}%) vs Standard
                    </>
                  ) : (
                    <>trailing Standard by {fmtDelta(-deltaAbs)}
                      {unit === 'hrs' ? 'h' : ''} — the surge is coming…</>
                  )}
                </div>
              )}
            </div>

            {/* zoom affordance / reset */}
            {zoomed ? (
              <button
                type="button"
                onClick={() => setView(null)}
                className="absolute right-3 top-3 rounded-md border border-[#2ee6a6]/50 bg-[rgba(8,18,14,0.85)] px-2.5 py-1 text-[0.72rem] font-semibold text-[#2ee6a6] hover:bg-[rgba(8,18,14,0.95)]"
              >
                ⤢ Reset zoom
              </button>
            ) : (
              p > 0 && (
                <div className="pointer-events-none absolute right-3 top-3 rounded-md border border-[#1b2942] bg-[rgba(8,12,20,0.6)] px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-[0.1em] text-[#5d6e8c]">
                  drag to zoom
                </div>
              )
            )}

            {/* run CTA */}
            {p === 0 && !playing && (
              <div className="absolute inset-0 flex items-center justify-center">
                <button
                  type="button"
                  onClick={toggle}
                  aria-label={`run the ${Math.round(xMax)}-hour simulation`}
                  className="flex items-center gap-3 rounded-2xl border-0 px-8 py-4 text-[1.1rem] font-bold text-[#04120c]"
                  style={{
                    background: 'linear-gradient(180deg,#46f3b4,#1fbf86)',
                    boxShadow:
                      '0 12px 40px rgba(46,230,166,0.4), inset 0 1px 0 rgba(255,255,255,0.4)',
                  }}
                >
                  <span
                    style={{
                      width: 0,
                      height: 0,
                      borderLeft: '14px solid #04120c',
                      borderTop: '9px solid transparent',
                      borderBottom: '9px solid transparent',
                    }}
                  />
                  Run {Math.round(xMax)}-Hour Simulation
                </button>
              </div>
            )}
          </div>

          {/* transport */}
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={toggle}
              className="rounded-md border border-[#1b2942] bg-[rgba(255,255,255,0.04)] px-3 py-1 text-[0.8rem] text-[#eaf1fb] hover:border-[#2ee6a6]"
              aria-label={playing ? 'pause replay' : atEnd ? 'replay' : 'play replay'}
            >
              {playing ? '❚❚ Pause' : atEnd ? '↺ Replay' : '▶ Play'}
            </button>
            <button
              type="button"
              onClick={toggleMute}
              className="rounded-md border border-[#1b2942] bg-[rgba(255,255,255,0.04)] px-2.5 py-1 text-[0.85rem] hover:border-[#2ee6a6]"
              aria-label={muted ? 'unmute race sounds' : 'mute race sounds'}
              aria-pressed={muted}
            >
              {muted ? '🔇' : '🔊'}
            </button>
            <input
              type="range"
              min={0}
              max={N}
              step={0.01}
              value={p}
              aria-label="scrub replay"
              className="flex-1 accent-[#2ee6a6]"
              onChange={(e) => seek(Number(e.target.value))}
            />
          </div>

          {/* view controls: absolute vs Δ, and one-click zoom presets */}
          <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-2">
            <div
              className="inline-flex rounded-full border border-[#1b2942] bg-[rgba(255,255,255,0.03)] p-0.5"
              role="tablist"
              aria-label="value mode"
            >
              {(['abs', 'delta'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => setMode(m)}
                  className={`rounded-full px-3 py-[0.28rem] text-[0.72rem] font-semibold ${
                    mode === m
                      ? 'bg-[#2ee6a6] text-[#04120c]'
                      : 'bg-transparent text-[#8fa2bf] hover:text-[#eaf1fb]'
                  }`}
                >
                  {m === 'abs' ? 'Absolute' : 'Δ vs Standard'}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-[0.6rem] uppercase tracking-[0.1em] text-[#5d6e8c]">
                Zoom
              </span>
              <button
                type="button"
                onClick={zoomFinish}
                className="rounded-md border border-[#1b2942] bg-[rgba(255,255,255,0.04)] px-2.5 py-1 text-[0.72rem] text-[#eaf1fb] hover:border-[#2ee6a6]"
              >
                Finish
              </button>
              <button
                type="button"
                onClick={zoomLast2h}
                className="rounded-md border border-[#1b2942] bg-[rgba(255,255,255,0.04)] px-2.5 py-1 text-[0.72rem] text-[#eaf1fb] hover:border-[#2ee6a6]"
              >
                Last 2h
              </button>
              <button
                type="button"
                onClick={() => setView(null)}
                aria-disabled={!zoomed}
                className={`rounded-md border px-2.5 py-1 text-[0.72rem] ${
                  zoomed
                    ? 'border-[#1b2942] bg-[rgba(255,255,255,0.04)] text-[#eaf1fb] hover:border-[#2ee6a6]'
                    : 'border-[#1b2942]/50 bg-transparent text-[#5d6e8c]'
                }`}
              >
                Full
              </button>
            </div>
          </div>

          <p className="mt-2 font-mono text-[0.62rem] text-[#5d6e8c]">
            {isDelta
              ? 'Δ mode: each line is its gap to Standard (the dashed 0 line) — the y-axis auto-fits so a few-percent win fills the panel.'
              : zoomed
                ? `Zoomed · ${fmtAxis(yDom0)}–${fmtAxis(yDom1)}${unit === 'hrs' ? 'h' : ''} · ${xDom0.toFixed(1)}–${xDom1.toFixed(1)}h — Reset to see the full scale`
                : 'Tip: drag a box across the finish (or use the Zoom presets) — the y-axis re-fits so the gap between policies is visible.'}
          </p>
        </div>

        {/* leaderboard */}
        <div className="min-w-0">
          <div className="mb-3 font-mono text-[0.62rem] uppercase tracking-[0.16em] text-[#5d6e8c]">
            Live standings · {regimeLabel}
          </div>
          <div className="relative" style={{ height: Math.max(displayLines.length, 1) * ROW_H }}>
            {displayLines.map((l) => {
              const rank = rankById.get(l.policy) ?? 0
              const leader = rank === 0
              const v = interpAt(l.ys, p)
              return (
                <div
                  key={l.policy}
                  data-testid={`race-standing-${l.policy}`}
                  data-rank={rank}
                  className="absolute inset-x-0 flex items-center gap-3 rounded-xl border px-3.5"
                  style={{
                    height: ROW_H - 8,
                    transform: `translateY(${rank * ROW_H}px)`,
                    transition: 'transform 0.6s cubic-bezier(0.3,0.8,0.2,1)',
                    borderColor: l.hero ? 'rgba(46,230,166,0.45)' : '#1b2942',
                    background: l.hero
                      ? 'linear-gradient(100deg, rgba(46,230,166,0.10), rgba(46,230,166,0.02))'
                      : 'rgba(255,255,255,0.022)',
                    boxShadow: l.hero
                      ? '0 0 0 1px rgba(46,230,166,0.18), 0 8px 30px rgba(46,230,166,0.10)'
                      : undefined,
                  }}
                >
                  <span className="w-4 font-mono text-[0.8rem] text-[#5d6e8c]">{rank + 1}</span>
                  <span
                    className="h-2.5 w-2.5 flex-none rounded-full"
                    style={{ background: l.color, boxShadow: `0 0 10px ${l.color}` }}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[0.9rem] font-semibold text-[#eaf1fb]">
                      {l.label}
                    </span>
                    <span className="block text-[0.7rem] text-[#5d6e8c]">{l.sublabel}</span>
                  </span>
                  <span
                    className="font-mono text-[1.25rem] font-bold tabular-nums"
                    style={{ color: l.hero ? '#2ee6a6' : '#eaf1fb' }}
                  >
                    {isDelta && v >= 0 ? '+' : ''}
                    {fmtShow(v)}
                    <span className="ml-0.5 text-[0.72rem] text-[#8fa2bf]">
                      {unit === 'hrs' ? 'h' : ''}
                    </span>
                  </span>
                  <span
                    className="w-4 text-[0.95rem] transition-opacity"
                    style={{ opacity: leader && l.hero ? 1 : 0 }}
                    aria-hidden
                  >
                    👑
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
