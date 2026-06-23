/**
 * PTL — per-seat **propensity to leave** (0–1), the one score not in the
 * frozen scores contract.
 *
 * Decided 2026-06-22: PTL is derived UI-side rather than baked into the scoring
 * engine. If a champion `ptl_scores.json` is ever produced, the binding swaps in
 * `PitBossTable` with no other change.
 *
 * The model is two layers, multiplied:
 *
 *   PTL = volatility(archetype) × pressure(table)
 *
 * - **Layer 1 — archetype volatility** is the *direction gate* (CLAUDE.md: health
 *   risk ≠ integrity risk). Vulnerable archetypes (new / recreational) carry the
 *   leave-signal and run hot under pressure; the people a table preys *on*.
 *   Predators, grinders, anchors, and cluster members sit cool — they're seated
 *   by design, not about to bolt. This is what makes the heat *legible*: a hot
 *   seat is a fish at an unhealthy table, never "this player is suspicious."
 * - **Layer 2 — table pressure** comes from the table's own health terms
 *   (predation + fragility), so it's defined for every table the roster knows —
 *   seated players need no `seating_scores` entry of their own.
 *
 * Deterministic and pure: same inputs → same PTL → same reason codes. Heat is
 * banded by `ptlTone` in `lib/table.ts` (≥0.7 hot, 0.4–0.7 warm, else cool).
 */
import type {
  Archetype,
  Classification,
  HealthBand,
  HealthScore,
  HealthTerms,
  ReasonCode,
  TableRosterEntry,
} from '../data/types'
import { BAND_META, TERM_CAP } from './health'

export interface PtlResult {
  /** Propensity to leave, 0–1. 1.0 = most likely to leave. */
  ptl: number
  /** Always two: the archetype gate, then the table-pressure reading. `[0]` is the headline. */
  reason_codes: ReasonCode[]
}

/**
 * Layer 1 — how much leave-signal each archetype carries (the direction
 * contract). Vulnerable archetypes near 1.0; players seated by design near 0.
 * `promo_hunter` sits mid: it bounces once a promo is milked, but isn't a fish.
 */
export const ARCHETYPE_VOLATILITY: Record<Archetype, number> = {
  new: 1.0,
  recreational: 0.85,
  regular: 0.45,
  promo_hunter: 0.5,
  shared_device_household: 0.15,
  grinder: 0.1,
  aggressive_predatory: 0.08,
  healthy_anchor: 0.05,
  cluster_member: 0.05,
  bot_like: 0.0,
}

/** Archetypes that carry the leave-signal — they drive the hot end of the ring. */
const VULNERABLE: ReadonlySet<Archetype> = new Set<Archetype>(['new', 'recreational'])

/** Pressure weighting: predation dominates, fragility supports. */
const W_PRED = 0.6
const W_FRAG = 0.4

const clamp01 = (n: number): number => Math.min(1, Math.max(0, n))
const round2 = (n: number): number => Math.round(n * 100) / 100

/**
 * Layer 2 — table pressure 0–1 from health terms. Predation (`P_pred`, /45) and
 * fragility (`P_frag`, /25) are the two terms a *seated* player feels; cluster
 * and bleed terms describe the integrity case, not the urge to leave, so they're
 * left out. A healthy table → ~0; a predatory, fragile one → ~1.
 */
export function tablePressure(terms: HealthTerms): number {
  const pred = terms.P_pred / TERM_CAP.P_pred
  const frag = terms.P_frag / TERM_CAP.P_frag
  return clamp01(W_PRED * pred + W_FRAG * frag)
}

/**
 * PTL for one (archetype × table). Pure; emits `{code, detail, signals}` reason
 * codes whose `detail` is rendered verbatim (PRD DoD — no hand-written per-seat
 * copy). The two codes are the archetype gate and the table-pressure reading.
 */
export function computePtl(
  archetype: Archetype,
  table: { table_id: string; band: HealthBand; terms: HealthTerms },
): PtlResult {
  const volatility = ARCHETYPE_VOLATILITY[archetype]
  const pressure = tablePressure(table.terms)
  const ptl = round2(clamp01(volatility * pressure))

  const bandLabel = BAND_META[table.band].label.toLowerCase()
  const carries = VULNERABLE.has(archetype)
  const cool = volatility <= 0.15

  const gate: ReasonCode = {
    code: carries ? 'vulnerable_archetype' : cool ? 'anchored_archetype' : 'moderate_archetype',
    detail: carries
      ? `Vulnerable profile (${archetype.replace('_', ' ')}) — carries the leave-signal; runs hot under table pressure.`
      : cool
        ? `Seated by design (${archetype.replace('_', ' ')}) — low propensity to leave regardless of table.`
        : `Moderate profile (${archetype.replace('_', ' ')}) — some leave-signal under pressure.`,
    signals: { archetype, volatility },
  }

  const pressureCode: ReasonCode = {
    code: 'table_pressure',
    detail:
      pressure >= 0.4
        ? `${table.table_id} runs ${bandLabel} (predation ${table.terms.P_pred.toFixed(0)}/${TERM_CAP.P_pred}, fragility ${table.terms.P_frag.toFixed(0)}/${TERM_CAP.P_frag}) — pressure on vulnerable seats.`
        : `${table.table_id} reads ${bandLabel} (predation ${table.terms.P_pred.toFixed(0)}/${TERM_CAP.P_pred}, fragility ${table.terms.P_frag.toFixed(0)}/${TERM_CAP.P_frag}) — little pressure to leave.`,
    signals: {
      table_id: table.table_id,
      band: table.band,
      P_pred: table.terms.P_pred,
      P_frag: table.terms.P_frag,
      pressure: round2(pressure),
    },
  }

  return { ptl, reason_codes: [gate, pressureCode] }
}

/**
 * Per-seat PTL for a table's seated players — the map the seat-ring binds to.
 * Returns one entry per seated player with a known classification; players the
 * model can't score (no health row, or unknown classification) are simply
 * absent, so their seat renders neutral/`pending`.
 */
export function ptlForTable(
  table: TableRosterEntry,
  healthRow: HealthScore | undefined,
  classifications: Map<string, Classification>,
): Map<string, PtlResult> {
  const out = new Map<string, PtlResult>()
  if (!healthRow) return out

  for (const playerId of table.seated_player_ids) {
    const cls = classifications.get(playerId)
    if (!cls) continue
    out.set(
      playerId,
      computePtl(cls.archetype, {
        table_id: table.table_id,
        band: healthRow.band,
        terms: healthRow.terms,
      }),
    )
  }
  return out
}
