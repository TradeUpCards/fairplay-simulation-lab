import { useEffect, useMemo, useRef, useState } from 'react'
import type { RoomSweepFile, RoomTimeseriesFile, SweepCell } from '../data/types'
import { loadRoomSweep, loadRoomTimeseries } from '../data/shim'
import { useResource } from '../state/useResource'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { RaceChart, type RaceLine } from '../components/RaceChart'
import { RegimeHeatmap } from '../components/RegimeHeatmap'
import { RegimeTable } from '../components/RegimeTable'
import { DeparturesPanel } from '../components/DeparturesPanel'
import {
  ADVANTAGE_METRICS,
  CANDIDATE_POLICY,
  cellKey,
  DISPLAY_POLICIES,
  findTimeseriesCell,
  pickDefaultCell,
  RACE_POLICY_META,
  regimeLabel,
} from '../lib/dashboard'

interface DashboardData {
  sweep: RoomSweepFile
  timeseries: RoomTimeseriesFile
}

const loadDashboard = async (): Promise<DashboardData> => ({
  sweep: await loadRoomSweep(),
  timeseries: await loadRoomTimeseries(),
})

export function Dashboard() {
  const state = useResource(loadDashboard, (d) => d.sweep.datasets.length === 0)
  return (
    <section aria-label="sweep dashboard">
      <ResourceBoundary state={state} label="sweep results">
        {(d) => <DashboardView sweep={d.sweep} timeseries={d.timeseries} />}
      </ResourceBoundary>
    </section>
  )
}

