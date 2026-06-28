import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import pokerTable from '../assets/poker-table.png'
import {
  BOT_CHOICES,
  coachStream,
  parsePartialJson,
  playApi,
  type ActionKind,
  type Coaching,
  type CoachDecision,
  type CoachResult,
  type HandReview,
  type LegalActions,
  type LogEntry,
  type PlayEnvelope,
  type PlayState,
  type SeatView,
} from '../state/playApi'
import { archetypeBadge } from '../lib/lobbyIdentity'

/**
 * The training table — a single human at a 2-6 handed No-Limit Hold'em table of
 * configurable bot styles, with AI post-hand coaching. The server (`/api/play`)
 * owns the hand and reports the table view (per-seat stacks/bets/blinds and the
 * action log); this view renders it on the same felt the pit-boss uses and submits
 * the human's moves, then fetches coaching once the hand completes.
 */

const SUITS: Record<string, { glyph: string; red: boolean }> = {
  h: { glyph: '♥', red: true },
  d: { glyph: '♦', red: true },
  c: { glyph: '♣', red: false },
  s: { glyph: '♠', red: false },
}
const rankLabel = (r: string) => (r === 'T' ? '10' : r)

function PlayingCard({ card, small, dealt }: { card?: string; small?: boolean; dealt?: boolean }) {
  const dim = small ? 'h-14 w-10 text-[1.15rem]' : 'h-20 w-14 text-[1.7rem]'
  // `dealt` cards play the deal-in keyframe once on mount — board cards pass it, so
  // each street visibly drops onto the felt as it is dealt.
  const anim = dealt ? 'animate-deal-in' : ''
  if (!card) {
    return (
      <div
        className={`${dim} ${anim} rounded-[5px] border border-brass-soft bg-[repeating-linear-gradient(135deg,#2a2114,#2a2114_4px,#1c160c_4px,#1c160c_8px)]`}
        aria-label="hidden card"
      />
    )
  }
  const s = SUITS[card[1]] ?? { glyph: card[1], red: false }
  return (
    <div
      className={`${dim} ${anim} flex flex-col items-center justify-center rounded-[5px] border border-line bg-[#f6f4ee] font-semibold leading-none shadow-[0_2px_5px_rgba(0,0,0,0.35)] ${
        s.red ? 'text-[#c8324a]' : 'text-[#15110b]'
      }`}
    >
      <span>{rankLabel(card[0])}</span>
      <span className="text-[0.85em]">{s.glyph}</span>
    </div>
  )
}

// Deterministic per-seat avatar: an archetype glyph on a hue derived from the label,
// so a given opponent looks the same all session. In Mystery mode the archetype is
// hidden (null), so unknown opponents share a neutral face.
const ARCH_AVATAR: Record<string, string> = {
  recreational: '🐟',
  aggressive_predatory: '🔥',
  promo_hunter: '🪨',
  grinder: '⚙️',
  regular: '🎯',
  solver_like: '🤖',
  new: '🌱',
}
function hashHue(s: string): number {
  let h = 0
  for (const ch of s) h = (h * 31 + ch.charCodeAt(0)) % 360
  return h
}
// Large round portrait — the same design as the lobby sidecar seats. Carries the
// turn/winner ring state so the circle (not a box) is the seat's focal point.
function Avatar({ sv }: { sv: SeatView }) {
  // Cartoon archetype mascot (shark/fish/robot…); null in Mystery mode → neutral face.
  const imageUrl = sv.is_hero ? null : archetypeBadge(sv.archetype)
  const emoji = sv.is_hero ? '🧑' : (ARCH_AVATAR[sv.archetype ?? ''] ?? '🎭')
  const hue = hashHue(sv.label)
  const ring = sv.won
    ? 'border-felt shadow-[0_0_0_3px_rgba(47,143,91,0.45)]'
    : sv.to_act
      ? 'border-brass animate-turn-pulse'
      : sv.is_hero
        ? 'border-brass'
        : 'border-[#3a4555]'
  return (
    <div
      className={`grid h-16 w-16 shrink-0 place-items-center overflow-hidden rounded-full border-2 text-[1.7rem] leading-none shadow-[0_2px_6px_rgba(0,0,0,0.5)] ${ring}`}
      style={{
        background: `radial-gradient(circle at 30% 25%, hsl(${hue} 42% 36%), hsl(${hue} 46% 15%))`,
      }}
      aria-hidden="true"
    >
      {imageUrl ? <img src={imageUrl} alt="" className="h-full w-full object-cover" /> : emoji}
    </div>
  )
}

function Chip({ children, tone }: { children: ReactNode; tone?: 'role' | 'bet' }) {
  const cls =
    tone === 'bet'
      ? 'border-brass-soft bg-[rgba(199,154,75,0.16)] text-brass'
      : tone === 'role'
        ? 'border-line bg-[rgba(0,0,0,0.4)] text-[#cfd5e0]'
        : 'border-brass-soft bg-[rgba(199,154,75,0.1)] text-brass'
  return (
    <span className={`rounded-full border px-1.5 py-0.5 font-mono text-[0.58rem] tracking-wider ${cls}`}>
      {children}
    </span>
  )
}

