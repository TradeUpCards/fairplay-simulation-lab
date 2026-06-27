// @vitest-environment happy-dom
import { describe, it, expect, afterEach } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { EvalPanelView } from '../src/views/EvalPanel'
import { loadSeededCases, loadHealth, loadIntegrity } from '../src/data/shim'
import { resolvePredicted, satisfiesExpected, splitByRisk } from '../src/lib/evals'
import type { SeededCase } from '../src/data/types'

afterEach(cleanup)

async function bundle() {
  return {
    labels: await loadSeededCases(),
    health: await loadHealth(),
    integrity: await loadIntegrity(),
  }
}

const caseById = (cases: SeededCase[], id: string): SeededCase =>
  cases.find((c) => c.case_id === id)!

describe('eval logic', () => {
  it('resolves each demo case to its computed band', async () => {
    const { labels, health, integrity } = await bundle()
    const p = (id: string) => resolvePredicted(caseById(labels.cases, id), health, integrity).band
    expect(p('CASE-A')).toBe('beginner_unfriendly') // T-22 health band
    expect(p('CASE-C')).toBe('high') // CL-001 cluster
    expect(p('CASE-E')).toBe('neutral') // H-01 household — not escalated
  })

  it('judges computed bands against expected categories', () => {
    expect(satisfiesExpected('integrity_review', 'high')).toBe(true)
    expect(satisfiesExpected('monitor_low', 'neutral')).toBe(true)
    expect(satisfiesExpected('beginner_unfriendly', 'beginner_unfriendly')).toBe(true)
    expect(satisfiesExpected('integrity_review', 'neutral')).toBe(false)
    expect(satisfiesExpected('integrity_review', null)).toBe(false)
  })

  it('splits true-risk cases from traps', async () => {
    const { labels } = await bundle()
    const { trueRisk, traps } = splitByRisk(labels.cases, labels.eval_summary)
    expect(trueRisk.map((c) => c.case_id)).toEqual(['CASE-A', 'CASE-C', 'CASE-F', 'CASE-G'])
    expect(traps.map((c) => c.case_id)).toEqual(['CASE-B', 'CASE-D', 'CASE-E'])
  })
})

describe('EvalPanelView', () => {
  it('renders all 7 expected case labels', async () => {
    render(<EvalPanelView bundle={await bundle()} />)
    for (const id of ['CASE-A', 'CASE-B', 'CASE-C', 'CASE-D', 'CASE-E', 'CASE-F', 'CASE-G']) {
      expect(screen.getByText(id)).toBeTruthy()
    }
    expect(screen.getAllByTestId('eval-case')).toHaveLength(7)
  })

  it('shows predicted + checks only for the 3 mandatory demo cases (A/C/E)', async () => {
    render(<EvalPanelView bundle={await bundle()} />)
    expect(screen.getAllByTestId('predicted-band')).toHaveLength(3)
  })

  it('CASE-C computes high and CASE-E computes neutral', async () => {
    render(<EvalPanelView bundle={await bundle()} />)
    const cardC = screen.getByText('CASE-C').closest('[data-testid="eval-case"]') as HTMLElement
    const cardE = screen.getByText('CASE-E').closest('[data-testid="eval-case"]') as HTMLElement
    expect(within(cardC).getByTestId('predicted-band').textContent).toBe('high')
    expect(within(cardE).getByTestId('predicted-band').textContent).toBe('neutral')
  })

  it('renders each mandatory case’s safety checks from data (CASE-C has 6)', async () => {
    const { labels } = await bundle()
    render(<EvalPanelView bundle={await bundle()} />)
    const cardC = screen.getByText('CASE-C').closest('[data-testid="eval-case"]') as HTMLElement
    expect(within(cardC).getAllByTestId('eval-check')).toHaveLength(
      caseById(labels.cases, 'CASE-C').eval_checks.length,
    )
  })

  it('ranks true-risk CASE-C above trap CASE-E, with a visible separator', async () => {
    render(<EvalPanelView bundle={await bundle()} />)
    expect(screen.getByTestId('risk-separator')).toBeTruthy()
    const cardC = screen.getByText('CASE-C').closest('[data-testid="eval-case"]') as HTMLElement
    const cardE = screen.getByText('CASE-E').closest('[data-testid="eval-case"]') as HTMLElement
    // E follows C in document order → C is ranked above E.
    expect(cardC.compareDocumentPosition(cardE) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('marks non-mandatory cases expected-only', async () => {
    render(<EvalPanelView bundle={await bundle()} />)
    const cardB = screen.getByText('CASE-B').closest('[data-testid="eval-case"]') as HTMLElement
    expect(within(cardB).getByText(/Expected-only/i)).toBeTruthy()
  })
})
