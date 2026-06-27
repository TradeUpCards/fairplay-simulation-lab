import { useMemo, useRef, useState } from 'react'
import type { RoomSweepFile, RoomTimeseriesFile, SweepCell } from '../data/types'
import { loadRoomSweep, loadRoomTimeseries } from '../data/shim'
import { useResource } from '../state/useResource'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { SweepReplayChart } from '../components/SweepReplayChart'
import { RegimeHeatmap } from '../components/RegimeHeatmap'
import { RegimeTable } from '../components/RegimeTable'
import {
  ADVANTAGE_METRICS,
  advantage,
  candidatePolicies,
  cellKey,
  findTimeseriesCell,
  pickDefaultCell,
  policyLabel,
} from '../lib/dashboard'

interface DashboardData {
  sweep: RoomSweepFile
  timeseries: RoomTimeseriesFile
}

const loadDashboard = async (): Promise<DashboardData> => ({
  sweep: await loadRoomSweep(),
  timeseries: await loadRoomTimeseries(),
})

const CONFIG_CHIPS: { key: string; label: string }[] = [
  { key: 'fixture', label: 'fixture' },
  { key: 'horizon_min', label: 'horizon (min)' },
  { key: 'arrival_mode', label: 'arrivals' },
  { key: 'formation_mode', label: 'formation' },
  { key: 'behavior', label: 'behavior' },
  { key: 'equity_samples', label: 'equity samples' },
]

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
  const [metricKey, setMetricKey] = useState<string>(ADVANTAGE_METRICS[0].key)
  const [candidatePref, setCandidatePref] = useState<string>('fairplay')

  const dataset = sweep.datasets[datasetIdx] ?? sweep.datasets[0]
  const metric =
    ADVANTAGE_METRICS.find((m) => m.key === metricKey) ?? ADVANTAGE_METRICS[0]
  // which non-baseline policy the heatmap scores against; fall back if absent.
  const candidates = candidatePolicies(dataset)
  const candidate = candidates.includes(candidatePref) ? candidatePref : (candidates[0] ?? 'fairplay')

  const [selectedKey, setSelectedKey] = useState<string | null>(
    () => {
      const d = pickDefaultCell(dataset, metricKey, candidate)
      return d ? cellKey(d) : null
    },
  )

  const selectedCell: SweepCell | undefined =
    dataset.cells.find((c) => cellKey(c) === selectedKey) ?? dataset.cells[0]

  const tsDataset = timeseries.datasets[dataset.id]
  const tsCell = selectedCell
    ? findTimeseriesCell(tsDataset, selectedCell.tables, selectedCell.rate)
    : undefined

  // headline read: how many regimes favour the candidate on the chosen metric.
  const wins = useMemo(
    () => dataset.cells.filter((c) => (advantage(c, metricKey, candidate) ?? 0) > 0).length,
    [dataset, metricKey, candidate],
  )

  // Selecting from the heatmap/table re-binds the hero; bring it back into view
  // (the chart often sits above the fold once you've scrolled to pick a cell).
  const heroRef = useRef<HTMLDivElement>(null)
  const select = (cell: SweepCell) => {
    setSelectedKey(cellKey(cell))
    const el = heroRef.current
    if (el && typeof el.scrollIntoView === 'function') {
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
      el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
    }
  }

  return (
    <div className="grid gap-6">
      {/* title + caveat */}
      <header className="grid gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="m-0 text-[1.25rem] text-text">Routing sweep — Standard vs FairPlay</h2>
          <span className="rounded-full border border-[#7a5b34] bg-[rgba(199,154,75,0.10)] px-2.5 py-0.5 font-mono text-[0.62rem] uppercase tracking-[0.14em] text-brass">
            Illustrative synthetic data — not a validated retention claim
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[0.66rem] text-faint">
          {CONFIG_CHIPS.map(({ key, label }) =>
            dataset.config[key] != null ? (
              <span key={key}>
                {label} <span className="text-muted">{String(dataset.config[key])}</span>
              </span>
            ) : null,
          )}
          <span>
            seeds <span className="text-muted">{dataset.seeds.join(' / ')}</span>
          </span>
          <span>
            generated <span className="text-muted">{sweep.generated_at}</span>
          </span>
        </div>
      </header>

      {/* stat strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Regimes tested" value={String(dataset.cells.length)} hint={`${dataset.table_axis.length} inventories × ${dataset.rate_axis.length} rates`} />
        <Stat label={`${policyLabel(candidate)}-ahead cells`} value={`${wins}/${dataset.cells.length}`} hint={metric.label} />
        <Stat label="Policies" value={String(dataset.policies.length)} hint={dataset.policies.map((p) => p.replace('fairplay_', 'fp-')).join(' · ')} />
        <Stat label="Seeds / cell" value={String(dataset.seeds.length)} hint="per-seed win dots below" />
      </div>

      {/* controls */}
      <div className="flex flex-wrap items-center gap-4">
        {sweep.datasets.length > 1 && (
          <label className="flex items-center gap-2 text-[0.8rem] text-muted">
            Dataset
            <select
              className="rounded-md border border-line bg-surface px-2 py-1 text-text"
              value={datasetIdx}
              onChange={(e) => {
                const idx = Number(e.target.value)
                setDatasetIdx(idx)
                const d = pickDefaultCell(sweep.datasets[idx], metricKey, candidate)
                setSelectedKey(d ? cellKey(d) : null)
              }}
            >
              {sweep.datasets.map((d, i) => (
                <option key={d.id} value={i}>
                  {d.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="inline-flex items-center gap-2 text-[0.8rem] text-muted">
          Metric
          <div className="inline-flex rounded-full border border-line bg-surface-2 p-0.5" role="tablist" aria-label="metric">
            {ADVANTAGE_METRICS.map((m) => (
              <button
                key={m.key}
                type="button"
                role="tab"
                aria-selected={metricKey === m.key}
                onClick={() => setMetricKey(m.key)}
                className={`rounded-full border-none px-3 py-[0.3rem] text-[0.74rem] ${
                  metricKey === m.key ? 'bg-brass font-semibold text-[#1a1407]' : 'bg-transparent text-muted hover:text-text'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
        {candidates.length > 1 && (
          <div className="inline-flex items-center gap-2 text-[0.8rem] text-muted">
            Compare
            <div className="inline-flex rounded-full border border-line bg-surface-2 p-0.5" role="tablist" aria-label="advantage policy">
              {candidates.map((p) => (
                <button
                  key={p}
                  type="button"
                  role="tab"
                  aria-selected={candidate === p}
                  onClick={() => setCandidatePref(p)}
                  className={`rounded-full border-none px-3 py-[0.3rem] text-[0.74rem] ${
                    candidate === p ? 'bg-brass font-semibold text-[#1a1407]' : 'bg-transparent text-muted hover:text-text'
                  }`}
                >
                  {policyLabel(p)}
                </button>
              ))}
            </div>
            <span className="text-faint">vs Standard</span>
          </div>
        )}
      </div>

      {/* animated hero, bound to the selected regime */}
      <div ref={heroRef} className="scroll-mt-24 rounded-xl border border-line bg-surface p-4">
        <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="m-0 text-[1rem] text-text">
            {selectedCell ? (
              <>
                Replay · <span className="text-brass">{selectedCell.tables} tables · {selectedCell.rate} joins/hr</span>
              </>
            ) : (
              'Replay'
            )}
          </h3>
          <span className="text-[0.74rem] text-muted">Click any heatmap cell or table row to replay that regime</span>
        </div>
        {tsCell ? (
          <SweepReplayChart
            cell={tsCell}
            cellId={`${dataset.id}|${selectedKey ?? ''}`}
            metricKey={metric.key}
            metricLabel={metric.label}
            unit="hrs"
          />
        ) : (
          <p className="text-muted">No time-series available for this regime.</p>
        )}
      </div>

      {/* heatmap + table */}
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

      <div className="rounded-xl border border-line bg-surface p-4">
        <RegimeTable dataset={dataset} selectedKey={selectedKey} onSelect={select} />
      </div>

      <p className="text-[0.72rem] leading-relaxed text-faint">
        Each cell is a deterministic, seed-averaged run of the closed-loop room simulator over a
        shared arrival stream (the A/B invariant). Throughput (total seat-hrs) structurally rewards
        concentration; vulnerable seat-hrs is the FairPlay cohort check. Numbers are illustrative
        until calibrated to real room traffic.
      </p>
    </div>
  )
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2.5">
      <div className="font-mono text-[0.6rem] uppercase tracking-[0.13em] text-faint">{label}</div>
      <div className="mt-0.5 text-[1.35rem] font-semibold text-text">{value}</div>
      <div className="mt-0.5 text-[0.7rem] text-muted">{hint}</div>
    </div>
  )
}
