import { describe, it, expect } from 'vitest'
import { computePtl, tablePressure, ptlForTable, ARCHETYPE_VOLATILITY } from '../src/lib/ptl'
import { ptlTone, classificationIndex } from '../src/lib/table'
import { loadHealth, loadClassifications, loadTableRoster } from '../src/data/shim'
import type { HealthScore } from '../src/data/types'

/**
 * PTL is derived UI-side (P3 declined to champion it, 2026-06-22). These pin the
 * direction contract to REAL shipped entities — the validator the coordination
 * doc settled on (`docs/p1-to-p3-ptl-and-perhour-health.md` Q2): P-104 (new)
 * runs hot at the predatory table, cool at the balanced one; everyone seated by
 * design stays cool. The stale plan IDs (P-150/P-CA) don't exist in the data.
 */
const tableArg = (row: HealthScore) => ({
  table_id: row.table_id,
  band: row.band,
  terms: row.terms,
})

async function tables() {
  const health = await loadHealth()
  const byId = (id: string) => health.health_scores.find((h) => h.table_id === id)!
  return { t22: byId('T-22'), t8: byId('T-8'), t11: byId('T-11') }
}

describe('PTL — table pressure (Layer 2)', () => {
  it('rises with predation + fragility: predatory ≫ healthy table', async () => {
    const { t22, t8, t11 } = await tables()
    expect(tablePressure(t22.terms)).toBeGreaterThan(tablePressure(t11.terms))
    expect(tablePressure(t11.terms)).toBeGreaterThan(tablePressure(t8.terms))
    expect(tablePressure(t8.terms)).toBeLessThan(0.2) // healthy → almost no pressure
  })
})

describe('PTL — P-104 validator (the demo direction contract)', () => {
  it('new player runs HOT at predatory T-22, COOL at balanced T-8', async () => {
    const { t22, t8 } = await tables()
    const hot = computePtl('new', tableArg(t22))
    const cool = computePtl('new', tableArg(t8))

    expect(ptlTone(hot.ptl)).toBe('hot')
    expect(hot.ptl).toBeGreaterThanOrEqual(0.7)
    expect(ptlTone(cool.ptl)).toBe('cool')
    expect(cool.ptl).toBeLessThan(0.4)
    expect(hot.ptl).toBeGreaterThan(cool.ptl) // same player, table makes the difference
  })
})

describe('PTL — archetype gate (Layer 1 direction)', () => {
  it('vulnerable archetypes carry the signal; anchored ones sit cool', () => {
    expect(ARCHETYPE_VOLATILITY.new).toBeGreaterThan(ARCHETYPE_VOLATILITY.regular)
    expect(ARCHETYPE_VOLATILITY.recreational).toBeGreaterThan(ARCHETYPE_VOLATILITY.grinder)
    for (const a of ['grinder', 'aggressive_predatory', 'cluster_member', 'healthy_anchor'] as const) {
      expect(ARCHETYPE_VOLATILITY[a]).toBeLessThanOrEqual(0.15)
    }
  })

  it('at the SAME predatory table, a fish is hot but predators/clusters stay cool', async () => {
    const { t22 } = await tables()
    expect(ptlTone(computePtl('recreational', tableArg(t22)).ptl)).not.toBe('cool')
    expect(ptlTone(computePtl('aggressive_predatory', tableArg(t22)).ptl)).toBe('cool')
    expect(ptlTone(computePtl('cluster_member', tableArg(t22)).ptl)).toBe('cool')
  })

  it('edge: a fish at a HEALTHY table is cool — heat needs table pressure too', async () => {
    const { t8 } = await tables()
    expect(ptlTone(computePtl('recreational', tableArg(t8)).ptl)).toBe('cool')
  })
})

describe('PTL — ptlForTable over the real T-11 roster (the flagged cluster)', () => {
  it('every seated player at T-11 reads cool (cluster + grinders — staying, not bolting)', async () => {
    const [health, classifications, roster] = await Promise.all([
      loadHealth(),
      loadClassifications(),
      loadTableRoster(),
    ])
    const t11 = roster.tables.find((t) => t.table_id === 'T-11')!
    const healthRow = health.health_scores.find((h) => h.table_id === 'T-11')
    const map = ptlForTable(t11, healthRow, classificationIndex(classifications.classifications))

    expect(map.size).toBe(t11.seated_player_ids.length)
    for (const playerId of t11.seated_player_ids) {
      expect(ptlTone(map.get(playerId)!.ptl)).toBe('cool')
    }
  })

  it('returns an empty map when the table has no health row (→ seats render pending)', async () => {
    const [classifications, roster] = await Promise.all([loadClassifications(), loadTableRoster()])
    const t11 = roster.tables.find((t) => t.table_id === 'T-11')!
    expect(ptlForTable(t11, undefined, classificationIndex(classifications.classifications)).size).toBe(0)
  })
})

describe('PTL — deterministic + reason codes', () => {
  it('same inputs → identical PTL and reason codes', async () => {
    const { t22 } = await tables()
    expect(computePtl('new', tableArg(t22))).toEqual(computePtl('new', tableArg(t22)))
  })

  it('emits a {code, detail, signals} gate then a table-pressure code', async () => {
    const { t22 } = await tables()
    const { reason_codes } = computePtl('new', tableArg(t22))
    expect(reason_codes).toHaveLength(2)
    expect(reason_codes[0].code).toBe('vulnerable_archetype')
    expect(reason_codes[1].code).toBe('table_pressure')
    for (const rc of reason_codes) {
      expect(rc.detail.length).toBeGreaterThan(0)
      expect(rc.signals).toBeTypeOf('object')
    }
    expect(reason_codes[1].signals.P_pred).toBe(t22.terms.P_pred)
  })
})
