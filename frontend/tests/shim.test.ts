import { describe, it, expect } from 'vitest'
import {
  loadClassifications,
  loadIntegrity,
  loadHealth,
  loadSeating,
  loadRouterLobby,
  loadRoomMetrics,
  safeLoad,
} from '../src/data/shim'

describe('data shim — frozen Contract-2 loaders', () => {
  it('loads table health typed to HealthScoresFile', async () => {
    const f = await loadHealth()
    expect(Array.isArray(f.health_scores)).toBe(true)
    expect(f.health_scores.length).toBeGreaterThan(0)
    expect(f.meta.contract).toBeTruthy()
    expect(typeof f.health_scores[0].health).toBe('number')
    expect(f.health_scores[0].table_id).toBeTruthy()
  })

  it('loads router lobby with both operator_view and player_lobby', async () => {
    const f = await loadRouterLobby()
    expect(f.routed.length).toBeGreaterThan(0)
    const r = f.routed[0]
    expect(Array.isArray(r.player_lobby)).toBe(true)
    expect(Array.isArray(r.operator_view)).toBe(true)
    // player_lobby rows carry the neutral badge label only — no scores.
    expect(r.player_lobby[0]).toHaveProperty('badge_label')
    expect(r.player_lobby[0]).not.toHaveProperty('health')
  })

  it('loads classifications, integrity and seating', async () => {
    expect((await loadClassifications()).classifications.length).toBeGreaterThan(0)
    expect((await loadIntegrity()).assessments.length).toBeGreaterThan(0)
    expect((await loadSeating()).seeking_players.length).toBeGreaterThan(0)
  })

  it('loadRoomMetrics returns the 8-hour series for each path', async () => {
    const std = await loadRoomMetrics('standard')
    const fp = await loadRoomMetrics('fairplay')
    expect(std.hours).toHaveLength(8)
    expect(fp.hours).toHaveLength(8)
    expect(std.meta.path).toBe('standard')
    expect(fp.meta.path).toBe('fairplay')
  })
})

describe('safeLoad — graceful degradation (origin AE5)', () => {
  it('wraps a resolved loader as ok', async () => {
    const s = await safeLoad(async () => ({ n: 1 }))
    expect(s).toEqual({ status: 'ok', data: { n: 1 } })
  })

  it('returns error (never throws) when the loader rejects', async () => {
    const s = await safeLoad(async () => {
      throw new Error('source down')
    })
    expect(s.status).toBe('error')
    if (s.status === 'error') expect(s.error.message).toBe('source down')
  })

  it('returns empty when isEmpty matches', async () => {
    const s = await safeLoad(async () => [] as number[], (d) => d.length === 0)
    expect(s.status).toBe('empty')
  })

  it('treats null data as error rather than ok', async () => {
    const s = await safeLoad(async () => null)
    expect(s.status).toBe('error')
  })

  it('every real loader resolves through safeLoad without throwing', async () => {
    const s = await safeLoad(loadHealth, (d) => d.health_scores.length === 0)
    expect(s.status).toBe('ok')
  })
})