// seats evenly around an ellipse, hero at the bottom (slot 0)
function seatPositions(n: number): { top: string; left: string }[] {
  return Array.from({ length: n }, (_, i) => {
    const theta = Math.PI / 2 + (i / n) * Math.PI * 2
    // Push the pods OUT past the rail (off the felt) so the cards-over-avatar don't
    // spill onto the table; vertical radius a touch tighter so top/bottom don't clip.
    return { left: `${50 + 54 * Math.cos(theta)}%`, top: `${50 + 40 * Math.sin(theta)}%` }
  })
}

function Seat({ sv }: { sv: SeatView }) {
  // face-up if we have the cards (hero, or an opponent at showdown); face-down
  // backs while an opponent is still in the hand; nothing once folded.
  const showCards = sv.hole !== null || !sv.folded
  const cards: (string | undefined)[] = sv.hole ?? [undefined, undefined]
  // Same design as the lobby sidecar: a large portrait above a name + stack card
  // (the card tucked behind the circle's lower edge). Active/winner state tints both
  // the avatar ring (in <Avatar/>) and the card border.
  const cardTone = sv.won
    ? 'border-felt bg-[#12251a]'
    : sv.to_act
      ? 'border-brass bg-[#1c1a12]'
      : 'border-[#2c3543] bg-[#10141b]'
  return (
    // The avatar+card unit is the anchor — its CENTER sits on the seat point. Hole
    // cards (above the avatar) and the bet chip (below the card) are absolutely
    // positioned, so showing/hiding either never nudges the seat.
    <div
      className={`relative flex w-[112px] flex-col items-center -translate-x-1/2 -translate-y-1/2 ${sv.folded ? 'opacity-40' : ''}`}
    >
      <div className="relative">
        {showCards && (
          <div className="absolute bottom-1 left-1/2 z-10 flex -translate-x-1/2 gap-0.5">
            {cards.map((c, i) => (
              <PlayingCard key={i} card={c} small={!sv.is_hero} />
            ))}
          </div>
        )}
        <Avatar sv={sv} />
      </div>
      <div
        className={`relative -mt-3 z-20 w-full rounded-lg border px-1.5 pb-1 pt-2.5 text-center leading-tight ${cardTone}`}
      >
        <div className={`text-[0.76rem] font-semibold ${sv.is_hero ? 'text-brass' : 'text-text'}`}>
          {sv.label}
        </div>
        <div className="mt-0.5 flex items-center justify-center gap-1 font-mono text-[0.7rem] font-semibold text-[#d9c08a]">
          {sv.role && <Chip tone="role">{sv.role}</Chip>}
          <span>
            {sv.stack_bb}bb{sv.won && <span className="text-felt"> · won</span>}
          </span>
        </div>
      </div>
      {sv.bet_bb > 0 && (
        <div className="absolute top-full left-1/2 mt-1 -translate-x-1/2">
          <Chip tone="bet">{sv.bet_bb}bb</Chip>
        </div>
      )}
    </div>
  )
}

function logName(e: LogEntry, seats: SeatView[]): string {
  const sv = seats.find((s) => s.seat === e.seat)
  if (sv?.is_hero) return 'You'
  return sv?.role || `Seat ${e.seat + 1}` // position (UTG/HJ/CO/BTN/SB/BB) anchors the action
}
function logVerb(e: LogEntry): string {
  switch (e.action) {
    case 'fold':
      return 'folds'
    case 'check':
      return 'checks'
    case 'call':
      return `calls ${e.amount_bb}bb`
    case 'bet':
      return `bets ${e.amount_bb}bb`
    case 'raise':
      return `raises to ${e.amount_bb}bb`
    default:
      return e.action
  }
}

