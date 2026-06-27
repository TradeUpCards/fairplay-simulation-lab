import { useState, type ReactNode } from 'react'
import pokerTable from '../assets/poker-table.png'
import type { OperatorTableDetail } from '../data/types'
import { ARCH_AVATAR, SeatAvatar, seatPositions } from './tableArt'
import { expandSeats, avatarFor, handleFor, stackFor, forecastFor } from '../lib/lobbyIdentity'

/**
 * In-flow table detail panel (lives in a reserved column beside the lobby — never
 * overlaps it). Two views via the header toggle: **Player view** is the player-safe
 * table preview (real felt + seat ring + neutral facts); **Pit-boss view** pulls
 * back the curtain — seats reveal their archetype, plus table health + term
 * breakdown, seating-risk, and the reasons a table is or isn't recommended. The
 * lobby itself never shows the curtain.
 */
const TERM_MAX: Record<string, number> = { P_pred: 45, P_frag: 25, P_clus: 30, P_bleed: 20 }
const TERM_LABEL: Record<string, string> = {
  P_pred: 'Predation', P_frag: 'Fragility', P_clus: 'Cluster', P_bleed: 'Bleed',
}

const RISK_TONE: Record<string, string> = {
  low: 'border-[#2f7d4a] bg-[#16341f] text-[#8be3a7]',
  medium: 'border-[#8a6d2f] bg-[#332a16] text-[#e3c98b]',
  high: 'border-[#8a3a3a] bg-[#341a1a] text-[#e38b8b]',
}

/** Composition chip tone — predators/sharks warm, vulnerable cool, rest neutral. */
function archTone(a: string): string {
  if (a === 'aggressive_predatory' || a === 'grinder' || a === 'solver_like')
    return 'border-[#8a3a3a] bg-[#2a1717] text-[#e3a08b]'
  if (a === 'new' || a === 'recreational' || a === 'promo_hunter')
    return 'border-[#2f6a8a] bg-[#16262f] text-[#8fd0ef]'
  return 'border-[#3a4757] bg-[#1c2028] text-[#b8c0cf]'
}

