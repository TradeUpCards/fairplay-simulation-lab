// @vitest-environment happy-dom
import { describe, it, expect, afterEach } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { Simulator, SimulatorView } from '../src/views/Simulator'
import { loadRoomMetrics } from '../src/data/shim'
import { simStore } from '../src/state/simStore'
import { projectMetric, integrityOutcome, displayHour } from '../src/lib/simulator'
import type { RoomMetricsFile } from '../src/data/types'

afterEach(() => {
  cleanup()
  simStore.reset()
})

async function bothPaths(): Promise<{ standard: RoomMetricsFile; fairplay: RoomMetricsFile }> {
  return { standard: await loadRoomMetrics('standard'), fairplay: await loadRoomMetrics('fairplay') }
}

const PAID = 'cumulative_paid_seat_time_minutes'

describe('simulator math (origin AE1 hinges on the endpoints)', () => {
  it('projectMetric is Standard at 0% and FairPlay at 100%', () => {
    expect(projectMetric(100, 200, 0)).toBe(100)
    expect(projectMetric(100, 200, 100)).toBe(200)
    expect(projectMetric(100, 200, 50)).toBe(150)
  })

  it('integrityOutcome flips cluster→held across the lever', () => {
    expect(integrityOutcome(0)).toBe('cluster_forms')
    expect(integrityOutcome(100)).toBe('seat_held')
    expect(integrityOutcome(50)).toBe('seat_held')
  })

  it('displayHour clamps the clock to the 1..8 series window', () => {
    expect(displayHour(0)).toBe(1)
    expect(displayHour(99)).toBe(8)
    expect(displayHour(3)).toBe(3)
  })
})

describe('SimulatorView — Standard vs FairPlay frame', () => {
  it('renders KPI cards for both paths and they diverge by hour 8', async () => {
    const { standard, fairplay } = await bothPaths()
    render(<SimulatorView standard={standard} fairplay={fairplay} hour={8} adherence={0} />)
    const std = screen.getByTestId(`std-${PAID}`).textContent
    const fp = screen.getByTestId(`fp-${PAID}`).textContent
    expect(std).toBeTruthy()
    expect(fp).toBeTruthy()
    expect(std).not.toBe(fp) // FairPlay grows paid seat-time vs Standard
  })

  it('divergence chart plots all 8 hours for both paths', async () => {
    const { standard, fairplay } = await bothPaths()
    render(<SimulatorView standard={standard} fairplay={fairplay} hour={1} adherence={0} />)
    expect(screen.getAllByTestId('hour-tick')).toHaveLength(8)
    expect(screen.getByTestId('line-standard').getAttribute('points')).toBeTruthy()
    expect(screen.getByTestId('line-fairplay').getAttribute('points')).toBeTruthy()
  })

  it('AE1: lever 0% → Standard KPIs + cluster forms', async () => {
    const { standard, fairplay } = await bothPaths()
    render(<SimulatorView standard={standard} fairplay={fairplay} hour={8} adherence={0} />)
    // Projected column equals Standard at 0% adherence.
    expect(screen.getByTestId(`proj-${PAID}`).textContent).toBe(screen.getByTestId(`std-${PAID}`).textContent)
    expect(screen.getByText(/Cluster forms/i)).toBeTruthy()
  })

  it('AE1: lever 100% → FairPlay KPIs + seat held', async () => {
    const { standard, fairplay } = await bothPaths()
    render(<SimulatorView standard={standard} fairplay={fairplay} hour={8} adherence={100} />)
    expect(screen.getByTestId(`proj-${PAID}`).textContent).toBe(screen.getByTestId(`fp-${PAID}`).textContent)
    expect(screen.getByText(/Seat held/i)).toBeTruthy()
  })

  it('scrubbing the clock changes the displayed hour snapshot', async () => {
    const { standard, fairplay } = await bothPaths()
    const { rerender } = render(
      <SimulatorView standard={standard} fairplay={fairplay} hour={3} adherence={0} />,
    )
    const atH3 = screen.getByTestId(`std-${PAID}`).textContent
    rerender(<SimulatorView standard={standard} fairplay={fairplay} hour={7} adherence={0} />)
    const atH7 = screen.getByTestId(`std-${PAID}`).textContent
    expect(atH3).not.toBe(atH7)
  })
})

describe('Simulator — store-wired clock (R2)', () => {
  it('moving the hour control re-renders the frame from the store', async () => {
    render(<Simulator />)
    await screen.findByText(/New-player retention/i)
    const before = screen.getByTestId(`std-${PAID}`).textContent

    fireEvent.change(screen.getByLabelText('sim hour'), { target: { value: '5' } })

    expect(simStore.getState().hour).toBe(5)
    expect(screen.getByTestId(`std-${PAID}`).textContent).not.toBe(before)
  })
})