/** Pure render from resolved data — the unit-tested surface. */
export function DashboardView({ sweep, timeseries }: DashboardData) {
  const [datasetIdx, setDatasetIdx] = useState(0)
  // Default the headline metric to the FairPlay cohort story.
  const [metricKey, setMetricKey] = useState<string>(
    ADVANTAGE_METRICS.find((m) => m.key === 'vulnerable_paid_seat_hours')?.key ??
      ADVANTAGE_METRICS[0].key,
  )

  const dataset = sweep.datasets[datasetIdx] ?? sweep.datasets[0]
  const metric = ADVANTAGE_METRICS.find((m) => m.key === metricKey) ?? ADVANTAGE_METRICS[0]
  const candidate = CANDIDATE_POLICY
  const tsDataset = timeseries.datasets[dataset.id]

  const [selectedKey, setSelectedKey] = useState<string | null>(() => {
    const d = pickDefaultCell(dataset, metricKey, candidate)
    return d ? cellKey(d) : null
  })
  // Reset the selected regime to the most candidate-favourable one when the dataset changes.
  useEffect(() => {
    const d = pickDefaultCell(dataset, metricKey, candidate)
    setSelectedKey(d ? cellKey(d) : null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset.id])

  const selectedCell = useMemo(
    () => dataset.cells.find((c) => cellKey(c) === selectedKey) ?? null,
    [dataset, selectedKey],
  )

  // Build the race for the selected regime: every policy present in its time-series.
  const tc = selectedCell
    ? findTimeseriesCell(tsDataset, selectedCell.tables, selectedCell.rate)
    : undefined
  const tHr = tc?.t_hr ?? []
  const raceLines: RaceLine[] = useMemo(() => {
    if (!tc || !selectedCell) return []
    const sub = regimeLabel(selectedCell.tables, selectedCell.rate)
    return Object.keys(tc.policies)
      .map((pol) => ({ pol, meta: RACE_POLICY_META[pol] }))
      .filter((x) => x.meta && tc.policies[x.pol]?.[metric.key])
      .sort((a, b) => a.meta.order - b.meta.order)
      .map(({ pol, meta }) => ({
        policy: pol,
        label: meta.label,
        sublabel: sub,
        color: meta.color,
        hero: meta.hero,
        ys: tc.policies[pol][metric.key],
      }))
  }, [tc, selectedCell, metric.key])

  const heroRef = useRef<HTMLDivElement>(null)
  const select = (cell: SweepCell) => {
    setSelectedKey(cellKey(cell))
    const el = heroRef.current
    if (el && typeof el.scrollIntoView === 'function') {
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
      el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
    }
  }

  const hasSeries = tHr.length > 0 && raceLines.length > 0

  return (
    <div className="grid gap-6">
      {/* title — app chrome (brass/felt) */}
      <header className="grid gap-1">
        <h2 className="m-0 text-[1.35rem] font-semibold tracking-[-0.01em] text-text">
          Routing sweep · Standard vs FairPlay
        </h2>
        <p className="m-0 text-[0.82rem] text-muted">
          One regime races every policy over an 8-hour room day — press play, then slice across
          regimes below.
        </p>
      </header>

      {/* controls — app chrome */}
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        {sweep.datasets.length > 1 && (
          <label className="flex items-center gap-2 text-[0.8rem] text-muted">
            Dataset
            <select
              className="rounded-md border border-line bg-surface px-2 py-1 text-text"
              value={datasetIdx}
              onChange={(e) => setDatasetIdx(Number(e.target.value))}
            >
              {sweep.datasets.map((d, i) => (
                <option key={d.id} value={i}>
                  {d.label}
                </option>
              ))}
            </select>
          </label>
        )}

        <div className="flex flex-col gap-1">
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.1em] text-faint">
            Metric
          </span>
          <div
            className="inline-flex rounded-full border border-line bg-surface-2 p-0.5"
            role="tablist"
            aria-label="metric"
          >
            {ADVANTAGE_METRICS.map((m) => (
              <button
                key={m.key}
                type="button"
                role="tab"
                aria-selected={metricKey === m.key}
                onClick={() => setMetricKey(m.key)}
                className={`rounded-full border-none px-3.5 py-[0.35rem] text-[0.76rem] ${
                  metricKey === m.key
                    ? 'bg-brass font-semibold text-[#1a1407]'
                    : 'bg-transparent text-muted hover:text-text'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.1em] text-faint">
            Regime · tables · arrivals/hr
          </span>
          <div className="flex flex-wrap gap-1.5">
            {dataset.cells.map((c) => {
              const on = cellKey(c) === selectedKey
              return (
                <button
                  key={cellKey(c)}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setSelectedKey(cellKey(c))}
                  className={`rounded-full border px-3 py-[0.3rem] font-mono text-[0.72rem] tabular-nums ${
                    on
                      ? 'border-brass bg-brass/15 text-text'
                      : 'border-line bg-surface text-muted hover:border-brass/60 hover:text-text'
                  }`}
                >
                  {c.tables}t · {c.rate}/hr
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* cinematic hero — one regime, policies race */}
      <div ref={heroRef} className="scroll-mt-24">
        {hasSeries && selectedCell ? (
          <RaceChart
            lines={raceLines}
            tHr={tHr}
            regimeLabel={regimeLabel(selectedCell.tables, selectedCell.rate)}
            metricLabel={metric.label}
            unit="hrs"
            resetKey={`${dataset.id}|${selectedKey}|${metric.key}`}
          />
        ) : (
          <p className="rounded-2xl border border-line bg-surface p-6 text-muted">
            No time-series available for this regime.
          </p>
        )}
      </div>

      {/* heatmap — slice across regimes (app chrome) */}
      <div className="rounded-xl border border-line bg-surface p-4">
        <RegimeHeatmap
          dataset={dataset}
          metricKey={metric.key}
          metricLabel={metric.label}
          candidate={candidate}
          selectedKey={selectedKey}
          onSelect={select}
        />
      </div>

      {/* per-regime table */}
      <div className="rounded-xl border border-line bg-surface p-4">
        <RegimeTable
          dataset={dataset}
          policies={DISPLAY_POLICIES}
          selectedKey={selectedKey}
          onSelect={select}
        />
      </div>

      {selectedCell?.departures && (
        <div className="rounded-xl border border-line bg-surface p-4">
          <DeparturesPanel cell={selectedCell} policies={DISPLAY_POLICIES} />
        </div>
      )}

      <p className="text-[0.72rem] leading-relaxed text-faint">
        Each line is a deterministic, seed-averaged run of the closed-loop room simulator over a
        shared arrival stream (the A/B invariant); FairPlay-Liveness is the liveness-aware arm.
        Throughput (total seat-hrs) structurally rewards concentration; vulnerable seat-hrs is the
        FairPlay cohort check. Numbers are illustrative until calibrated to real room traffic.
      </p>
    </div>
  )
}
