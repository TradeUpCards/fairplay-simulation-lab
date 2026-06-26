import { useMemo, useState, type ReactNode } from 'react'
import pokerTable from '../assets/poker-table.png'
import {
  BOT_CHOICES,
  playApi,
  type ActionKind,
  type CoachResult,
  type LegalActions,
  type LogEntry,
  type PlayEnvelope,
  type PlayState,
  type SeatView,
} from '../state/playApi'

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

function PlayingCard({ card, small }: { card?: string; small?: boolean }) {
  const dim = small ? 'h-12 w-9 text-[1rem]' : 'h-20 w-14 text-[1.7rem]'
  if (!card) {
    return (
      <div
        className={`${dim} rounded-[5px] border border-brass-soft bg-[repeating-linear-gradient(135deg,#2a2114,#2a2114_4px,#1c160c_4px,#1c160c_8px)]`}
        aria-label="hidden card"
      />
    )
  }
  const s = SUITS[card[1]] ?? { glyph: card[1], red: false }
  return (
    <div
      className={`${dim} flex flex-col items-center justify-center rounded-[5px] border border-line bg-[#f6f4ee] font-semibold leading-none shadow-[0_2px_5px_rgba(0,0,0,0.35)] ${
        s.red ? 'text-[#c8324a]' : 'text-[#15110b]'
      }`}
    >
      <span>{rankLabel(card[0])}</span>
      <span className="text-[0.85em]">{s.glyph}</span>
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
    return { left: `${50 + 44 * Math.cos(theta)}%`, top: `${50 + 40 * Math.sin(theta)}%` }
  })
}

