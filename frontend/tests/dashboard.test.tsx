// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import type { RoomSweepFile, RoomTimeseriesFile, SweepCell, SweepDataset } from '../src/data/types'
import { DashboardView } from '../src/views/Dashboard'
import {
  advantage,
  cellKey,
  findTimeseriesCell,
  heatColor,
  interpAt,
  pickDefaultCell,
  toCsv,
} from '../src/lib/dashboard'

function cell(tables: number, rate: number, stdTotal: number, fpTotal: number): SweepCell {
  return {
    tables,
    active_tables: Math.round(tables * 0.7),
    rate,
    source_file: 'x.json',
    policies: ['standard', 'fairplay', 'fairplay_liveness'],
    seeds: [7, 42],
    means: {
      standard: { total_paid_seat_hours: stdTotal, vulnerable_paid_seat_hours: stdTotal / 5 },
      fairplay: { total_paid_seat_hours: fpTotal, vulnerable_paid_seat_hours: fpTotal / 5 },
      fairplay_liveness: {
        total_paid_seat_hours: fpTotal - 0.2,
        vulnerable_paid_seat_hours: fpTotal / 5,
      },
    },
    departures: {
      standard: {
        left_satisfied_count: 5,
        left_damaged_count: 100,
        couldnt_seat_count: 8,
        cohort_left_satisfied_count: 5,
        cohort_left_damaged_count: 100,
        cohort_couldnt_seat_count: 3,
      },
      fairplay_liveness: {
        left_satisfied_count: 7,
        left_damaged_count: 98,
        couldnt_seat_count: 9,
        cohort_left_satisfied_count: 7,
        cohort_left_damaged_count: 98,
        cohort_couldnt_seat_count: 4,
      },
    },
    runs: [
      {
        seed: 7,
        policy: 'standard',
        total_paid_seat_hours: stdTotal,
        vulnerable_paid_seat_hours: stdTotal / 5,
      },
      {
        seed: 7,
        policy: 'fairplay',
        total_paid_seat_hours: fpTotal,
        vulnerable_paid_seat_hours: fpTotal / 5,
      },
    ],
    stability: {
      fairplay: {
        total_paid_seat_hours: {
          wins: fpTotal > stdTotal ? 2 : 0,
          n: 2,
          deltas: { '7': fpTotal - stdTotal, '42': fpTotal - stdTotal },
          mean_delta: fpTotal - stdTotal,
        },
        vulnerable_paid_seat_hours: {
          wins: 1,
          n: 2,
          deltas: { '7': 0.1, '42': -0.1 },
          mean_delta: 0,
        },
      },
    },
  }
}

const DATASET: SweepDataset = {
  id: 'static-capacity',
  label: 'Static capacity sweep',
  kind: 'grid',
  config: { fixture: 'playsim-large-room', horizon_min: 480, formation_mode: 'forming' },
  seeds: [7, 42],
  policies: ['standard', 'fairplay', 'fairplay_liveness'],
  table_axis: [10, 20],
  rate_axis: [20, 40],
  metrics: [
    {
      key: 'total_paid_seat_hours',
      label: 'Total paid seat-hrs',
      unit: 'hrs',
      lower_is_better: false,
    },
    {
      key: 'vulnerable_paid_seat_hours',
      label: 'Vulnerable seat-hrs',
      unit: 'hrs',
      lower_is_better: false,
    },
    { key: 'final_active_tables', label: 'Final active tables', unit: 'n', lower_is_better: false },
  ],
  cells: [
    cell(10, 20, 10, 9), // FairPlay behind
    cell(10, 40, 10, 10.5),
    cell(20, 20, 10, 12),
    cell(20, 40, 10, 14), // biggest FairPlay advantage
  ],
}

const SWEEP: RoomSweepFile = { generated_at: '2026-06-27 12:00', datasets: [DATASET] }

const tsCell = (tables: number, rate: number) => ({
  tables,
  rate,
  t_min: [240, 480],
  t_hr: [4, 8],
  seeds: [7, 42],
  policies: {
    standard: {
      total_paid_seat_hours: [5, 10],
      vulnerable_paid_seat_hours: [1, 2],
      active_tables: [14, 13],
    },
    fairplay: {
      total_paid_seat_hours: [6, 14],
      vulnerable_paid_seat_hours: [1.5, 2.8],
      active_tables: [16, 15],
    },
    fairplay_liveness: {
      total_paid_seat_hours: [6, 13.8],
      vulnerable_paid_seat_hours: [1.4, 2.8],
      active_tables: [16, 16],
    },
  },
})

