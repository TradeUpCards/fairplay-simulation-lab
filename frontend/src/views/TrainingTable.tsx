import { useMemo, useState, type ReactNode } from 'react'
import {
  BOT_CHOICES,
  playApi,
  type ActionKind,
  type CoachResult,
  type Opponent,
  type PlayEnvelope,
  type PlayState,
} from '../state/playApi'

/**
 * The training table — a single human at a 6-max No-Limit Hold'em table of
 * configurable bot styles, with AI post-hand coaching. Orthogonal to the
 * FairPlay operator product: this is the *coach*, the same AI architecture
 * pointed at teaching instead of risk. The server (`/api/play`) owns the hand;
 * this view renders state and submits the human's moves, then fetches coaching
 * once the hand completes.
 */

const SUITS: Record<string, { glyph: string; red: boolean }> = {
  h: { glyph: '♥', red: true },
  d: { glyph: '♦', red: true },
  c: { glyph: '♣', red: false },
  s: { glyph: '♠', red: false },
}
const rankLabel = (r: string) => (r === 'T' ? '10' : r)

function PlayingCard({ card, small }: { card?: string; small?: boolean }) {
  const dim = small ? 'h-11 w-8 text-[0.95rem]' : 'h-16 w-12 text-[1.3rem]'
  if (!card) {
    return (
      <div
        className={`${dim} rounded-[6px] border border-brass-soft bg-[repeating-linear-gradient(135deg,#2a2114,#2a2114_5px,#1c160c_5px,#1c160c_10px)]`}
        aria-label="hidden card"
      />
    )
  }
  const r = card[0]
  const s = SUITS[card[1]] ?? { glyph: card[1], red: false }
  return (
    <div
      className={`${dim} flex flex-col items-center justify-center rounded-[6px] border border-line bg-[#f6f4ee] font-semibold leading-none shadow-[0_2px_6px_rgba(0,0,0,0.35)] ${
        s.red ? 'text-[#c8324a]' : 'text-[#15110b]'
      }`}
    >
      <span>{rankLabel(r)}</span>
      <span className="text-[0.85em]">{s.glyph}</span>
    </div>
  )
}

// six anchor points around the oval; slot 0 is the hero, bottom-center
const SLOTS = [
  { top: '90%', left: '50%' },
  { top: '72%', left: '12%' },
  { top: '28%', left: '9%' },
  { top: '7%', left: '50%' },
  { top: '28%', left: '91%' },
  { top: '72%', left: '88%' },
]

function Seat({
  label,
  sub,
  cards,
  active,
  hero,
}: {
  label: string
  sub?: string
  cards?: (string | undefined)[]
  active?: boolean
  hero?: boolean
}) {
  return (
    <div
      className={`flex w-[140px] -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1.5 rounded-xl border px-2.5 py-2 text-center ${
        active
          ? 'border-brass bg-[rgba(199,154,75,0.14)] shadow-[0_0_0_3px_rgba(199,154,75,0.18)]'
          : 'border-line bg-surface-2/80'
      }`}
    >
      <div className="flex gap-1">
        {(cards ?? [undefined, undefined]).map((c, i) => (
          <PlayingCard key={i} card={c} small />
        ))}
      </div>
      <div className="leading-tight">
        <div className={`text-[0.78rem] font-semibold ${hero ? 'text-brass' : 'text-text'}`}>{label}</div>
        {sub && <div className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted">{sub}</div>}
      </div>
    </div>
  )
}

function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full border border-brass-soft bg-[rgba(199,154,75,0.1)] px-2.5 py-0.5 font-mono text-[0.7rem] tracking-wider text-brass">
      {children}
    </span>
  )
}

