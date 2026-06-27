// @vitest-environment happy-dom
import { describe, it, expect, afterEach } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import { PlayerLobbyView } from '../src/views/PlayerLobby'
import { loadRouterLobby } from '../src/data/shim'
import type { LobbyTable } from '../src/data/types'

afterEach(cleanup)

/**
 * Operator language / fields that must NEVER reach a player screen
 * (CLAUDE.md hard rule #3, R17). Numeric *facts* like stakes "1/2" and seat
 * counts are fine — what's banned are scores, classifications, and integrity
 * language, which is what these lists target.
 */
const FORBIDDEN_TERMS = [
  'predator', 'collusion', 'cluster', 'integrity', 'archetype',
  'seating_risk', 'health score', 'risk score',
]
const FORBIDDEN_KEYS = [
  'health', 'rank', 'seating_risk', 'archetype', 'integrity_gated',
  'fit', 'delta_health', 'health_band', 'reason_codes', 'band', 'convergence_count',
]

/** Compile-time guardrail: only a LobbyTable may be handed to lobby code. */
function acceptsLobbyTable(_table: LobbyTable): void {}

describe('player lobby guardrail — the player/operator wall (R17 / AE2)', () => {
  it('compile-time: an operator row is NOT assignable to lobby code', async () => {
    const file = await loadRouterLobby()
    const safe = file.routed[0].player_lobby[0]
    acceptsLobbyTable(safe) // ✅ player-safe row is fine

    const operatorRow = file.routed[0].operator_view[0]
    // @ts-expect-error operator rows carry scores + the OperatorOnly brand — not a LobbyTable.
    acceptsLobbyTable(operatorRow)

    // Keep a runtime assertion so the test is meaningful, not just a type probe.
    expect(operatorRow).toBeDefined()
  })

  it('runtime: rendered lobby exposes no scores, classifications, or integrity language', async () => {
    const file = await loadRouterLobby()
    render(<PlayerLobbyView data={file} />)
    const text = (document.body.textContent ?? '').toLowerCase()
    for (const term of FORBIDDEN_TERMS) {
      expect(text).not.toContain(term)
    }
  })

  it('runtime: every player_lobby row is structurally free of operator-only keys', async () => {
    const file = await loadRouterLobby()
    for (const routed of file.routed) {
      for (const table of routed.player_lobby) {
        for (const key of FORBIDDEN_KEYS) {
          expect(Object.prototype.hasOwnProperty.call(table, key)).toBe(false)
        }
      }
    }
  })

  it('the flagged table T-11 never appears in the P-104 lobby', async () => {
    const file = await loadRouterLobby()
    const p104 = file.routed.find((r) => r.player_id === 'P-104')
    expect(p104).toBeDefined()
    expect(p104!.player_lobby.some((t) => t.table_id === 'T-11')).toBe(false)
  })
})