const TS: RoomTimeseriesFile = {
  generated_at: '2026-06-27 12:00',
  datasets: {
    'static-capacity': {
      label: 'Static capacity sweep',
      interval_min: 20,
      horizon_min: 480,
      cells: {
        '10|20.0': tsCell(10, 20),
        '10|40.0': tsCell(10, 40),
        '20|20.0': tsCell(20, 20),
        '20|40.0': tsCell(20, 40),
      },
    },
  },
}

describe('dashboard helpers', () => {
  it('advantage is FairPlay minus Standard on a metric', () => {
    expect(advantage(cell(20, 40, 10, 14), 'total_paid_seat_hours')).toBe(4)
    expect(advantage(cell(10, 20, 10, 9), 'total_paid_seat_hours')).toBe(-1)
  })

  it('pickDefaultCell selects the most FairPlay-favourable regime', () => {
    const best = pickDefaultCell(DATASET, 'total_paid_seat_hours')
    expect(best && cellKey(best)).toBe('20|40')
  })

  it('findTimeseriesCell matches by numeric identity, not string key', () => {
    // dataset cell rate is 40 (number); ts key is "20|40.0" — must still resolve.
    const found = findTimeseriesCell(TS.datasets['static-capacity'], 20, 40)
    expect(found?.tables).toBe(20)
    expect(found?.policies.fairplay.total_paid_seat_hours).toEqual([6, 14])
  })

  it('interpAt linearly interpolates a fractional index', () => {
    expect(interpAt([0, 10], 0.5)).toBe(5)
    expect(interpAt([0, 10, 30], 1.5)).toBe(20)
    expect(interpAt([4, 9], 5)).toBe(9) // clamps past the end
  })

  it('heatColor is green for FairPlay-ahead, red for behind', () => {
    expect(heatColor(2, 4)).toContain('95,176,121') // green
    expect(heatColor(-2, 4)).toContain('201,93,93') // red
  })

  it('toCsv emits a header and one row per run', () => {
    const csv = toCsv(DATASET)
    expect(csv.split('\n')[0]).toContain('tables,rate,policy,seed')
    expect(csv).toContain('fairplay')
  })
})

