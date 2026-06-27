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
      fairplay_liveness: { total_paid_seat_hours: fpTotal - 0.2, vulnerable_paid_seat_hours: fpTotal / 5 },
    },
    runs: [
      { seed: 7, policy: 'standard', total_paid_seat_hours: stdTotal, vulnerable_paid_seat_hours: stdTotal / 5 },
      { seed: 7, policy: 'fairplay', total_paid_seat_hours: fpTotal, vulnerable_paid_seat_hours: fpTotal / 5 },
    ],
    stability: {
      fairplay: {
        total_paid_seat_hours: { wins: fpTotal > stdTotal ? 2 : 0, n: 2, deltas: { '7': fpTotal - stdTotal, '42': fpTotal - stdTotal }, mean_delta: fpTotal - stdTotal },
        vulnerable_paid_seat_hours: { wins: 1, n: 2, deltas: { '7': 0.1, '42': -0.1 }, mean_delta: 0 },
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
    { key: 'total_paid_seat_hours', label: 'Total paid seat-hrs', unit: 'hrs', lower_is_better: false },
    { key: 'vulnerable_paid_seat_hours', label: 'Vulnerable seat-hrs', unit: 'hrs', lower_is_better: false },
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

const TS: RoomTimeseriesFile = {
  generated_at: '2026-06-27 12:00',
  datasets: {
    'static-capacity': {
      label: 'Static capacity sweep',
      interval_min: 20,
      horizon_min: 480,
      cells: {
        '20|40.0': {
          tables: 20,
          rate: 40,
          t_min: [240, 480],
          t_hr: [4, 8],
          seeds: [7, 42],
          policies: {
            standard: { total_paid_seat_hours: [5, 10], vulnerable_paid_seat_hours: [1, 2], active_tables: [14, 13] },
            fairplay: { total_paid_seat_hours: [6, 14], vulnerable_paid_seat_hours: [1.5, 2.8], active_tables: [16, 15] },
            fairplay_liveness: { total_paid_seat_hours: [6, 13.8], vulnerable_paid_seat_hours: [1.4, 2.8], active_tables: [16, 16] },
          },
        },
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

  it('renders the title, caveat, and the default (most-favourable) regime in the hero', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    expect(screen.getByText(/Routing sweep/)).toBeTruthy()
    expect(screen.getByText(/Illustrative synthetic data/)).toBeTruthy()
    // default cell is 20 tables / 40 joins/hr (max advantage) → shown in the hero header
    expect(screen.getByText(/20 tables · 40 joins\/hr/)).toBeTruthy()
    // all three policy lines are present in the replay
    expect(screen.getByTestId('replay-line-standard')).toBeTruthy()
    expect(screen.getByTestId('replay-line-fairplay')).toBeTruthy()
  })

  it('switching the metric tab re-colours toward vulnerable seat-hrs', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    fireEvent.click(screen.getByRole('tab', { name: /Vulnerable seat-hrs/ }))
    // heatmap caption reflects the active metric
    expect(screen.getAllByText(/Vulnerable seat-hrs/).length).toBeGreaterThan(0)
  })

  it('toggling the compare policy rescopes the advantage to FairPlay-liveness', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    expect(screen.getByText(/^FairPlay-ahead cells$/)).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'FairPlay-liveness' }))
    // stat strip + heatmap now compare the liveness arm vs Standard
    expect(screen.getByText(/^FairPlay-liveness-ahead cells$/)).toBeTruthy()
  })

  it('clicking a heatmap cell re-binds the hero and scrolls it into view', () => {
    render(<DashboardView sweep={SWEEP} timeseries={TS} />)
    // default hero is the max-advantage cell (20t/40hr); pick a different one.
    fireEvent.click(screen.getByTitle(/10 tables · 20\/hr/))
    expect(screen.getByText(/10 tables · 20 joins\/hr/)).toBeTruthy()
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
  })
})