/** Seat ring on the real felt; `reveal` swaps neutral seats for archetype avatars. */
function MiniTable({ detail, reveal }: { detail: OperatorTableDetail; reveal: boolean }) {
  const seated = detail.composition.flatMap((c) => Array<string>(c.count).fill(c.archetype))
  const pos = seatPositions(detail.max_seats)
  return (
    <div className="relative mx-auto my-2 aspect-3/2 w-full max-w-[17rem]">
      <img
        src={pokerTable}
        className="absolute inset-0 h-full w-full rounded-[14px] object-cover"
        alt=""
        aria-hidden="true"
      />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center leading-tight">
        <div className="font-mono text-[0.62rem] text-[#f0e8d6] [text-shadow:0_1px_3px_rgba(0,0,0,0.7)]">
          {detail.table_id}
        </div>
        <div className="text-[0.6rem] text-[#dccf9f] [text-shadow:0_1px_3px_rgba(0,0,0,0.7)]">
          {detail.seated_count}/{detail.max_seats}
        </div>
      </div>
      {pos.map((p, i) => {
        const arch = seated[i]
        return (
          <div
            key={i}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left: p.left, top: p.top }}
          >
            {!arch ? (
              <span className="flex h-7 w-7 items-center justify-center rounded-full border border-dashed border-[#3a4757] bg-[rgba(0,0,0,0.45)] text-[0.7rem] text-[#7a828e]">
                +
              </span>
            ) : reveal ? (
              <SeatAvatar archetype={arch} label={`${detail.table_id}-${i}`} size="sm" />
            ) : (
              <span className="flex h-7 w-7 items-center justify-center rounded-full border border-[#4a5260] bg-[#39414c] text-[0.8rem] text-[#aeb6c2]">
                🧑
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

function ViewTab({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-2.5 py-0.5 text-[0.66rem] font-semibold tracking-wide ${
        active ? 'bg-brass text-[#1a1407]' : 'text-muted hover:text-text'
      }`}
    >
      {children}
    </button>
  )
}

/**
 * The seated players as large portraits. `reveal=false` (player view) shows only
 * face + handle + stack — NO archetype, ever (the wall). `reveal=true` (pit-boss)
 * adds the archetype glyph + tone and an illustrative sit-time forecast.
 */
function SeatList({ detail, reveal }: { detail: OperatorTableDetail; reveal: boolean }) {
  const seats = expandSeats(detail.table_id, detail.composition)
  if (seats.length === 0) {
    return <p className="text-[0.74rem] text-[#6f7682]">Empty table — no one seated yet.</p>
  }
  return (
    <ul className="space-y-1.5" aria-label={reveal ? 'who is seated (operator)' : 'who is seated'}>
      {seats.map((s) => (
        <li
          key={s.id}
          data-testid="seat-row"
          {...(reveal ? { 'data-archetype': s.archetype } : {})}
          className="flex items-center gap-2.5 rounded-md border border-[#23262d] bg-[rgba(0,0,0,0.22)] px-2 py-1.5"
        >
          <SeatAvatar
            archetype={reveal ? s.archetype : undefined}
            label={s.id}
            imageUrl={avatarFor(s.id)}
            size="lg"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-[0.86rem] font-semibold text-[#f3ece0]">
                {handleFor(s.id)}
              </span>
              <span className="font-mono text-[0.74rem] text-[#cdb98a]">${stackFor(s.id)}</span>
            </div>
            {reveal ? (
              <div className="flex flex-wrap items-center gap-x-2 text-[0.7rem]">
                <span className={`rounded-full border px-1.5 py-[0.05rem] ${archTone(s.archetype)}`}>
                  {ARCH_AVATAR[s.archetype] ?? ''} {s.archetype.replace(/_/g, ' ')}
                </span>
                <span className="text-[#7e8694]">~{forecastFor(s.id, s.archetype)} min (est.)</span>
              </div>
            ) : (
              <div className="text-[0.7rem] text-[#7e8694]">in the game</div>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

export function LobbySidecar({
  detail,
  onClose,
  initialCurtain = false,
}: {
  detail: OperatorTableDetail
  onClose: () => void
  initialCurtain?: boolean
}) {
  const [curtain, setCurtain] = useState(initialCurtain)
  const band = detail.band ?? '—'
  const rec =
    detail.badge === 'recommended'
      ? 'Recommended'
      : detail.badge === 'good_fit'
        ? 'Good fit'
        : detail.full
          ? 'Full — no open seat'
          : 'Not recommended'

  return (
    <aside
      className="flex min-h-0 w-full flex-1 flex-col overflow-y-auto rounded-md border border-[#2a2e36] bg-[#0e1014]"
      aria-label="table detail"
    >
      <div className="sticky top-0 z-10 border-b border-[#23262d] bg-[#0e1014] px-3 py-2.5">
        <div className="flex items-start justify-between">
          <div>
            <div className="font-mono text-[1rem] font-semibold text-[#f3ece0]">{detail.table_id}</div>
            <div className="text-[0.72rem] text-[#a9b0bb]">
              {detail.stakes} · {detail.seated_count}/{detail.max_seats} · {detail.open_seats} open
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex gap-0.5 rounded-full border border-line bg-surface-2 p-0.5">
              <ViewTab active={!curtain} onClick={() => setCurtain(false)}>
                Player
              </ViewTab>
              <ViewTab active={curtain} onClick={() => setCurtain(true)}>
                Pit-boss
              </ViewTab>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="close"
              className="rounded-md border border-[#3a3f47] px-1.5 py-0.5 text-[0.85rem] text-[#b8c0cf] hover:border-brass hover:text-brass"
            >
              ×
            </button>
          </div>
        </div>
      </div>

      <div className="px-3 py-2 text-[0.8rem]">
        <MiniTable detail={detail} reveal={curtain} />

        {!curtain ? (
          <div className="mt-1 space-y-2">
            <p className="text-[0.74rem] text-[#a9b0bb]">
              {detail.seated_count} seated · {detail.open_seats} open seat
              {detail.open_seats === 1 ? '' : 's'}
              {detail.full ? ' · table full' : ''}
            </p>
            <SeatList detail={detail} reveal={false} />
            <p className="text-[0.68rem] leading-snug text-[#6f7682]">
              The neutral preview a player sees — handles and stacks only. Switch to{' '}
              <span className="text-[#8b8276]">Pit-boss</span> to reveal who's seated and why this
              table is ranked where it is (operator-only).
            </p>
          </div>
        ) : (
          <div className="mt-1 space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[#8b8276]">Routing:</span>
              <span className="font-semibold text-[#f3ece0]">{rec}</span>
              {detail.seating_risk && (
                <span
                  className={`rounded-full border px-1.5 py-[0.05rem] text-[0.7rem] ${
                    RISK_TONE[detail.seating_risk] ?? RISK_TONE.medium
                  }`}
                >
                  seating risk: {detail.seating_risk}
                </span>
              )}
              {detail.rank != null && (
                <span className="text-[0.72rem] text-[#6f7682]">rank {detail.rank}</span>
              )}
            </div>

            {detail.health != null && (
              <div>
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-[#8b8276]">Table health</span>
                  <span className="text-[#f3ece0]">
                    <span className="text-[1.05rem] font-semibold">{detail.health}</span>
                    <span className="ml-1 text-[0.72rem] text-[#a9b0bb]">/ 100 · {band}</span>
                  </span>
                </div>
                <div className="space-y-1">
                  {detail.terms &&
                    Object.entries(TERM_MAX).map(([k, max]) => {
                      const v = detail.terms?.[k] ?? 0
                      return (
                        <div key={k} className="flex items-center gap-2">
                          <span className="w-16 text-[0.68rem] text-[#8b8276]">{TERM_LABEL[k]}</span>
                          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#1c2028]">
                            <span
                              className="block h-full rounded-full bg-[#c98b93]"
                              style={{ width: `${Math.min(100, (v / max) * 100)}%` }}
                            />
                          </span>
                          <span className="w-10 text-right text-[0.66rem] text-[#6f7682]">
                            {Math.round(v)}/{max}
                          </span>
                        </div>
                      )
                    })}
                </div>
              </div>
            )}

            <div>
              <div className="mb-1.5 text-[#8b8276]">Who's seated</div>
              <SeatList detail={detail} reveal />
            </div>

            {detail.reasons && detail.reasons.length > 0 && (
              <div>
                <div className="mb-1 text-[#8b8276]">Why this rank</div>
                <ul className="space-y-1.5">
                  {detail.reasons.map((r) => (
                    <li key={r.code} className="text-[0.74rem] leading-snug text-[#b8c0cf]">
                      <span className="text-[#8fd0ef]">{r.code.replace(/_/g, ' ')}</span> — {r.detail}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="border-t border-[#23262d] pt-2 text-[0.68rem] leading-snug text-[#6f7682]">
              Operator-only — the reasoning behind the ranking. Players never see scores or risk
              language.
            </p>
          </div>
        )}
      </div>
    </aside>
  )
}