describe('DashboardView render', () => {
  beforeEach(() => {
    // freeze the replay clock so the RAF loop doesn't churn state during the test
    vi.stubGlobal('requestAnimationFrame', () => 0)
    vi.stubGlobal('cancelAnimationFrame', () => {})
    // jsdom has no layout, so stub the scroll-into-view used on cell select
    Element.prototype.scrollIntoView = vi.fn()
  })
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('renders title, caveat, and a multi-regime replay (Standard + FairPlay lines)', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    expect(screen.getByText(/Routing sweep/)).toBeTruthy()
    // the illustrative-data caveat still lives in the footer note
    expect(screen.getByText(/illustrative until calibrated/i)).toBeTruthy()
    expect(screen.getByText(/all regimes/)).toBeTruthy()
    expect(screen.getByTestId('replay-line-20|40|standard')).toBeTruthy()
    expect(screen.getByTestId('replay-line-20|40|fairplay_liveness')).toBeTruthy()
  })

  it('shows the liveness arm AS "FairPlay" and hides the plain route arm', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    // the liveness arm is surfaced as "FairPlay" (table rows, chart key)…
    expect(screen.getAllByText('FairPlay').length).toBeGreaterThan(0)
    // …never under the raw liveness/route names
    expect(screen.queryByText('FairPlay-liveness')).toBeNull()
    expect(screen.queryByText('FairPlay-route')).toBeNull()
  })

  it('switching the metric tab re-colours toward vulnerable seat-hrs', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    fireEvent.click(screen.getByRole('tab', { name: /Vulnerable seat-hrs/ }))
    expect(screen.getAllByText(/Vulnerable seat-hrs/).length).toBeGreaterThan(0)
  })

  it('toggling a key chip hides that line', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    expect(screen.getByTestId('replay-line-20|40|standard')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '20t · 40/hr Standard' }))
    expect(screen.queryByTestId('replay-line-20|40|standard')).toBeNull()
  })

  it('clicking a heatmap cell solos that regime and scrolls the chart into view', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    fireEvent.click(screen.getByTitle(/10 tables · 20\/hr/))
    expect(screen.getByTestId('replay-line-10|20|fairplay_liveness')).toBeTruthy()
    expect(screen.queryByTestId('replay-line-20|40|standard')).toBeNull()
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
  })

  it('shows the descriptive departures panel for the selected regime and follows selection', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    // defaults to the most FairPlay-favourable regime (20t · 40/hr)
    expect(screen.getByRole('heading', { name: /Where players left.*20t · 40\/hr/ })).toBeTruthy()
    // the three descriptive buckets are labelled (not a comparison metric)
    expect(screen.getByText('Left satisfied')).toBeTruthy()
    expect(screen.getByText('Left tilted / busted')).toBeTruthy()
    // selecting another regime re-points the panel
    fireEvent.click(screen.getByTitle(/10 tables · 20\/hr/))
    expect(screen.getByRole('heading', { name: /Where players left.*10t · 20\/hr/ })).toBeTruthy()
  })

  it('omits the departures panel when the data carries no departure buckets', () => {
    const noDepCell = cell(20, 40, 10, 14)
    delete noDepCell.departures
    const sweep: RoomSweepFile = {
      generated_at: '2026-06-27 12:00',
      datasets: [{ ...DATASET, cells: [noDepCell] }],
    }
    render(<DashboardView sweep={sweep} timeseries={TS} />)
    expect(screen.queryByText(/Where players left/)).toBeNull()
  })

  it('renders live standings that rank the visible lines by value', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    expect(screen.getByText(/Live standings/i)).toBeTruthy()
    const live = screen.getByTestId('standing-20|40|fairplay_liveness')
    const std = screen.getByTestId('standing-20|40|standard')
    // FairPlay's opening value leads Standard's → it holds the better (lower) rank
    expect(Number(live.getAttribute('data-rank'))).toBeLessThan(
      Number(std.getAttribute('data-rank')),
    )
  })

  it('reveals the winner banner only once the replay reaches the finish', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    expect(screen.getByTestId('winner-banner').getAttribute('data-shown')).toBe('false')
    // scrub to the end (N = tHr.length - 1 = 1)
    fireEvent.change(screen.getByLabelText('scrub replay'), { target: { value: '1' } })
    expect(screen.getByTestId('winner-banner').getAttribute('data-shown')).toBe('true')
  })

  it('dismisses the winner banner with the close button', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    fireEvent.change(screen.getByLabelText('scrub replay'), { target: { value: '1' } })
    expect(screen.getByTestId('winner-banner').getAttribute('data-shown')).toBe('true')
    fireEvent.click(screen.getByLabelText('dismiss winner banner'))
    expect(screen.getByTestId('winner-banner').getAttribute('data-shown')).toBe('false')
  })

  it('the leading-score readout matches the top standing at the finish', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    fireEvent.change(screen.getByLabelText('scrub replay'), { target: { value: '1' } })
    // FairPlay's final sample (13.8) leads → score rounds to "14"
    expect(screen.getByTestId('replay-score').textContent).toContain('14')
    const leaderRow = screen
      .getAllByTestId(/^standing-/)
      .find((r) => r.getAttribute('data-rank') === '0')
    expect(leaderRow?.textContent).toContain('14')
  })

  it('toggles every FairPlay line at once with the policy control', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    expect(screen.getByTestId('replay-line-20|40|fairplay_liveness')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('toggle all FairPlay lines'))
    // all FairPlay regimes drop out…
    expect(screen.queryByTestId('replay-line-20|40|fairplay_liveness')).toBeNull()
    expect(screen.queryByTestId('replay-line-10|20|fairplay_liveness')).toBeNull()
    // …while Standard lines stay
    expect(screen.getByTestId('replay-line-20|40|standard')).toBeTruthy()
    // clicking again brings them back
    fireEvent.click(screen.getByLabelText('toggle all FairPlay lines'))
    expect(screen.getByTestId('replay-line-20|40|fairplay_liveness')).toBeTruthy()
  })

  it('does not autoplay — a center button starts the simulation', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    const run = screen.getByRole('button', { name: /run the 8-hour simulation/i })
    expect(run).toBeTruthy()
    fireEvent.click(run)
    // once running, the center run button disappears
    expect(screen.queryByRole('button', { name: /run the 8-hour simulation/i })).toBeNull()
  })

  it('toggles the race-sound mute control', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    fireEvent.click(screen.getByLabelText('mute race sounds'))
    expect(screen.getByLabelText('unmute race sounds')).toBeTruthy()
  })
})
