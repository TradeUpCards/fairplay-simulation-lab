// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { cleanup, render, screen, fireEvent, within } from '@testing-library/react'
import { PlayerLobbyView } from '../src/views/PlayerLobby'
import { loadRouterLobby } from '../src/data/shim'
import type { LobbyTable, RouterLobbyFile, RouterPolicy } from '../src/data/types'

afterEach(cleanup)

function badgeWithin(tableId: string): HTMLElement {
  const card = screen.getByText(tableId).closest('[data-testid="lobby-card"]')
  expect(card).not.toBeNull()
  return card as HTMLElement
}

describe('PlayerLobby — personalized, score-free (origin AE2)', () => {
  it('renders P-104 with the AE2 badges and hides the gated table', async () => {
    const file = await loadRouterLobby()
    render(<PlayerLobbyView data={file} />)

    expect(within(badgeWithin('T-8')).queryByText('Recommended for you')).not.toBeNull()
    expect(within(badgeWithin('T-14')).queryByText('Good fit')).not.toBeNull()
    expect(within(badgeWithin('T-22')).queryByText('Available')).not.toBeNull()

    // T-11 is under integrity review — gated out of the lobby entirely.
    expect(screen.queryByText('T-11')).toBeNull()
  })

  it('shows neutral table facts (stakes, seats, pace) for each card', async () => {
    const file = await loadRouterLobby()
    render(<PlayerLobbyView data={file} />)
    const card = badgeWithin('T-8')
    expect(within(card).queryByText('Stakes')).not.toBeNull()
    expect(within(card).queryByText('Pace')).not.toBeNull()
  })

  it('switching the selected player swaps the routed lobby', () => {
    const fixture = makeFixture()
    render(<PlayerLobbyView data={fixture} initialPlayerId="P-AAA" />)

    expect(screen.queryByText('T-100')).not.toBeNull()
    expect(screen.queryByText('T-200')).toBeNull()

    fireEvent.change(screen.getByLabelText('select player'), { target: { value: 'P-BBB' } })

    expect(screen.queryByText('T-200')).not.toBeNull()
    expect(screen.queryByText('T-100')).toBeNull()
  })

  it('falls back to the first routed player when the default is absent', () => {
    const fixture = makeFixture()
    render(<PlayerLobbyView data={fixture} initialPlayerId="P-NOPE" />)
    // P-AAA is first → its table shows.
    expect(screen.queryByText('T-100')).not.toBeNull()
  })
})

// ── test fixtures ────────────────────────────────────────────────────────────

const POLICY: RouterPolicy = {
  w_fit: 0.5,
  w_health: 0.3,
  w_delta: 0.2,
  rec_rank_min: 80,
  goodfit_rank_min: 60,
}

const card = (
  table_id: string,
  badge: LobbyTable['badge'],
  badge_label: LobbyTable['badge_label'],
): LobbyTable => ({
  table_id,
  stakes: '1/2',
  game_type: "NL Hold'em",
  max_seats: 9,
  seated_count: 5,
  open_seats: 4,
  pace_label: 'moderate',
  badge,
  badge_label,
})

function makeFixture(): RouterLobbyFile {
  return {
    meta: { schema_version: '1', contract: 'Contract 2', score: 'router' },
    routed: [
      {
        player_id: 'P-AAA',
        policy: POLICY,
        operator_view: [],
        player_lobby: [card('T-100', 'recommended', 'Recommended for you')],
      },
      {
        player_id: 'P-BBB',
        policy: POLICY,
        operator_view: [],
        player_lobby: [card('T-200', 'available', 'Available')],
      },
    ],
  }
}
