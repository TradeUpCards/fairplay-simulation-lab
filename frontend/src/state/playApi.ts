/**
 * Client for the single-human training table (`/api/play/*`).
 *
 * Request/response (no SSE) — a hand is short and turn-based, so the UI POSTs each
 * action and renders the returned state. Coaching is a separate, slower call made
 * once the hand completes. Mirrors the `API_BASE` convention used by `liveRoom`.
 */

const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ??
  'http://localhost:8000'

export interface LegalActions {
  can_fold: boolean
  can_check: boolean
  can_call: boolean
  call_chips: number
  can_raise: boolean
  min_raise_to: number
  max_raise_to: number
}

export interface SeatView {
  seat: number
  label: string
  archetype: string | null
  role: string // "BTN" | "SB" | "BB" | ""
  stack_bb: number
  bet_bb: number
  folded: boolean
  is_hero: boolean
  to_act: boolean
  hole: [string, string] | null // hero always; opponents only at showdown
  won: boolean
}

export interface LogEntry {
  seat: number
  street: string
  action: string
  amount_bb: number
}

export interface HandReview {
  opponent: { label: string; leak: string }
  decisions: { street: string; action: string; equity_pct: number }[]
}

export interface PlayState {
  hand_id: number
  complete: boolean
  hero_seat: number
  max_seats: number
  mystery: boolean
  hero_hole: [string, string] | null
  board: string[]
  street: string
  pot: number
  big_blind: number
  to_call: number
  legal: LegalActions | null
  seats: SeatView[]
  log: LogEntry[]
  review: HandReview | null // instant, LLM-free grounded feedback
  coaching: CoachResult | null
}

export interface PlayEnvelope {
  session_id: string
  state: PlayState
}

export interface CoachDecision {
  street: string
  your_action: string
  equity_pct: number
  verdict: 'good' | 'thin' | 'mistake'
  assessment: string
  better_line: string
  why_vs_this_type: string
}

export interface Coaching {
  headline: string
  opponent_read: { seat: number; style_label: string; tell: string }
  decisions: CoachDecision[]
  summary: string
  coach_note: string
}

export interface CoachResult {
  model?: string
  stop_reason?: string
  coaching: Coaching | null
  guardrail_violations?: string[]
  elapsed_ms?: number // server-side LLM call time (debug)
  summary_ms?: number // equity + summary assembly time (debug)
}

export type ActionKind = 'fold' | 'check' | 'call' | 'raise'

export interface NewHandOptions {
  bots?: string[]
  hero_seat?: number
  reveal?: boolean
  button_seat?: number
  seed?: number
  stack_bb?: number
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error((detail as { detail?: string }).detail ?? `request failed (${res.status})`)
  }
  return (await res.json()) as T
}

export const playApi = {
  newHand: (opts: NewHandOptions = {}): Promise<PlayEnvelope> =>
    post<PlayEnvelope>('/api/play/new', opts),
  act: (sid: string, kind: ActionKind, amount = 0): Promise<PlayEnvelope> =>
    post<PlayEnvelope>(`/api/play/${sid}/action`, { kind, amount }),
  coach: (sid: string): Promise<{ session_id: string; coaching: CoachResult; version?: string }> =>
    post<{ session_id: string; coaching: CoachResult; version?: string }>(`/api/play/${sid}/coach`),
}

/** The bot archetypes a player can seat, with friendly labels for the picker. */
export const BOT_CHOICES: { archetype: string; label: string }[] = [
  { archetype: 'recreational', label: 'Calling station' },
  { archetype: 'aggressive_predatory', label: 'Maniac / LAG' },
  { archetype: 'promo_hunter', label: 'Rock / nit' },
  { archetype: 'grinder', label: 'Grinder / TAG' },
  { archetype: 'regular', label: 'Solid regular' },
  { archetype: 'solver_like', label: 'Solver-like' },
  { archetype: 'new', label: 'Beginner / fish' },
]
