// @vitest-environment happy-dom
import { describe, it, expect, afterEach } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import { PlayerLobbyView } from '../src/views/PlayerLobby'
import { LobbySidecar } from '../src/components/LobbySidecar'
import { loadRouterLobby } from '../src/data/shim'
import type { LobbyTable, OperatorTableDetail } from '../src/data/types'

/** An operator detail whose archetypes embed forbidden terms (predator/cluster). */
const SAMPLE_DETAIL: OperatorTableDetail = {
  table_id: 'T-22',
  stakes: '$1/$2',
  seated_count: 4,
  max_seats: 6,
  open_seats: 2,
  full: false,
  composition: [
    { archetype: 'aggressive_predatory', count: 1 },
    { archetype: 'cluster_member', count: 1 },
    { archetype: 'recreational', count: 2 },
  ],
  health: 58,
  band: 'medium',
  terms: { P_pred: 20, P_frag: 10, P_clus: 8, P_bleed: 5 },
  reasons: [{ code: 'predation_pressure', detail: 'skill-weighted aggressor load' }],
  rank: 3,
  badge: 'available',
  fit: 0.5,
  delta_health: -4,
  seating_risk: 'medium',
}

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

describe('lobby sidecar — player view never leaks archetype (the curtain wall)', () => {
  it('player view: seats render handles but no archetype text or attribute', () => {
    render(<LobbySidecar detail={SAMPLE_DETAIL} onClose={() => {}} pitboss={false} onPitbossChange={() => {}} />)
    // Seats rendered (so the assertion below is meaningful, not vacuous).
    expect(document.querySelectorAll('[data-testid="seat-row"]').length).toBeGreaterThan(0)
    // No seat carries an archetype attribute in the player view.
    expect(document.querySelectorAll('[data-archetype]').length).toBe(0)
    // No operator/integrity language leaks into the player-view text.
    const text = (document.body.textContent ?? '').toLowerCase()
    for (const term of FORBIDDEN_TERMS) {
      expect(text).not.toContain(term)
    }
  })

  it('pit-boss view DOES reveal archetype (proves the player-view test discriminates)', () => {
    render(<LobbySidecar detail={SAMPLE_DETAIL} onClose={() => {}} pitboss={true} onPitbossChange={() => {}} />)
    expect(document.querySelectorAll('[data-archetype]').length).toBeGreaterThan(0)
    const text = (document.body.textContent ?? '').toLowerCase()
    // The archetype names embed forbidden substrings — expected on the operator side.
    expect(text).toContain('predator')
    expect(text).toContain('cluster')
  })
})