function Seat({ sv, heroHole }: { sv: SeatView; heroHole: [string, string] | null }) {
  const cards: (string | undefined)[] = sv.is_hero
    ? heroHole ?? [undefined, undefined]
    : [undefined, undefined]
  return (
    <div
      className={`flex w-[112px] -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1 ${
        sv.folded ? 'opacity-40' : ''
      }`}
    >
      {!sv.folded && (
        <div className="flex gap-1">
          {cards.map((c, i) => (
            <PlayingCard key={i} card={c} small={!sv.is_hero} />
          ))}
        </div>
      )}
      <div
        className={`w-full rounded-lg border px-2 py-1 text-center ${
          sv.to_act
            ? 'border-brass bg-[rgba(199,154,75,0.16)] shadow-[0_0_0_3px_rgba(199,154,75,0.2)]'
            : 'border-[#2c3543] bg-[rgba(14,17,22,0.88)]'
        }`}
      >
        <div className="flex items-center justify-center gap-1">
          <span className={`text-[0.74rem] font-semibold ${sv.is_hero ? 'text-brass' : 'text-text'}`}>
            {sv.label}
          </span>
          {sv.role && <Chip tone="role">{sv.role}</Chip>}
        </div>
        <div className="font-mono text-[0.62rem] text-muted">{sv.stack_bb}bb</div>
      </div>
      {sv.bet_bb > 0 && <Chip tone="bet">{sv.bet_bb}bb</Chip>}
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
      <ol className="m-0 flex max-h-[220px] list-none flex-col gap-1 overflow-auto p-0">
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

function CoachCard({ result }: { result: CoachResult }) {
  const c = result.coaching
  if (!c) {
    return (
      <div className="rounded-xl border border-line bg-surface p-4 text-sm text-muted">
        No coaching {result.guardrail_violations?.length ? '(guardrail)' : 'for this hand'}.
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-brass-soft bg-surface p-4">
      <div className="mb-1 font-mono text-[0.62rem] uppercase tracking-[0.18em] text-brass">AI Coach</div>
      <h3 className="m-0 mb-3 text-[1rem] font-semibold leading-snug text-text">{c.headline}</h3>
      <div className="mb-3 rounded-lg border border-line bg-surface-2 p-2.5 text-[0.82rem] text-muted">
        <span className="font-semibold text-text">Read — {c.opponent_read.style_label}:</span> {c.opponent_read.tell}
      </div>
      <div className="flex flex-col gap-2.5">
        {c.decisions.map((d, i) => (
          <div key={i} className="rounded-lg border border-line bg-surface-2 p-2.5">
            <div className="mb-1 flex flex-wrap items-center gap-2 text-[0.76rem]">
              <Chip>{d.street}</Chip>
              <span className="text-muted">you {d.your_action}</span>
              <span className="font-mono text-faint">equity {d.equity_pct}%</span>
            </div>
            <div className="text-[0.82rem] text-text">{d.assessment}</div>
            <div className="mt-1 text-[0.82rem]">
              <span className="font-semibold text-felt">Better:</span> <span className="text-text">{d.better_line}</span>
            </div>
            <div className="mt-0.5 text-[0.8rem] text-muted">{d.why_vs_this_type}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 mb-1 text-[0.84rem] text-text">{c.summary}</p>
      <p className="m-0 text-[0.8rem] italic text-muted">{c.coach_note}</p>
    </div>
  )
}

const FOLD_BTN =
  'rounded-md border px-4 py-1.5 text-[0.82rem] font-medium border-[#6b3a44] bg-[rgba(176,69,90,0.16)] text-[#e69aa8] hover:border-[#b3455a] disabled:opacity-50'
const CALL_BTN =
  'rounded-md border px-4 py-1.5 text-[0.82rem] font-medium border-line bg-surface-2 text-text hover:border-brass-soft disabled:opacity-50'
const RAISE_BTN =
  'rounded-md border px-4 py-1.5 text-[0.82rem] font-semibold border-brass bg-brass text-[#1a1407] hover:brightness-110 disabled:opacity-50'
const SIZE_BTN =
  'rounded-md border border-line bg-surface-2 px-2.5 py-1 text-[0.72rem] text-muted hover:border-brass-soft hover:text-text'

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

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        {legal.can_fold && (
          <button className={FOLD_BTN} onClick={() => onAct('fold')} disabled={busy}>
            Fold
          </button>
        )}
        {legal.can_check && (
          <button className={CALL_BTN} onClick={() => onAct('check')} disabled={busy}>
            Check
          </button>
        )}
        {legal.can_call && (
          <button className={CALL_BTN} onClick={() => onAct('call')} disabled={busy}>
            Call {bbStr(legal.call_chips)}
          </button>
        )}
        {legal.can_raise && (
          <button className={`${RAISE_BTN} ml-auto`} onClick={() => onAct('raise', raiseTo)} disabled={busy}>
            {facing ? 'Raise to' : 'Bet'} {bbStr(raiseTo)}
          </button>
        )}
      </div>
      {legal.can_raise && (
        <div className="flex flex-wrap items-center gap-2">
          <button className={SIZE_BTN} onClick={() => sizeTo(0.5)}>
            ½ pot
          </button>
          <button className={SIZE_BTN} onClick={() => sizeTo(0.75)}>
            ¾ pot
          </button>
          <button className={SIZE_BTN} onClick={() => sizeTo(1)}>
            Pot
          </button>
          <button className={SIZE_BTN} onClick={() => setRaiseTo(legal.max_raise_to)}>
            All-in
          </button>
          <div className="ml-auto flex items-center gap-2">
            <input
              type="range"
              min={legal.min_raise_to}
              max={legal.max_raise_to}
              value={raiseTo}
              onChange={(e) => setRaiseTo(Number(e.target.value))}
              className="w-32 accent-brass"
            />
            <div className="flex items-center gap-1">
              <input
                type="number"
                step={0.5}
                min={Number((legal.min_raise_to / bb).toFixed(1))}
                max={Number((legal.max_raise_to / bb).toFixed(1))}
                value={Number((raiseTo / bb).toFixed(1))}
                onChange={(e) => setRaiseTo(clamp(Number(e.target.value) * bb))}
                className="w-[4.5rem] rounded-md border border-line bg-surface-2 px-2 py-1 text-right text-[0.8rem] text-text"
              />
              <span className="font-mono text-[0.7rem] text-muted">bb</span>
            </div>
          </div>
        </div>
      )}
      {legal.can_raise && (
        <div className="font-mono text-[0.6rem] tracking-wider text-faint">
          min {bbStr(legal.min_raise_to)} · max {bbStr(legal.max_raise_to)} (all-in)
        </div>
      )}
    </div>
  )
}

const DEFAULT_SLOTS = ['recreational', 'aggressive_predatory', 'promo_hunter', 'grinder', 'regular']
const ARCHS = BOT_CHOICES.map((c) => c.archetype)

export function TrainingTable() {
  const [slots, setSlots] = useState<string[]>(DEFAULT_SLOTS) // '' = empty seat
  const [mystery, setMystery] = useState(false)
  const [seed, setSeed] = useState(1)
  const [handNum, setHandNum] = useState(0) // rotates the button so position varies
  const [env, setEnv] = useState<PlayEnvelope | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [coach, setCoach] = useState<CoachResult | null>(null)
  const [coachBusy, setCoachBusy] = useState(false)

  const st: PlayState | null = env?.state ?? null
  const sid = env?.session_id ?? null
  const bb = st?.big_blind ?? 2
  const nBots = slots.filter(Boolean).length

  const positions = useMemo(() => (st ? seatPositions(st.max_seats) : []), [st])
  // Place seats in true action order around the ring with the hero at the bottom
  // (slot 0). The seat to the hero's left lands at slot 1, and so on — so the
  // positions (UTG/HJ/CO/BTN/SB/BB) flow around the table the way poker action does.
  const slotForSeat = (seat: number) =>
    st ? (seat - st.hero_seat + st.max_seats) % st.max_seats : 0

  async function deal() {
    setBusy(true)
    setError(null)
    setCoach(null)
    try {
      const nSeats = slots.filter(Boolean).length + 1
      const next = await playApi.newHand({
        bots: slots,
        reveal: !mystery,
        seed,
        hero_seat: handNum % nSeats, // rotate the button each hand
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
      setEnv(next)
      if (next.state.complete) void fetchCoach(sid)
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  async function fetchCoach(s: string) {
    setCoachBusy(true)
    try {
      setCoach((await playApi.coach(s)).coaching)
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setCoachBusy(false)
    }
  }

  const legal: LegalActions | null = st?.legal ?? null
  const heroTurn = !!st && !st.complete && !!legal
  const bbStr = (chips: number) => `${(chips / bb).toFixed(1)}bb`

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
      <div>
        {/* setup bar */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
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
          <label className="flex items-center gap-1.5 text-[0.76rem] text-muted">
            <input type="checkbox" checked={mystery} onChange={(e) => setMystery(e.target.checked)} className="accent-brass" />
            Mystery
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

        {/* felt */}
        <div className="relative mx-auto aspect-4/3 w-full max-w-[680px]">
          <img
            className="absolute inset-0 h-full w-full object-contain opacity-[0.92]"
            src={pokerTable}
            alt=""
            aria-hidden="true"
          />
          {/* board + pot */}
          <div className="absolute left-1/2 top-[46%] flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2">
            <div className="flex gap-1.5">
              {(st?.board ?? []).map((c, i) => (
                <PlayingCard key={i} card={c} />
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
            const pos = positions[slotForSeat(sv.seat)]
            return (
              <div key={sv.seat} className="absolute" style={pos}>
                <Seat sv={sv} heroHole={st.hero_hole} />
              </div>
            )
          })}
        </div>

        {/* action bar */}
        <div className="mt-4 min-h-[64px] rounded-xl border border-line bg-surface p-3">
          {error && <div className="mb-2 text-[0.8rem] text-[#e0607a]">{error}</div>}
          {!st && <div className="text-[0.84rem] text-muted">Seat 1–5 opponents (Empty = fewer players), then deal.</div>}
          {st?.complete && (
            <div className="text-[0.84rem] text-muted">
              Hand complete{coachBusy ? ' — coaching…' : coach ? '' : ' — fetching coaching…'}
            </div>
          )}
          {heroTurn && legal && st && (
            <ActionBar
              key={`${st.hand_id}-${st.street}-${st.pot}-${st.to_call}`}
              legal={legal}
              pot={st.pot}
              toCall={st.to_call}
              bb={bb}
              busy={busy}
              onAct={act}
            />
          )}
        </div>
      </div>

      {/* right column: action log + coaching */}
      <aside className="flex flex-col gap-4">
        {st && <ActionLog log={st.log} seats={st.seats} />}
        {coach ? (
          <CoachCard result={coach} />
        ) : (
          <div className="rounded-xl border border-dashed border-line bg-surface-2 p-4 text-[0.84rem] text-muted">
            {coachBusy
              ? 'The coach is reviewing your hand…'
              : 'Play a hand to the end and the AI coach reviews your decisions against the opponents’ specific leaks.'}
          </div>
        )}
      </aside>
    </div>
  )
}
