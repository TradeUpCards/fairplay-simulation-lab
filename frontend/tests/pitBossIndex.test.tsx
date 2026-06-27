// @vitest-environment happy-dom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { cleanup, render, screen, fireEvent, within } from '@testing-library/react'
import { PitBossIndexView } from '../src/views/PitBossIndex'
import { rankTables } from '../src/lib/health'
import { loadHealth } from '../src/data/shim'
import type { HealthScoresFile } from '../src/data/types'

afterEach(cleanup)

async function scores(): Promise<HealthScoresFile['health_scores']> {
  return (await loadHealth()).health_scores
}

describe('rankTables — healthiest-first, data-driven', () => {
  it('orders real health scores by descending health (T-7 best, T-22 worst)', async () => {
    const ranked = rankTables(await scores())
    const healths = ranked.map((r) => r.health)
    for (let i = 1; i < healths.length; i += 1) {
      expect(healths[i]).toBeLessThanOrEqual(healths[i - 1])
    }
    expect(ranked[0].table_id).toBe('T-7')
    expect(ranked[ranked.length - 1].table_id).toBe('T-22')
  })

  it('sorts by the data, not input order (not hard-coded)', () => {
    const a = [{ id: 'a', health: 50 }, { id: 'b', health: 90 }, { id: 'c', health: 70 }]
    expect(rankTables(a).map((x) => x.id)).toEqual(['b', 'c', 'a'])
    // Reversing the input yields the same ranked order.
    expect(rankTables([...a].reverse()).map((x) => x.id)).toEqual(['b', 'c', 'a'])
  })
})

describe('PitBossIndexView', () => {
  it('renders every table, ranked healthiest-first in the DOM', async () => {
    const { container } = render(<PitBossIndexView scores={await scores()} />)
    const ids = Array.from(container.querySelectorAll('[data-testid="pit-table-id"]')).map((el) => el.textContent)
    expect(ids).toHaveLength(12)
    expect(ids[0]).toBe('T-7')
    expect(ids[ids.length - 1]).toBe('T-22')
  })

  it('shows T-22 as 38 / beginner-unfriendly', async () => {
    render(<PitBossIndexView scores={await scores()} />)
    const row = screen.getByText('T-22').closest('[data-testid="pit-row"]') as HTMLElement
    expect(within(row).getByText('38')).toBeTruthy()
    expect(within(row).getByText('Beginner-unfriendly')).toBeTruthy()
  })

  it('flags ONLY the integrity_candidate table (T-11) for review', async () => {
    render(<PitBossIndexView scores={await scores()} />)
    const flags = screen.getAllByTestId('review-flag')
    expect(flags).toHaveLength(1)
    const flaggedRow = flags[0].closest('[data-testid="pit-row"]')
    expect(flaggedRow?.contains(screen.getByText('T-11'))).toBe(true)
  })

  it('renders reason_codes[0].detail verbatim', async () => {
    const data = await scores()
    render(<PitBossIndexView scores={data} />)
    const t22 = data.find((s) => s.table_id === 'T-22')!
    expect(screen.getByText(t22.reason_codes[0].detail)).toBeTruthy()
  })

  it('row click selects the table (wires to the future table view)', async () => {
    const onSelectTable = vi.fn()
    render(<PitBossIndexView scores={await scores()} onSelectTable={onSelectTable} />)
    fireEvent.click(screen.getByLabelText('open table T-7'))
    expect(onSelectTable).toHaveBeenCalledWith('T-7')
  })
})