function ActionLog({ log, seats }: { log: LogEntry[]; seats: SeatView[] }) {
  if (!log.length) return null
  return (
    <div className="rounded-xl border border-line bg-surface p-3">
      <div className="mb-2 font-mono text-[0.6rem] uppercase tracking-[0.18em] text-muted">Hand action</div>
      <ol className="m-0 flex list-none flex-col gap-1 p-0">
        {log.map((e, i) => (
          <li key={i} className="flex items-baseline gap-2 text-[0.8rem]">
            <span className="w-12 font-mono text-[0.58rem] uppercase tracking-wider text-faint">{e.street}</span>
            <span className="text-text">
              <span className="font-semibold">{logName(e, seats)}</span> {logVerb(e)}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function VerdictChip({ v }: { v: 'good' | 'thin' | 'mistake' }) {
  const tone: Record<string, string> = {
    good: 'border-[#2f8f5b] bg-[rgba(47,143,91,0.16)] text-[#5fcf8a]',
    thin: 'border-[#8a6d2f] bg-[rgba(199,154,75,0.14)] text-[#e3b25f]',
    mistake: 'border-[#7a3340] bg-[rgba(176,69,90,0.18)] text-[#e69aa8]',
  }
  return (
    <span className={`rounded-full border px-1.5 py-0.5 font-mono text-[0.56rem] uppercase tracking-wider ${tone[v] ?? tone.thin}`}>
      {v}
    </span>
  )
}

// One card for the post-hand right column. The grounded, LLM-free review (opponent
// leak + each decision's equity) paints instantly and is ALWAYS the skeleton; the AI
// coach's verdict / reasoning / summary stream in and ANNOTATE those same rows rather
// than replacing the card — so nothing the user is already reading gets overwritten.
function ReviewCoachCard({
  review,
  coaching,
  streaming,
  busy,
  guardrail,
  onCoach,
}: {
  review: HandReview | null
  coaching: Coaching | null
  streaming?: boolean
  busy?: boolean
  guardrail?: boolean
  onCoach?: () => void
}) {
  const coached = !!coaching
  // Match each coach decision to a grounded row by street + nearest equity (one-to-one,
  // within tolerance) so a rounded or reordered coach decision can't mislabel a row.
  const coachList = (coaching?.decisions ?? []).filter(Boolean)
  const used = new Set<number>()
  const matchCoach = (street: string, eq: number): CoachDecision | null => {
    let best = -1
    let bestDiff = Infinity
    coachList.forEach((d, idx) => {
      if (used.has(idx) || d.street !== street) return
      const diff = Math.abs((d.equity_pct ?? 999) - eq)
      if (diff < bestDiff) {
        bestDiff = diff
        best = idx
      }
    })
    if (best >= 0 && bestDiff <= 6) {
      used.add(best)
      return coachList[best]
    }
    return null
  }

  // Prefer the grounded review as the stable skeleton; fall back to the coach's own
  // decision list only if the review is somehow absent.
  const rows = review?.decisions.length
    ? review.decisions.map((d) => ({
        street: d.street,
        action: d.action,
        equity_pct: d.equity_pct,
        coach: matchCoach(d.street, d.equity_pct),
      }))
    : coachList.map((d) => ({
        street: d.street,
        action: d.your_action,
        equity_pct: d.equity_pct,
        coach: d,
      }))

  const oppLabel = coaching?.opponent_read?.style_label ?? review?.opponent.label ?? ''
  const oppTell = coaching?.opponent_read?.tell ?? review?.opponent.leak ?? ''

  return (
    <div className={`rounded-xl border ${coached || busy ? 'border-brass-soft' : 'border-line'} bg-surface p-4`}>
      <div className="mb-1 flex items-center gap-2 font-mono text-[0.62rem] uppercase tracking-[0.18em] text-brass">
        {coached ? 'AI Coach' : 'Hand review'}
        {streaming && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brass" />}
      </div>
      {coaching?.headline && (
        <h3 className="m-0 mb-3 text-[1rem] font-semibold leading-snug text-text">{coaching.headline}</h3>
      )}
      {oppTell && (
        <div className="mb-3 rounded-lg border border-line bg-surface-2 p-2.5 text-[0.82rem] text-muted">
          <span className="font-semibold text-text">
            {coached ? 'Read — ' : 'vs '}
            {oppLabel}:
          </span>{' '}
          {oppTell}
        </div>
      )}
      <div className="flex flex-col gap-2.5">
        {rows.map((d, i) => (
          <div key={i} className="rounded-lg border border-line bg-surface-2 p-2.5">
            <div className="flex flex-wrap items-center gap-2 text-[0.76rem]">
              <Chip>{d.street}</Chip>
              {d.coach?.verdict && <VerdictChip v={d.coach.verdict} />}
              <span className="text-muted">you {d.action}</span>
              <span className="font-mono text-faint">equity {d.equity_pct}%</span>
            </div>
            {d.coach?.why_this_play && <div className="mt-1 text-[0.82rem] text-text">{d.coach.why_this_play}</div>}
            {d.coach?.better_line && (
              <div className="mt-1 text-[0.82rem]">
                <span className="font-semibold text-felt">{d.coach.verdict === 'good' ? 'Right play:' : 'Better:'}</span>{' '}
                <span className="text-text">{d.coach.better_line}</span>
              </div>
            )}
          </div>
        ))}
      </div>
      {coaching?.summary && <p className="mt-3 mb-0 text-[0.84rem] text-text">{coaching.summary}</p>}
      {!coached && (
        <div className="mt-3">
          {busy ? (
            <div className="flex items-center gap-2 text-[0.78rem] text-muted">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-brass" />
              AI coach is writing…
            </div>
          ) : guardrail ? (
            <div className="text-[0.78rem] text-muted">No AI coaching for this hand (guardrail).</div>
          ) : onCoach ? (
            <button
              type="button"
              onClick={onCoach}
              className="rounded-md border border-brass bg-brass px-3 py-1.5 text-[0.78rem] font-semibold text-[#1a1407]"
            >
              Coach this hand
            </button>
          ) : null}
        </div>
      )}
    </div>
  )
}

// Poker-client action buttons: large, the aggressive action a bold saturated
// primary (green, on-theme with the felt), Check/Call neutral, Fold a filled red.
const BTN_BASE = 'flex items-center justify-center gap-1.5 rounded-xl px-4 py-2.5 leading-tight disabled:opacity-50'
const FOLD_BTN =
  `${BTN_BASE} bg-[#5a2730] border border-[#7a3340] text-[#f0c0cc] hover:bg-[#6b2f3a]`
const CALL_BTN =
  `${BTN_BASE} bg-[#2a323f] border border-[#3a4757] text-text hover:bg-[#333d4d]`
const RAISE_BTN =
  `${BTN_BASE} bg-felt border border-[#3aa86c] text-[#0c1f14] shadow-[0_2px_8px_rgba(47,143,91,0.3)] hover:brightness-110`
const SIZE_BTN =
  'rounded-full border border-line bg-surface px-3 py-1 text-[0.72rem] font-semibold text-muted hover:border-brass hover:text-brass'

/** The betting interface: distinct action buttons + quick pot-sizes + a typed
 * bet-amount field (in bb) synced to a slider. Remounted per decision (via `key`)
 * so the default size re-primes each time. Amounts are in chips internally; the
 * API wants a total "raise-to". */
function ActionBar({
  legal,
  pot,
  toCall,
  bb,
  busy,
  onAct,
}: {
  legal: LegalActions
  pot: number
  toCall: number
  bb: number
  busy: boolean
  onAct: (kind: ActionKind, amount?: number) => void
}) {
  const facing = toCall > 0
  const clamp = (chips: number) =>
    Math.max(legal.min_raise_to, Math.min(legal.max_raise_to, Math.round(chips)))
  const [raiseTo, setRaiseTo] = useState(() => clamp(toCall + pot * 0.66))
  const bbStr = (chips: number) => `${(chips / bb).toFixed(1)}bb`
  const sizeTo = (frac: number) => setRaiseTo(clamp(toCall + pot * frac))
  // fraction of the slider range that's filled, for the brass progress track
  const span = Math.max(1, legal.max_raise_to - legal.min_raise_to)
  const fillPct = Math.round(((raiseTo - legal.min_raise_to) / span) * 100)
  const SIZES: [string, number][] = [['25%', 0.25], ['33%', 0.33], ['50%', 0.5], ['75%', 0.75], ['Pot', 1]]

  return (
    <div className="flex flex-col gap-2">
      {/* sizing — percent presets, a poker-client slider, and the editable amount */}
      {legal.can_raise && (
        <div className="rounded-xl border border-line bg-surface-2 p-2">
          <div className="mb-1.5 flex items-center gap-2">
            <span className="font-mono text-[0.58rem] uppercase tracking-[0.18em] text-muted">
              {facing ? 'Raise to' : 'Bet'}
            </span>
            <div className="ml-auto flex items-baseline gap-1">
              <input
                type="number"
                step={0.5}
                min={Number((legal.min_raise_to / bb).toFixed(1))}
                max={Number((legal.max_raise_to / bb).toFixed(1))}
                value={Number((raiseTo / bb).toFixed(1))}
                onChange={(e) => setRaiseTo(clamp(Number(e.target.value) * bb))}
                className="w-[4.5rem] rounded-md border border-line bg-surface px-2 py-0.5 text-right text-[1.05rem] font-bold text-brass"
              />
              <span className="font-mono text-[0.7rem] text-muted">bb</span>
            </div>
          </div>
          <input
            type="range"
            min={legal.min_raise_to}
            max={legal.max_raise_to}
            value={raiseTo}
            onChange={(e) => setRaiseTo(Number(e.target.value))}
            className="bet-slider mb-2"
            style={{ ['--fill' as string]: `${fillPct}%` }}
          />
          <div className="flex flex-wrap items-center gap-1.5">
            {SIZES.map(([label, frac]) => (
              <button key={label} className={SIZE_BTN} onClick={() => sizeTo(frac)}>
                {label}
              </button>
            ))}
            <button className={SIZE_BTN} onClick={() => setRaiseTo(legal.max_raise_to)}>
              Max
            </button>
          </div>
        </div>
      )}
      {/* action buttons — single-line; the aggressive action is the green primary */}
      <div className="flex items-stretch gap-2">
        {legal.can_fold && (
          <button className={`${FOLD_BTN} flex-1`} onClick={() => onAct('fold')} disabled={busy}>
            <span className="text-[0.95rem] font-bold">Fold</span>
          </button>
        )}
        {legal.can_check && (
          <button className={`${CALL_BTN} flex-1`} onClick={() => onAct('check')} disabled={busy}>
            <span className="text-[0.95rem] font-bold">Check</span>
          </button>
        )}
        {legal.can_call && (
          <button className={`${CALL_BTN} flex-1`} onClick={() => onAct('call')} disabled={busy}>
            <span className="text-[0.95rem] font-bold">Call</span>
            <span className="font-mono text-[0.7rem] opacity-80">{bbStr(legal.call_chips)}</span>
          </button>
        )}
        {legal.can_raise && (
          <button
            className={`${RAISE_BTN} flex-[1.5]`}
            onClick={() => onAct('raise', raiseTo)}
            disabled={busy}
          >
            <span className="text-[0.95rem] font-bold">{facing ? 'Raise' : 'Bet'}</span>
            <span className="font-mono text-[0.72rem] opacity-90">{bbStr(raiseTo)}</span>
          </button>
        )}
      </div>
    </div>
  )
}

// The hero's decision timer. When it runs out we auto-check (free) or auto-fold —
// generous so it never rushes a thinking player, but it keeps a walked-away table moving.
const CLOCK_SECONDS = 30

function ActionClock({ left, total }: { left: number; total: number }) {
  const pct = Math.max(0, Math.min(100, (left / total) * 100))
  const low = left <= 10
  return (
    <div className="mb-1.5 flex items-center gap-2">
      <span className={`font-mono text-[0.7rem] tabular-nums ${low ? 'text-[#e0607a]' : 'text-muted'}`}>
        ⏱ {Math.ceil(left)}s
      </span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
        <div
          className={`h-full rounded-full transition-[width] duration-100 ease-linear ${low ? 'bg-[#b0455a]' : 'bg-brass'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// Phase 5 — the blind "identify the type" round. After playing the mystery table, the
// human guesses each hidden opponent's archetype; reveal + score. Mirrors the classifier.
function IdentifyModal({
  opponents,
  truthFor,
  onClose,
}: {
  opponents: SeatView[]
  truthFor: (seat: number) => string | undefined
  onClose: () => void
}) {
  const [guesses, setGuesses] = useState<Record<number, string>>({})
  const [scored, setScored] = useState(false)
  const labelFor = (a?: string) => BOT_CHOICES.find((c) => c.archetype === a)?.label ?? a ?? '—'
  const correct = opponents.filter((o) => guesses[o.seat] === truthFor(o.seat)).length
  const allGuessed = opponents.every((o) => guesses[o.seat])
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[rgba(0,0,0,0.62)] p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-brass-soft bg-surface p-5 shadow-[0_10px_40px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-1 font-mono text-[0.62rem] uppercase tracking-[0.18em] text-brass">Read the table</div>
        <h3 className="m-0 mb-3 text-[1.05rem] font-semibold leading-snug text-text">
          {scored ? 'How well did you read them?' : "Guess each opponent's type from how they played."}
        </h3>
        <div className="flex flex-col gap-2.5">
          {opponents.map((o) => {
            const truth = truthFor(o.seat)
            const right = scored && guesses[o.seat] === truth
            return (
              <div key={o.seat} className="flex items-center gap-2.5">
                <Avatar sv={o} />
                <span className="w-[4.5rem] shrink-0 text-[0.82rem] font-semibold text-text">{o.label}</span>
                <select
                  value={guesses[o.seat] ?? ''}
                  disabled={scored}
                  onChange={(e) => setGuesses((g) => ({ ...g, [o.seat]: e.target.value }))}
                  className="min-w-0 flex-1 rounded-md border border-line bg-surface-2 px-2 py-1 text-[0.8rem] text-text disabled:opacity-70"
                >
                  <option value="">— pick a type —</option>
                  {BOT_CHOICES.map((c) => (
                    <option key={c.archetype} value={c.archetype}>
                      {c.label}
                    </option>
                  ))}
                </select>
                {scored && (
                  <span className={`w-[5.5rem] shrink-0 text-right text-[0.74rem] ${right ? 'text-felt' : 'text-[#e0607a]'}`}>
                    {right ? '✓ right' : `✗ ${labelFor(truth)}`}
                  </span>
                )}
              </div>
            )
          })}
        </div>
        {scored ? (
          <div className="mt-4 flex items-center justify-between">
            <span className="text-[0.95rem] font-semibold text-brass">
              {correct}/{opponents.length} correct
            </span>
            <button
              className="rounded-md border border-brass bg-brass px-3 py-1.5 text-[0.78rem] font-semibold text-[#1a1407]"
              onClick={onClose}
            >
              Play on
            </button>
          </div>
        ) : (
          <div className="mt-4 flex justify-end gap-2">
            <button
              className="rounded-md border border-line bg-surface-2 px-3 py-1.5 text-[0.78rem] text-muted"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              disabled={!allGuessed}
              className="rounded-md border border-brass bg-brass px-3 py-1.5 text-[0.78rem] font-semibold text-[#1a1407] disabled:opacity-50"
              onClick={() => setScored(true)}
            >
              Reveal &amp; score
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

const DEFAULT_SLOTS = ['recreational', 'aggressive_predatory', 'promo_hunter', 'grinder', 'regular']
const ARCHS = BOT_CHOICES.map((c) => c.archetype)

export function TrainingTable() {
  const [slots, setSlots] = useState<string[]>(DEFAULT_SLOTS) // '' = empty seat
  const [mystery, setMystery] = useState(false)
  const [challenge, setChallenge] = useState(false) // Phase 5: mystery "identify the type" round
  const [identifyOpen, setIdentifyOpen] = useState(false)
  const [aggression, setAggression] = useState(1.0) // table-style preset (0.8 / 1.0 / 1.4)
  const [seed, setSeed] = useState(1)
  const [handNum, setHandNum] = useState(0) // rotates the button so position varies
  const [env, setEnv] = useState<PlayEnvelope | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [coach, setCoach] = useState<CoachResult | null>(null)
  const [coachBusy, setCoachBusy] = useState(false)
  const [autoCoach, setAutoCoach] = useState(true)
  const [partial, setPartial] = useState<Coaching | null>(null)
  const [review, setReview] = useState<HandReview | null>(null) // grounded review (fetched on complete)
  const [debug, setDebug] = useState<{
    clientMs: number
    ttfaMs: number
    llmMs: number
    equityMs: number
    model: string
    version: string
  } | null>(null)

  const st: PlayState | null = env?.state ?? null
  const sid = env?.session_id ?? null
  const bb = st?.big_blind ?? 2
  const nBots = slots.filter(Boolean).length

  // FIXED ring: always (5 opponent slots + hero) positions, so seats never move when a
  // player is unseated. The hero owns slot 0 (bottom); opponent dropdown index i owns
  // slot i+1, permanently — empty dropdowns simply leave that ring spot vacant.
  const SEAT_RING = slots.length + 1
  const positions = useMemo(() => seatPositions(SEAT_RING), [SEAT_RING])
  const filledSlots = useMemo(
    () => slots.map((s, i) => (s ? i : -1)).filter((i) => i >= 0),
    [slots],
  )
  // seat number -> fixed ring slot. The k-th opponent (by seat order) is the k-th
  // filled dropdown, so its ring slot is its dropdown index + 1.
  const seatToSlot = useMemo(() => {
    const map: Record<number, number> = {}
    let opp = 0
    for (const sv of st?.seats ?? []) {
      map[sv.seat] = sv.is_hero ? 0 : (filledSlots[opp++] ?? 0) + 1
    }
    return map
  }, [st, filledSlots])

  // Phase 5: a blind "identify the type" round — seat a full RANDOM table, hidden, so
  // the player reads behavior across hands then guesses. The truth lives in `slots`.
  function startChallenge() {
    setSlots(DEFAULT_SLOTS.map(() => ARCHS[Math.floor(Math.random() * ARCHS.length)]))
    setMystery(true)
    setChallenge(true)
    setEnv(null)
  }
  function exitChallenge() {
    setChallenge(false)
    setMystery(false)
    setIdentifyOpen(false)
  }
  // each opponent seat's true archetype, via its fixed ring slot → dropdown index.
  const truthFor = (seat: number) => {
    const slot = seatToSlot[seat]
    return slot ? slots[slot - 1] : undefined
  }
  const opponents = (st?.seats ?? []).filter((s) => !s.is_hero)

  async function deal() {
    setBusy(true)
    setError(null)
    setCoach(null)
    setPartial(null)
    setReview(null)
    try {
      const nSeats = slots.filter(Boolean).length + 1
      const next = await playApi.newHand({
        bots: slots,
        reveal: !mystery,
        seed,
        aggression,
        // the human keeps a fixed seat (players don't move); rotate the dealer
        // button clockwise between hands, so only positions change.
        button_seat: handNum % nSeats,
      })
      setEnv(next)
      setSeed((s) => s + 1)
      setHandNum((h) => h + 1)
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  async function act(kind: ActionKind, amount = 0) {
    if (!sid) return
    setBusy(true)
    setError(null)
    try {
      const next = await playApi.act(sid, kind, amount)
      setEnv(next) // the RESULT shows immediately (no equity on this path)
      if (next.state.complete) {
        // grounded review (per-decision equity) fills in a beat after the result
        playApi.review(sid).then((r) => setReview(r.review)).catch(() => {})
        if (autoCoach) startCoach(sid)
      }
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  function startCoach(s: string) {
    setCoachBusy(true)
    setCoach(null)
    setPartial(null)
    let acc = ''
    let ttfa = 0
    const t0 = performance.now()
    coachStream(s, {
      onDelta: (chunk) => {
        if (!ttfa) ttfa = Math.round(performance.now() - t0) // time to first token
        acc += chunk
        // Keep the last successfully-parsed partial: a mid-key/mid-string chunk
        // parses to null, and reverting to it would flash the "writing…" card.
        const p = parsePartialJson(acc)
        if (p) setPartial(p)
      },
      onDone: (d) => {
        setCoach({
          coaching: d.coaching,
          model: d.model,
          guardrail_violations: d.guardrail_violations,
          elapsed_ms: d.elapsed_ms,
          summary_ms: d.summary_ms,
        })
        setPartial(null)
        setCoachBusy(false)
        setDebug({
          clientMs: Math.round(performance.now() - t0),
          ttfaMs: ttfa,
          llmMs: d.elapsed_ms ?? 0,
          equityMs: d.summary_ms ?? 0,
          model: d.model ?? '',
          version: d.version ?? '?',
        })
      },
      onError: () => {
        setCoachBusy(false)
        setError('coaching stream failed')
      },
    })
  }

  const legal: LegalActions | null = st?.legal ?? null
  const heroTurn = !!st && !st.complete && !!legal
  const bbStr = (chips: number) => `${(chips / bb).toFixed(1)}bb`

  // Action clock: count down per hero decision; on expiry auto-check (if free) or fold.
  // Latest `act`/`legal` go through refs so the interval effect only restarts when the
  // actual decision changes — not on every render.
  const [clockLeft, setClockLeft] = useState(CLOCK_SECONDS)
  const actRef = useRef(act)
  const legalRef = useRef(legal)
  actRef.current = act
  legalRef.current = legal
  const decisionKey = heroTurn && st ? `${st.hand_id}|${st.street}|${st.pot}|${st.to_call}` : null
  useEffect(() => {
    // Freeze the clock the moment an action is submitted (busy) — it shouldn't keep
    // ticking (or auto-fire) while the server resolves the hand.
    if (!decisionKey || busy) return
    setClockLeft(CLOCK_SECONDS)
    const started = performance.now()
    const id = window.setInterval(() => {
      const left = Math.max(0, CLOCK_SECONDS - (performance.now() - started) / 1000)
      setClockLeft(left)
      if (left <= 0) {
        window.clearInterval(id)
        actRef.current(legalRef.current?.can_check ? 'check' : 'fold')
      }
    }, 100)
    return () => window.clearInterval(id)
  }, [decisionKey, busy])

  return (
    <>
      <div className="grid h-full min-h-0 grid-cols-1 gap-6 overflow-y-auto lg:grid-cols-[1fr_360px] lg:overflow-hidden">
      <div className="flex min-h-0 flex-col">
        {/* setup bar */}
        <div className="mb-4 flex shrink-0 flex-wrap items-center gap-2">
          {challenge ? (
            <>
              <span className="rounded-full border border-brass-soft bg-[rgba(199,154,75,0.1)] px-2.5 py-1 text-[0.74rem] text-brass">
                🎭 Mystery table — read them across hands
              </span>
              <button
                type="button"
                onClick={() => setIdentifyOpen(true)}
                disabled={opponents.length === 0}
                className="rounded-md border border-brass bg-brass px-2.5 py-1 text-[0.76rem] font-semibold text-[#1a1407] disabled:opacity-50"
                title={opponents.length === 0 ? 'Play at least one hand first' : undefined}
              >
                Identify types
              </button>
              <button
                type="button"
                onClick={exitChallenge}
                className="rounded-md border border-line bg-surface-2 px-2.5 py-1 text-[0.76rem] text-muted hover:border-brass-soft"
              >
                Exit
              </button>
            </>
          ) : (
            <>
              <span className="font-mono text-[0.62rem] uppercase tracking-[0.18em] text-muted">Seat</span>
              {slots.map((b, i) => (
                <select
                  key={i}
                  value={b}
                  onChange={(e) => setSlots((prev) => prev.map((p, j) => (j === i ? e.target.value : p)))}
                  className="rounded-md border border-line bg-surface-2 px-2 py-1 text-[0.76rem] text-text"
                >
                  <option value="">— Empty —</option>
                  {BOT_CHOICES.map((c) => (
                    <option key={c.archetype} value={c.archetype}>
                      {c.label}
                    </option>
                  ))}
                </select>
              ))}
              <button
                type="button"
                onClick={() => setSlots((prev) => prev.map(() => ARCHS[Math.floor(Math.random() * ARCHS.length)]))}
                className="rounded-md border border-line bg-surface-2 px-2.5 py-1 text-[0.76rem] text-text hover:border-brass-soft"
              >
                🎲 Random
              </button>
              <button
                type="button"
                onClick={startChallenge}
                className="rounded-md border border-brass-soft bg-[rgba(199,154,75,0.1)] px-2.5 py-1 text-[0.76rem] text-brass hover:bg-[rgba(199,154,75,0.18)]"
                title="Seat a random hidden table, then guess each opponent's type"
              >
                🎭 Mystery challenge
              </button>
            </>
          )}
          <label className="flex items-center gap-1.5 text-[0.76rem] text-muted" title="How loose/aggressive the table plays (applies on the next deal)">
            <span>Table</span>
            <select
              value={aggression}
              onChange={(e) => setAggression(Number(e.target.value))}
              className="rounded-md border border-line bg-surface-2 px-2 py-1 text-[0.76rem] text-text"
            >
              <option value={0.8}>Passive</option>
              <option value={1.0}>Standard</option>
              <option value={1.4}>Aggressive</option>
            </select>
          </label>
          {!challenge && (
            <label className="flex items-center gap-1.5 text-[0.76rem] text-muted">
              <input type="checkbox" checked={mystery} onChange={(e) => setMystery(e.target.checked)} className="accent-brass" />
              Mystery
            </label>
          )}
          <label className="flex items-center gap-1.5 text-[0.76rem] text-muted" title="Coach every hand automatically, or pull coaching on demand">
            <input type="checkbox" checked={autoCoach} onChange={(e) => setAutoCoach(e.target.checked)} className="accent-brass" />
            Auto coach
          </label>
          <button
            type="button"
            onClick={deal}
            disabled={busy || nBots === 0}
            className="ml-auto rounded-full border border-brass bg-brass px-4 py-1.5 text-[0.78rem] font-semibold text-[#1a1407] disabled:opacity-50"
            title={nBots === 0 ? 'Seat at least one opponent' : undefined}
          >
            {st && !st.complete ? 'New hand' : 'Deal'}
          </button>
        </div>

        {/* felt — the hero: the table scales to fill the available height, and the
            action controls overlay the bottom-right rail (poker-client composition) */}
        <div className="relative min-h-0 flex-1">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="relative aspect-3/2 h-full max-h-full w-auto max-w-full">
              <img
                className="absolute inset-0 h-full w-full object-contain opacity-[0.92]"
                src={pokerTable}
                alt=""
                aria-hidden="true"
              />
              {/* board + pot */}
              <div className="absolute left-1/2 top-[44%] flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2">
                <div className="flex gap-1.5">
                  {(st?.board ?? []).map((c, i) => (
                    <PlayingCard key={`${st?.hand_id}-${i}`} card={c} dealt />
                  ))}
                  {!st && <span className="font-mono text-[0.72rem] uppercase tracking-[0.18em] text-[#cdd6cf]">deal to begin</span>}
                </div>
                {st && (
                  <span className="rounded-full bg-[rgba(0,0,0,0.42)] px-3 py-0.5 font-mono text-[0.74rem] text-[#f0e6cf]">
                    pot {bbStr(st.pot)}
                  </span>
                )}
              </div>
              {/* seats */}
              {st?.seats.map((sv) => {
                const pos = positions[seatToSlot[sv.seat] ?? 0]
                return (
                  <div key={sv.seat} className="absolute" style={pos}>
                    <Seat sv={sv} />
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* action region — FIXED height, always present, so the felt above never
            reflows when the controls show/hide. The inner box is top-aligned and only
            rendered when there's something to say. */}
        <div className="mt-2 flex h-[212px] shrink-0 items-start justify-end">
          {(!!error || !st || st.complete || heroTurn) && (
            <div className="w-full max-w-[440px] rounded-xl border border-line bg-[rgba(20,25,34,0.97)] p-3 shadow-[0_6px_24px_rgba(0,0,0,0.5)]">
              {error && <div className="mb-2 text-[0.8rem] text-[#e0607a]">{error}</div>}
              {!st && <div className="text-[0.84rem] text-muted">Seat 1–5 opponents, then deal.</div>}
              {st?.complete && (
                <div className="text-[0.84rem] text-muted">
                  Hand complete
                  {coachBusy
                    ? ' — coaching…'
                    : coach
                      ? ''
                      : autoCoach
                        ? ' — fetching coaching…'
                        : ' — “Coach this hand”, or deal again.'}
                </div>
              )}
              {heroTurn && legal && st && (
                <>
                  <ActionClock left={clockLeft} total={CLOCK_SECONDS} />
                  <ActionBar
                    key={`${st.hand_id}-${st.street}-${st.pot}-${st.to_call}`}
                    legal={legal}
                    pot={st.pot}
                    toCall={st.to_call}
                    bb={bb}
                    busy={busy}
                    onAct={act}
                  />
                </>
              )}
            </div>
          )}
        </div>

      </div>

      {/* right column: AI coach and hand action, each with its OWN scroll */}
      <aside className="flex min-h-0 flex-col gap-4">
        <div className="min-h-0 overflow-y-auto lg:flex-1">
          {st?.complete && (review || coach || partial || coachBusy) ? (
            // One card: the grounded review (fetched a beat after the result) paints and
            // stays put; the AI coach streams its verdicts INTO those same rows.
            <ReviewCoachCard
              review={review}
              coaching={partial ?? coach?.coaching ?? null}
              streaming={!!partial && coachBusy}
              busy={coachBusy && !partial}
              guardrail={!!coach && !coach.coaching}
              onCoach={!autoCoach && !coach && !coachBusy && sid ? () => startCoach(sid) : undefined}
            />
          ) : st?.complete ? (
            <div className="rounded-xl border border-line bg-surface p-4 text-[0.84rem] text-muted">
              <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-brass" />
              Reviewing the hand…
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-line bg-surface-2 p-4 text-[0.84rem] text-muted">
              Play a hand to the end and the AI coach reviews your decisions against the opponents’ specific leaks.
            </div>
          )}
        </div>
        {st && st.log.length > 0 && (
          <div className="max-h-[14rem] shrink-0 overflow-y-auto">
            <ActionLog log={st.log} seats={st.seats} />
          </div>
        )}
      </aside>
      </div>
      {debug && (
        <button
          type="button"
          onClick={() => {
            const t = `v${debug.version} · client ${(debug.clientMs / 1000).toFixed(1)}s · TTFA ${(debug.ttfaMs / 1000).toFixed(1)}s · LLM ${(debug.llmMs / 1000).toFixed(1)}s · equity ${debug.equityMs}ms · ${debug.model}`
            void navigator.clipboard?.writeText(t)
          }}
          title="click to copy"
          className="fixed bottom-2 right-2 z-50 select-text rounded-md border border-line bg-[rgba(13,17,23,0.92)] px-2 py-1 font-mono text-[0.58rem] leading-tight text-faint"
        >
          DEBUG · v{debug.version} · client {(debug.clientMs / 1000).toFixed(1)}s · TTFA{' '}
          {(debug.ttfaMs / 1000).toFixed(1)}s · LLM {(debug.llmMs / 1000).toFixed(1)}s · equity{' '}
          {debug.equityMs}ms · {debug.model} · ⧉
        </button>
      )}
      {identifyOpen && (
        <IdentifyModal opponents={opponents} truthFor={truthFor} onClose={() => setIdentifyOpen(false)} />
      )}
    </>
  )
}
