import { useEffect, useMemo, useRef, useState } from 'react'
import type { RoomSweepFile, RoomTimeseriesFile, SweepCell } from '../data/types'
import { loadRoomSweep, loadRoomTimeseries } from '../data/shim'
import { useResource } from '../state/useResource'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { SweepReplayChart, type ChartLine } from '../components/SweepReplayChart'
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
  policyLabel,
  regimeColor,
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
  const [metricKey, setMetricKey] = useState<string>(ADVANTAGE_METRICS[0].key)

  const dataset = sweep.datasets[datasetIdx] ?? sweep.datasets[0]
  const metric = ADVANTAGE_METRICS.find((m) => m.key === metricKey) ?? ADVANTAGE_METRICS[0]
  // The dashboard scores the liveness arm against Standard, relabelled "FairPlay".
  const candidate = CANDIDATE_POLICY
  const tsDataset = timeseries.datasets[dataset.id]

  // Shared time axis (all regimes share the sampling cadence/horizon).
  const tHr = useMemo(() => {
    const first = Object.values(tsDataset?.cells ?? {})[0]
    return first?.t_hr ?? []
  }, [tsDataset])

  // One line per (regime, shown-policy): Standard dashed + FairPlay solid, coloured by regime.
  const lines: ChartLine[] = useMemo(() => {
    const out: ChartLine[] = []
    dataset.cells.forEach((c, i) => {
      const tc = findTimeseriesCell(tsDataset, c.tables, c.rate)
      if (!tc) return
      const color = regimeColor(i)
      for (const pol of DISPLAY_POLICIES) {
        const ys = tc.policies[pol]?.[metric.key]
        if (!ys) continue
        out.push({
          id: `${c.tables}|${c.rate}|${pol}`,
          regimeLabel: regimeLabel(c.tables, c.rate),
          tables: c.tables,
          rate: c.rate,
          policy: pol,
          policyLabel: policyLabel(pol),
          color,
          dash: pol === 'standard',
          ys,
        })
      }
    })
    return out
  }, [dataset, tsDataset, metric.key])

  const allIds = useMemo(() => lines.map((l) => l.id), [lines])
  const [visible, setVisible] = useState<Set<string>>(() => new Set(allIds))
  // Reset to "all visible" when the dataset (and thus the line set) changes.
  useEffect(() => {
    setVisible(new Set(lines.map((l) => l.id)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset.id])

  const toggleLine = (id: string) =>
    setVisible((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const showAll = () => setVisible(new Set(allIds))
  const hideAll = () => setVisible(new Set())
  // flip every line of one policy (all Standard / all FairPlay) at once: hide
  // them if any are showing, otherwise reveal them all.
  const togglePolicy = (policy: string) =>
    setVisible((prev) => {
      const ids = lines.filter((l) => l.policy === policy).map((l) => l.id)
      const anyOn = ids.some((id) => prev.has(id))
      const next = new Set(prev)
      for (const id of ids) {
        if (anyOn) next.delete(id)
        else next.add(id)
      }
      return next
    })

  const [selectedKey, setSelectedKey] = useState<string | null>(() => {
    const d = pickDefaultCell(dataset, metricKey, candidate)
    return d ? cellKey(d) : null
  })

  // Clicking a regime in the heatmap/table solos its two lines and scrolls the chart up.
  const heroRef = useRef<HTMLDivElement>(null)
  const select = (cell: SweepCell) => {
    setSelectedKey(cellKey(cell))
    const ids = DISPLAY_POLICIES.map((p) => `${cell.tables}|${cell.rate}|${p}`).filter((id) =>
      allIds.includes(id),
    )
    if (ids.length) setVisible(new Set(ids))
    const el = heroRef.current
    if (el && typeof el.scrollIntoView === 'function') {
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
      el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
    }
  }

  const hasSeries = tHr.length > 0 && lines.length > 0
  const selectedCell = useMemo(
    () => dataset.cells.find((c) => cellKey(c) === selectedKey) ?? null,
    [dataset, selectedKey],
  )

  return (
    <div className="grid gap-6">
      {/* title */}
      <header className="grid gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="m-0 text-[1.25rem] text-text">Routing sweep — Standard vs FairPlay</h2>
        </div>
      </header>

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
                className={`rounded-full border-none px-3 py-[0.3rem] text-[0.74rem] ${
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
      </div>

      {/* animated hero — every regime, Standard vs FairPlay */}
      <div ref={heroRef} className="scroll-mt-24 rounded-xl border border-line bg-surface p-4">
        <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="m-0 text-[1rem] text-text">
            Replay · <span className="text-brass">all regimes</span> · {metric.label}
          </h3>
        </div>
        {hasSeries ? (
          <SweepReplayChart
            lines={lines}
            tHr={tHr}
            metricLabel={metric.label}
            unit="hrs"
            visible={visible}
            onToggle={toggleLine}
            onTogglePolicy={togglePolicy}
            onShowAll={showAll}
            onHideAll={hideAll}
            resetKey={`${dataset.id}|${metric.key}`}
          />
        ) : (
          <p className="text-muted">No time-series available for this dataset.</p>
        )}
      </div>

      {/* heatmap */}
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

      {/* per-regime table (Standard + FairPlay only) */}
      <div className="rounded-xl border border-line bg-surface p-4">
        <RegimeTable
          dataset={dataset}
          policies={DISPLAY_POLICIES}
          selectedKey={selectedKey}
          onSelect={select}
        />
      </div>

      {/* descriptive departure breakdown for the selected regime (renders only
          when the frozen data carries departure buckets) */}
      {selectedCell?.departures && (
        <div className="rounded-xl border border-line bg-surface p-4">
          <DeparturesPanel cell={selectedCell} policies={DISPLAY_POLICIES} />
        </div>
      )}

      <p className="text-[0.72rem] leading-relaxed text-faint">
        Each line is a deterministic, seed-averaged run of the closed-loop room simulator over a
        shared arrival stream (the A/B invariant); "FairPlay" is the liveness-aware arm. Throughput
        (total seat-hrs) structurally rewards concentration; vulnerable seat-hrs is the FairPlay
        cohort check. Numbers are illustrative until calibrated to real room traffic.
      </p>
    </div>
  )
}
