import { useSyncExternalStore } from 'react'
import type { RoomMetricsFile } from '../data/types'
import { loadRoomMetrics } from '../data/shim'
import { simStore } from '../state/simStore'
import { useResource } from '../state/useResource'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { KpiComparison } from '../components/KpiComparison'
import { DivergenceChart } from '../components/DivergenceChart'
import { integrityOutcome, OUTCOME_LABEL, displayHour } from '../lib/simulator'

interface BothPaths {
  standard: RoomMetricsFile
  fairplay: RoomMetricsFile
}

const loadBothPaths = async (): Promise<BothPaths> => ({
  standard: await loadRoomMetrics('standard'),
  fairplay: await loadRoomMetrics('fairplay'),
})

function useSim() {
  return useSyncExternalStore(simStore.subscribe, simStore.getState, simStore.getState)
}

/**
 * Standard-vs-FairPlay comparison frame. The shared sim-store drives both the
 * clock (R2) and the adherence lever (R3); the two frozen `room_metrics_*`
 * series supply the KPIs and the 8-hour divergence (R1/R4). The lever also flips
 * the integrity outcome — cluster forms vs. seat held (R5).
 */
export function Simulator() {
  const sim = useSim()
  const metrics = useResource(loadBothPaths, (d) => d.standard.hours.length === 0)
  const h = displayHour(sim.hour)

  return (
    <section aria-label="standard vs fairplay simulator">
      <header>
        <h2 className="m-0 mb-3 text-[1.15rem]">Standard vs FairPlay — 8-hour room</h2>
      </header>

      <div className="mb-4 flex flex-wrap gap-6 text-[0.85rem] text-muted">
        <label className="flex flex-col gap-[0.3rem]">
          Hour {h}
          <input
            type="range"
            min={1}
            max={8}
            value={h}
            aria-label="sim hour"
            onChange={(e) => simStore.setHour(Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col gap-[0.3rem]">
          FairPlay adherence {sim.adherence}%
          <input
            type="range"
            min={0}
            max={100}
            step={25}
            value={sim.adherence}
            aria-label="fairplay adherence"
            onChange={(e) => simStore.setAdherence(Number(e.target.value))}
          />
        </label>
      </div>

      <ResourceBoundary state={metrics} label="room metrics">
        {(d) => (
          <SimulatorView standard={d.standard} fairplay={d.fairplay} hour={sim.hour} adherence={sim.adherence} />
        )}
      </ResourceBoundary>
    </section>
  )
}

/** Pure render from resolved data + sim values — what the unit tests drive. */
export function SimulatorView({
  standard,
  fairplay,
  hour,
  adherence,
}: {
  standard: RoomMetricsFile
  fairplay: RoomMetricsFile
  hour: number
  adherence: number
}) {
  const h = displayHour(hour)
  const stdRow = standard.hours[h - 1]
  const fpRow = fairplay.hours[h - 1]
  const outcome = integrityOutcome(adherence)
  const isBlended = adherence !== 0 && adherence !== 100

  return (
    <div className="grid gap-5">
      <DivergenceChart
        standard={standard}
        fairplay={fairplay}
        metricKey="cumulative_paid_seat_time_minutes"
        metricLabel="Paid seat-time"
        currentHour={h}
      />

      <KpiComparison standardRow={stdRow} fairplayRow={fpRow} adherence={adherence} />

      <aside className="rounded-lg border border-line bg-surface px-[0.9rem] py-3" aria-label="integrity outcome">
        <h3 className="m-0 mb-[0.3rem] text-[0.95rem]">Integrity outcome{isBlended ? ' (illustrative)' : ''}</h3>
        <p className={`m-0 font-semibold ${outcome === 'cluster_forms' ? 'text-[#ff9b9b]' : 'text-[#8be3a7]'}`}>
          {OUTCOME_LABEL[outcome]}
        </p>
        <p className="m-0 mt-[0.4rem] text-[0.8rem] text-muted">
          High-risk formations (h{h}): Standard {stdRow.high_risk_seating_formations} · FairPlay{' '}
          {fpRow.high_risk_seating_formations}
        </p>
      </aside>

      <div className="grid gap-[0.3rem] text-[0.8rem] text-[#9aa2b3]">
        <p>
          <strong className="text-[#c3c9d6]">Standard · h{h}:</strong> {stdRow.hour_note}
        </p>
        <p>
          <strong className="text-[#c3c9d6]">FairPlay · h{h}:</strong> {fpRow.hour_note}
        </p>
      </div>
    </div>
  )
}