function CoachCard({ result }: { result: CoachResult }) {
  const c = result.coaching
  if (!c) {
    return (
      <div className="rounded-xl border border-line bg-surface p-4 text-sm text-muted">
        No coaching available {result.guardrail_violations?.length ? '(guardrail)' : ''}.
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-brass-soft bg-surface p-4">
      <div className="mb-1 font-mono text-[0.64rem] uppercase tracking-[0.18em] text-brass">AI Coach</div>
      <h3 className="m-0 mb-3 text-[1.02rem] font-semibold leading-snug text-text">{c.headline}</h3>
      <div className="mb-3 rounded-lg border border-line bg-surface-2 p-2.5 text-[0.84rem] text-muted">
        <span className="font-semibold text-text">Read — {c.opponent_read.style_label}:</span> {c.opponent_read.tell}
      </div>
      <div className="flex flex-col gap-2.5">
        {c.decisions.map((d, i) => (
          <div key={i} className="rounded-lg border border-line bg-surface-2 p-2.5">
            <div className="mb-1 flex flex-wrap items-center gap-2 text-[0.78rem]">
              <Chip>{d.street}</Chip>
              <span className="text-muted">you {d.your_action}</span>
              <span className="font-mono text-faint">equity {d.equity_pct}%</span>
            </div>
            <div className="text-[0.84rem] text-text">{d.assessment}</div>
            <div className="mt-1 text-[0.84rem]">
              <span className="font-semibold text-felt">Better:</span> <span className="text-text">{d.better_line}</span>
            </div>
            <div className="mt-0.5 text-[0.8rem] text-muted">{d.why_vs_this_type}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 mb-1 text-[0.86rem] text-text">{c.summary}</p>
      <p className="m-0 text-[0.8rem] italic text-muted">{c.coach_note}</p>
      {result.model && (
        <div className="mt-2 font-mono text-[0.6rem] uppercase tracking-[0.14em] text-faint">{result.model}</div>
      )}
    </div>
  )
}

const DEFAULT_BOTS = ['recreational', 'aggressive_predatory', 'promo_hunter', 'grinder', 'regular']

export function TrainingTable() {
  const [bots, setBots] = useState<string[]>(DEFAULT_BOTS)
  const [seed, setSeed] = useState<number>(() => 1)
  const [env, setEnv] = useState<PlayEnvelope | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [coach, setCoach] = useState<CoachResult | null>(null)
  const [coachBusy, setCoachBusy] = useState(false)
  const [raiseTo, setRaiseTo] = useState<number>(0)

  const st: PlayState | null = env?.state ?? null
  const sid = env?.session_id ?? null
  const bb = st?.big_blind ?? 2

  const labelBySeat = useMemo(() => {
    const m = new Map<number, Opponent>()
    st?.opponents.forEach((o) => m.set(o.seat - 1, o))
    return m
  }, [st])

  async function deal() {
    setBusy(true)
    setError(null)
    setCoach(null)
    try {
      const next = await playApi.newHand({ bots, seed })
      setEnv(next)
      setSeed((s) => s + 1)
      primeRaise(next.state)
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  function primeRaise(state: PlayState) {
    if (state.legal?.can_raise) {
      const pot = state.pot
      const target = Math.min(
        state.legal.max_raise_to,
        Math.max(state.legal.min_raise_to, state.to_call + Math.round(pot * 0.66)),
      )
      setRaiseTo(target)
    }
  }

  async function act(kind: ActionKind, amount = 0) {
    if (!sid) return
    setBusy(true)
    setError(null)
    try {
      const next = await playApi.act(sid, kind, amount)
      setEnv(next)
      primeRaise(next.state)
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
      const r = await playApi.coach(s)
      setCoach(r.coaching)
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setCoachBusy(false)
    }
  }

  const legal = st?.legal
  const heroTurn = !!st && !st.complete && !!legal
  const bbStr = (chips: number) => `${(chips / bb).toFixed(1)}bb`

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
      <div>
        {/* setup bar */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[0.64rem] uppercase tracking-[0.18em] text-muted">Seat the table</span>
          {bots.map((b, i) => (
            <select
              key={i}
              value={b}
              onChange={(e) => setBots((prev) => prev.map((p, j) => (j === i ? e.target.value : p)))}
              className="rounded-md border border-line bg-surface-2 px-2 py-1 text-[0.78rem] text-text"
            >
              {BOT_CHOICES.map((c) => (
                <option key={c.archetype} value={c.archetype}>
                  {c.label}
                </option>
              ))}
            </select>
          ))}
          <button
            type="button"
            onClick={deal}
            disabled={busy}
            className="rounded-full border border-brass bg-brass px-4 py-1.5 text-[0.78rem] font-semibold text-[#1a1407] disabled:opacity-50"
          >
            {st && !st.complete ? 'New hand' : 'Deal'}
          </button>
        </div>

        {/* felt */}
        <div className="relative mx-auto aspect-[16/11] w-full max-w-[720px]">
          <div className="absolute inset-[6%] rounded-[48%] border-[6px] border-[#1f3b2c] bg-[radial-gradient(120%_120%_at_50%_30%,#3aa56b,#236c44_60%,#1c5235)] shadow-[inset_0_0_60px_rgba(0,0,0,0.45)]" />
          {/* board + pot */}
          <div className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2">
            <div className="flex gap-1.5">
              {(st?.board ?? []).map((c, i) => (
                <PlayingCard key={i} card={c} />
              ))}
              {!st && <span className="font-mono text-[0.72rem] uppercase tracking-[0.18em] text-[#0d1f16]">deal to begin</span>}
            </div>
            {st && (
              <span className="rounded-full bg-[rgba(0,0,0,0.35)] px-3 py-0.5 font-mono text-[0.74rem] text-[#f0e6cf]">
                pot {bbStr(st.pot)}
              </span>
            )}
          </div>
          {/* seats */}
          {st &&
            SLOTS.map((pos, slot) => {
              const seat =
                slot === 0
                  ? st.hero_seat
                  : [0, 1, 2, 3, 4, 5].filter((s) => s !== st.hero_seat)[slot - 1]
              const isHero = seat === st.hero_seat
              const opp = labelBySeat.get(seat)
              return (
                <div key={slot} className="absolute" style={{ top: pos.top, left: pos.left }}>
                  <Seat
                    hero={isHero}
                    active={isHero && heroTurn}
                    label={isHero ? 'You' : opp?.style_label ?? `Seat ${seat + 1}`}
                    sub={isHero ? 'hero' : `seat ${seat + 1}`}
                    cards={isHero ? st.hero_hole ?? [undefined, undefined] : [undefined, undefined]}
                  />
                </div>
              )
            })}
        </div>

        {/* action bar */}
        <div className="mt-4 min-h-[68px] rounded-xl border border-line bg-surface p-3">
          {error && <div className="mb-2 text-[0.8rem] text-[#e0607a]">{error}</div>}
          {!st && <div className="text-[0.84rem] text-muted">Pick five styles and deal a hand.</div>}
          {st && st.complete && (
            <div className="text-[0.84rem] text-muted">
              Hand complete{coachBusy ? ' — coaching…' : coach ? '' : ' — fetching coaching…'}
            </div>
          )}
          {heroTurn && legal && (
            <div className="flex flex-wrap items-center gap-2">
              {legal.can_fold && (
                <button onClick={() => act('fold')} disabled={busy} className="rounded-md border border-line bg-surface-2 px-3 py-1.5 text-[0.8rem] text-text hover:border-brass-soft disabled:opacity-50">Fold</button>
              )}
              {legal.can_check && (
                <button onClick={() => act('check')} disabled={busy} className="rounded-md border border-line bg-surface-2 px-3 py-1.5 text-[0.8rem] text-text hover:border-brass-soft disabled:opacity-50">Check</button>
              )}
              {legal.can_call && (
                <button onClick={() => act('call')} disabled={busy} className="rounded-md border border-line bg-surface-2 px-3 py-1.5 text-[0.8rem] text-text hover:border-brass-soft disabled:opacity-50">
                  Call {bbStr(legal.call_chips)}
                </button>
              )}
              {legal.can_raise && (
                <div className="ml-auto flex items-center gap-2">
                  <input
                    type="range"
                    min={legal.min_raise_to}
                    max={legal.max_raise_to}
                    value={raiseTo}
                    onChange={(e) => setRaiseTo(Number(e.target.value))}
                    className="w-40 accent-brass"
                  />
                  <button
                    onClick={() => act('raise', raiseTo)}
                    disabled={busy}
                    className="rounded-md border border-brass bg-brass px-3 py-1.5 text-[0.8rem] font-semibold text-[#1a1407] disabled:opacity-50"
                  >
                    Raise to {bbStr(raiseTo)}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* coaching column */}
      <aside>
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
