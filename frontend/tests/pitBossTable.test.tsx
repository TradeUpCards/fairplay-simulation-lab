// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { cleanup, render, screen, fireEvent, within } from '@testing-library/react'
import { PitBossTableView } from '../src/views/PitBossTable'
import { PitBossConsole } from '../src/views/PitBossConsole'
import {
  loadHealth,
  loadIntegrity,
  loadTableRoster,
  loadClassifications,
} from '../src/data/shim'
import {
  seatPositions,
  buildSeats,
  assessmentsForTable,
  classificationIndex,
} from '../src/lib/table'
import type { IntegrityAssessment } from '../src/data/types'

afterEach(cleanup)

async function bundle() {
  return {
    health: await loadHealth(),
    integrity: await loadIntegrity(),
    roster: await loadTableRoster(),
    classifications: await loadClassifications(),
  }
}

const tableEntry = async (id: string) =>
  (await loadTableRoster()).tables.find((t) => t.table_id === id)!

const counterDetail = (a: IntegrityAssessment) => a.counter_evidence[0]?.detail

describe('seat-ring + table helpers', () => {
  it('seatPositions returns one point per seat within the ring box', () => {
    const pos = seatPositions(6)
    expect(pos).toHaveLength(6)
    for (const p of pos) {
      expect(p.leftPct).toBeGreaterThanOrEqual(0)
      expect(p.leftPct).toBeLessThanOrEqual(100)
    }
  })

  it('assessmentsForTable surfaces CL-001 at T-11 and nothing at T-22', async () => {
    const { integrity } = await bundle()
    expect(assessmentsForTable(await tableEntry('T-11'), integrity.assessments).map((a) => a.group_id)).toEqual(['CL-001'])
    expect(assessmentsForTable(await tableEntry('T-22'), integrity.assessments)).toHaveLength(0)
  })

  it('buildSeats flags cluster members and leaves PTL null (pending U2)', async () => {
    const { integrity, classifications } = await bundle()
    const t11 = await tableEntry('T-11')
    const seats = buildSeats(
      t11,
      classificationIndex(classifications.classifications),
      assessmentsForTable(t11, integrity.assessments),
    )
    expect(seats).toHaveLength(t11.max_seats)
    const flagged = seats.filter((s) => s.flaggedGroupId).map((s) => s.playerId)
    expect(flagged).toEqual(['P-198', 'P-199'])
    expect(seats.every((s) => s.ptl === null)).toBe(true)
  })
})

describe('PitBossTableView — seat ring', () => {
  it('renders one seat per max seat with occupants and open seats', async () => {
    const b = await bundle()
    const { container } = render(<PitBossTableView tableId="T-11" {...b} />)
    expect(screen.getAllByTestId('seat')).toHaveLength(6)
    expect(screen.getByText('P-198')).toBeTruthy()
    expect(container.querySelectorAll('[data-open="true"]').length).toBe(2)
  })

  it('flags exactly the seated cluster members, PTL still pending', async () => {
    const b = await bundle()
    const { container } = render(<PitBossTableView tableId="T-11" {...b} />)
    expect(container.querySelectorAll('[data-flagged="true"]')).toHaveLength(2)
    expect(container.querySelectorAll('[data-ptl-tone="pending"]').length).toBe(4)
    expect(screen.getByTestId('ptl-legend').textContent).toMatch(/pending/i)
  })

  it('renders a centered brand watermark on the felt', async () => {
    const b = await bundle()
    render(<PitBossTableView tableId="T-11" {...b} />)
    expect(screen.getByTestId('table-watermark')).toBeTruthy()
  })
})

describe('PitBossTableView — integrity case', () => {
  it('T-11 folds in the high cluster case: 4 families, hold, uncertainty framing', async () => {
    const b = await bundle()
    render(<PitBossTableView tableId="T-11" {...b} />)
    const card = screen.getByLabelText('integrity case CL-001')
    expect(card.getAttribute('data-band')).toBe('high')
    expect(within(card).getByText('Signal families (4)')).toBeTruthy()
    expect(within(card).getByText(/Hold seat for pit-boss review/i)).toBeTruthy()
    expect(within(card).getByText(/Elevated for review/i)).toBeTruthy()
    // counter-evidence section always present (empty here → explicit message)
    expect(within(card).getByLabelText('counter-evidence')).toBeTruthy()
  })

  it('AE3: the household reads neutral with counter-evidence and monitors — not escalated', async () => {
    const b = await bundle()
    render(<PitBossTableView tableId="T-7" {...b} />)
    const card = screen.getByLabelText('integrity case H-01')
    expect(card.getAttribute('data-band')).toBe('neutral')
    const h01 = b.integrity.assessments.find((a) => a.group_id === 'H-01')!
    expect(within(card).getByText(counterDetail(h01)!)).toBeTruthy()
    expect(within(card).getByText(/Keep monitoring/i)).toBeTruthy()
    expect(within(card).getByText(/Monitor only — not escalated/i)).toBeTruthy()
  })

  it('guardrail: hedged (not accusatory), counter-evidence shown, no auto-enforcement', async () => {
    const b = await bundle()
    render(<PitBossTableView tableId="T-11" {...b} />)
    const card = screen.getByLabelText('integrity case CL-001')
    // R15: counter-evidence section is always present next to the finding.
    expect(within(card).getByLabelText('counter-evidence')).toBeTruthy()
    // R18: framing denies a factual accusation rather than asserting one.
    expect(within(card).getByText(/not a determination that anyone cheated/i)).toBeTruthy()
    // R18: the offered actions are human review per PRD §5 — never a ban / auto-enforcement.
    expect(within(card).queryByText(/\bban\b/i)).toBeNull()
    expect(within(card).getByText('Escalate to review')).toBeTruthy()
  })

  it('an unflagged table shows no integrity flags + its health vitals', async () => {
    const b = await bundle()
    render(<PitBossTableView tableId="T-22" {...b} />)
    expect(screen.queryByTestId('integrity-case')).toBeNull()
    expect(screen.getByTestId('no-flags')).toBeTruthy()
    expect(screen.getByText('38')).toBeTruthy()
    expect(screen.getByText('Beginner-unfriendly')).toBeTruthy()
  })

  it('operator action is a human confirm, logged, never auto-executed', async () => {
    const b = await bundle()
    render(<PitBossTableView tableId="T-11" {...b} />)
    const card = screen.getByLabelText('integrity case CL-001')
    fireEvent.click(within(card).getByText('Accept recommendation'))
    const decision = within(card).getByTestId('operator-decision')
    expect(decision.textContent).toMatch(/no automatic action taken/i)
  })
})

describe('PitBossConsole — index drives detail', () => {
  it('clicking a table row swaps the detail panel', async () => {
    render(<PitBossConsole />)
    // Defaults to T-11 (flagged cluster).
    expect(await screen.findByLabelText('integrity case CL-001')).toBeTruthy()
    fireEvent.click(await screen.findByLabelText('open table T-22'))
    expect(await screen.findByTestId('no-flags')).toBeTruthy()
  })
})
