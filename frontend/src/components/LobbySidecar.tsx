import { type ReactNode } from 'react'
import pokerTable from '../assets/poker-table.png'
import type { OperatorTableDetail, Archetype, HealthBand, HealthTerms } from '../data/types'
import { computePtl } from '../lib/ptl'
import { ptlTone, type PtlTone } from '../lib/table'
import { ARCH_AVATAR, SeatAvatar, seatPositions } from './tableArt'
import {
  expandSeats,
  avatarFor,
  handleFor,
  stackFor,
  forecastFor,
  archetypeBadge,
} from '../lib/lobbyIdentity'

/** A round identity face with an optional small cartoon archetype badge pinned at
 *  its lower-right (the pit-boss "reveal" — face stays the same, badge denotes role). */
function SeatFace({
  id,
  archetype,
  reveal,
  size,
}: {
  id: string
  archetype: string
  reveal: boolean
  size: 'sm' | 'md' | 'lg'
}) {
  const badge = reveal ? archetypeBadge(archetype) : null
  const badgeDim = size === 'lg' ? 'h-7 w-7' : size === 'md' ? 'h-6 w-6' : 'h-4 w-4'
  return (
    <div className="relative shrink-0">
      <SeatAvatar label={id} imageUrl={avatarFor(id)} size={size} />
      {badge && (
        <img
          src={badge}
          alt=""
          title={archetype.replace(/_/g, ' ')}
          className={`absolute -bottom-1 -right-1.5 ${badgeDim} rounded-full border-2 border-[#0e1014] bg-[#0e1014] object-cover`}
        />
      )}
    </div>
  )
}

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

// PTL (propensity to leave) heat — reuses the dedicated pit-boss model so the lobby
// curtain shows the same signal: vulnerable seats run hot at a fragile/predatory table.
const PTL_DOT: Record<PtlTone, string> = {
  pending: 'bg-[#4a5466]',
  cool: 'bg-[#5fcf8a]',
  warm: 'bg-[#e3b25f]',
  hot: 'bg-[#ff7b7b]',
}
const PTL_TEXT: Record<PtlTone, string> = {
  pending: 'text-faint',
  cool: 'text-[#5fcf8a]',
  warm: 'text-[#e3b25f]',
  hot: 'text-[#ff7b7b]',
}
const PTL_LABEL: Record<PtlTone, string> = {
  pending: '—',
  cool: 'staying',
  warm: 'restless',
  hot: 'about to leave',
}

function seatHeat(
  detail: OperatorTableDetail,
  archetype: string,
): { tone: PtlTone; why: string } | null {
  if (!detail.terms || !detail.band) return null
  try {
    const r = computePtl(archetype as Archetype, {
      table_id: detail.table_id,
      band: detail.band as HealthBand,
      terms: detail.terms as unknown as HealthTerms,
    })
    if (Number.isNaN(r.ptl)) return null
    return { tone: ptlTone(r.ptl), why: r.reason_codes[1]?.detail ?? r.reason_codes[0]?.detail ?? '' }
  } catch {
    return null
  }
}

/** Composition chip tone — predators/sharks warm, vulnerable cool, rest neutral. */
function archTone(a: string): string {
  if (a === 'aggressive_predatory' || a === 'grinder' || a === 'solver_like')
    return 'border-[#8a3a3a] bg-[#2a1717] text-[#e3a08b]'
  if (a === 'new' || a === 'recreational' || a === 'promo_hunter')
    return 'border-[#2f6a8a] bg-[#16262f] text-[#8fd0ef]'
  return 'border-[#3a4757] bg-[#1c2028] text-[#b8c0cf]'
}

/** Seat ring on the real felt — each seat is a round avatar portrait sitting above
 *  and behind a name + balance card (its bottom tucked behind the card), pushed out
 *  toward the rail. Same synthetic ids as the seat list, so they always match. */
function MiniTable({
  detail,
  reveal,
  large = false,
}: {
  detail: OperatorTableDetail
  reveal: boolean
  large?: boolean
}) {
  const seats = expandSeats(detail.table_id, detail.composition)
  const pos = seatPositions(detail.max_seats, 50, 44)
  return (
    <div
      className={`relative mx-auto aspect-3/2 w-full ${large ? 'my-2 max-w-[16rem]' : 'my-6 max-w-[17rem]'}`}
    >
      <img
        src={pokerTable}
        className="absolute inset-0 h-full w-full rounded-[14px] object-cover"
        alt=""
        aria-hidden="true"
      />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center leading-tight">
        <div className="font-mono text-[0.62rem] text-[#f0e8d6] [text-shadow:0_1px_3px_rgba(0,0,0,0.7)]">
          {detail.table_id.replace('LR-', 'T-')}
        </div>
        <div className="text-[0.6rem] text-[#dccf9f] [text-shadow:0_1px_3px_rgba(0,0,0,0.7)]">
          {detail.seated_count}/{detail.max_seats}
        </div>
      </div>
      {pos.map((p, i) => {
        const s = seats[i]
        return (
          <div
            key={i}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left: p.left, top: p.top }}
          >
            {!s ? (
              <span className="flex h-6 w-6 items-center justify-center rounded-full border border-dashed border-[#3a4757] bg-[rgba(0,0,0,0.45)] text-[0.65rem] text-[#7a828e]">
                +
              </span>
            ) : (
              <div className="flex w-[3.6rem] flex-col items-center">
                <div className="relative">
                  <SeatAvatar label={s.id} imageUrl={avatarFor(s.id)} size="md" />
                  {reveal &&
                    (() => {
                      const h = seatHeat(detail, s.archetype)
                      if (!h) return null
                      return (
                        <span
                          title={`${PTL_LABEL[h.tone]} — ${h.why}`}
                          className={`absolute -right-0.5 -top-0.5 z-20 h-3.5 w-3.5 rounded-full border-2 border-[#0e1014] ${PTL_DOT[h.tone]}`}
                        />
                      )
                    })()}
                </div>
                <div className="relative -mt-2 z-10 w-full rounded-[5px] border border-[#3a4555] bg-[rgba(8,10,14,0.92)] px-1 pb-[0.12rem] pt-[0.18rem] text-center leading-tight shadow-[0_1px_4px_rgba(0,0,0,0.55)]">
                  <div className="truncate text-[0.55rem] font-semibold text-[#e7e0d2]">
                    {handleFor(s.id)}
                  </div>
                  <div className="font-mono text-[0.55rem] text-[#cdb98a]">${stackFor(s.id)}</div>
                  {reveal && archetypeBadge(s.archetype) && (
                    <img
                      src={archetypeBadge(s.archetype) as string}
                      alt=""
                      title={s.archetype.replace(/_/g, ' ')}
                      className="absolute -right-2.5 -top-3 z-20 h-6 w-6 rounded-full border-2 border-[#0e1014] bg-[#0e1014] object-cover"
                    />
                  )}
                </div>
              </div>
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
function SeatList({
  detail,
  reveal,
  large = false,
}: {
  detail: OperatorTableDetail
  reveal: boolean
  large?: boolean
}) {
  const seats = expandSeats(detail.table_id, detail.composition)
  if (seats.length === 0) {
    return <p className="text-[0.74rem] text-[#6f7682]">Empty table — no one seated yet.</p>
  }
  const handleCls = large ? 'text-[1.08rem]' : 'text-[0.86rem]'
  const stackCls = large ? 'text-[0.94rem]' : 'text-[0.74rem]'
  const metaCls = large ? 'text-[0.92rem]' : 'text-[0.7rem]'
  return (
    <ul
      className={large ? 'space-y-2.5' : 'space-y-1.5'}
      aria-label={reveal ? 'who is seated (operator)' : 'who is seated'}
    >
      {seats.map((s) => (
        <li
          key={s.id}
          data-testid="seat-row"
          {...(reveal ? { 'data-archetype': s.archetype } : {})}
          className={`flex items-center rounded-md border border-[#23262d] bg-[rgba(0,0,0,0.22)] ${
            large ? 'gap-3 px-2.5 py-2' : 'gap-2.5 px-2 py-1.5'
          }`}
        >
          <SeatFace id={s.id} archetype={s.archetype} reveal={reveal} size="lg" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <span className={`truncate font-semibold text-[#f3ece0] ${handleCls}`}>
                {handleFor(s.id)}
              </span>
              <span className={`font-mono text-[#cdb98a] ${stackCls}`}>${stackFor(s.id)}</span>
            </div>
            {reveal ? (
              <div className={`flex flex-wrap items-center gap-x-2 gap-y-0.5 ${metaCls}`}>
                <span className={`rounded-full border px-1.5 py-[0.05rem] ${archTone(s.archetype)}`}>
                  {ARCH_AVATAR[s.archetype] ?? ''} {s.archetype.replace(/_/g, ' ')}
                </span>
                {(() => {
                  const h = seatHeat(detail, s.archetype)
                  if (!h) return null
                  return (
                    <span className="inline-flex items-center gap-1" title={h.why}>
                      <span className={`h-2 w-2 rounded-full ${PTL_DOT[h.tone]}`} />
                      <span className={PTL_TEXT[h.tone]}>{PTL_LABEL[h.tone]}</span>
                    </span>
                  )
                })()}
                <span className="text-[#7e8694]">
                  ~{forecastFor(s.id, s.archetype, detail.health)} min (est.)
                </span>
              </div>
            ) : (
              <div className={`text-[#7e8694] ${metaCls}`}>in the game</div>
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
  pitboss,
  onPitbossChange,
  expanded = false,
}: {
  detail: OperatorTableDetail
  onClose: () => void
  pitboss: boolean
  onPitbossChange: (v: boolean) => void
  expanded?: boolean
}) {
  const band = detail.band ?? '—'
  const rec =
    detail.badge === 'recommended'
      ? 'Recommended'
      : detail.badge === 'good_fit'
        ? 'Good fit'
        : detail.full
          ? 'Full — no open seat'
          : 'Not recommended'

  const routingLine = (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[#8b8276]">Routing:</span>
      <span className="font-semibold text-[#f3ece0]">{rec}</span>
      {detail.seating_risk && (
        <span
          className={`rounded-full border px-1.5 py-[0.05rem] ${expanded ? 'text-[0.85rem]' : 'text-[0.7rem]'} ${
            RISK_TONE[detail.seating_risk] ?? RISK_TONE.medium
          }`}
        >
          seating risk: {detail.seating_risk}
        </span>
      )}
      {detail.rank != null && (
        <span className={`text-[#6f7682] ${expanded ? 'text-[0.85rem]' : 'text-[0.72rem]'}`}>
          rank {detail.rank}
        </span>
      )}
    </div>
  )

  const healthBlock = detail.health != null && (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-[#8b8276]">Table health</span>
        <span className="text-[#f3ece0]">
          <span className={expanded ? 'text-[1.7rem] font-semibold' : 'text-[1.05rem] font-semibold'}>
            {detail.health}
          </span>
          <span className={`ml-1 text-[#a9b0bb] ${expanded ? 'text-[0.85rem]' : 'text-[0.72rem]'}`}>
            / 100 · {band}
          </span>
        </span>
      </div>
      <div className="space-y-1">
        {detail.terms &&
          Object.entries(TERM_MAX).map(([k, max]) => {
            const v = detail.terms?.[k] ?? 0
            return (
              <div key={k} className="flex items-center gap-2">
                <span className={`text-[#8b8276] ${expanded ? 'w-20 text-[0.85rem]' : 'w-16 text-[0.68rem]'}`}>
                  {TERM_LABEL[k]}
                </span>
                <span className={`${expanded ? 'h-2.5' : 'h-1.5'} flex-1 overflow-hidden rounded-full bg-[#1c2028]`}>
                  <span
                    className="block h-full rounded-full bg-[#c98b93]"
                    style={{ width: `${Math.min(100, (v / max) * 100)}%` }}
                  />
                </span>
                <span className={`text-right text-[#6f7682] ${expanded ? 'w-12 text-[0.82rem]' : 'w-10 text-[0.66rem]'}`}>
                  {Math.round(v)}/{max}
                </span>
              </div>
            )
          })}
      </div>
    </div>
  )

  const seatedBlock = (
    <div>
      <div className="mb-1.5 text-[#8b8276]">Who's seated</div>
      <SeatList detail={detail} reveal large={expanded} />
    </div>
  )

  const reasonsBlock = detail.reasons && detail.reasons.length > 0 && (
    <div>
      <div className="mb-1 text-[#8b8276]">Why this rank</div>
      <ul className={expanded ? 'space-y-2' : 'space-y-1.5'}>
        {detail.reasons.map((r) => (
          <li
            key={r.code}
            className={`leading-snug text-[#b8c0cf] ${expanded ? 'text-[0.95rem]' : 'text-[0.74rem]'}`}
          >
            <span className="text-[#8fd0ef]">{r.code.replace(/_/g, ' ')}</span> — {r.detail}
          </li>
        ))}
      </ul>
    </div>
  )

  const footer = (
    <p
      className={`border-t border-[#23262d] pt-2 leading-snug text-[#6f7682] ${
        expanded ? 'text-[0.82rem]' : 'text-[0.68rem]'
      }`}
    >
      Operator-only — the reasoning behind the ranking. Players never see scores or risk language.
    </p>
  )

  return (
    <aside
      className="flex min-h-0 w-full flex-1 flex-col overflow-y-auto rounded-md border border-[#2a2e36] bg-[#0e1014]"
      aria-label="table detail"
      data-expanded={expanded ? 'true' : undefined}
    >
      <div className="sticky top-0 z-10 border-b border-[#23262d] bg-[#0e1014] px-3 py-2.5">
        <div className="flex items-start justify-between">
          <div>
            <div className="font-mono text-[1rem] font-semibold text-[#f3ece0]">
              {detail.table_id.replace('LR-', 'T-')}
            </div>
            <div className="text-[0.72rem] text-[#a9b0bb]">
              {detail.stakes} · {detail.seated_count}/{detail.max_seats} · {detail.open_seats} open
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex gap-0.5 rounded-full border border-line bg-surface-2 p-0.5">
              <ViewTab active={!pitboss} onClick={() => onPitbossChange(false)}>
                Player
              </ViewTab>
              <ViewTab active={pitboss} onClick={() => onPitbossChange(true)}>
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

      <div className={`px-3 py-2 ${expanded ? 'text-[1rem]' : 'text-[0.8rem]'}`}>
        {!pitboss ? (
          <>
            <MiniTable detail={detail} reveal={false} />
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
          </>
        ) : expanded ? (
          // Focus mode — two columns: the felt + seats, and the analysis.
          <>
            <div className="grid gap-x-8 gap-y-4 xl:grid-cols-2">
              <div className="space-y-3">
                <MiniTable detail={detail} reveal large />
                {seatedBlock}
              </div>
              <div className="space-y-5">
                {routingLine}
                {healthBlock}
                {reasonsBlock}
              </div>
            </div>
            <div className="mt-3">{footer}</div>
          </>
        ) : (
          <>
            <MiniTable detail={detail} reveal />
            <div className="mt-1 space-y-4">
              {routingLine}
              {healthBlock}
              {seatedBlock}
              {reasonsBlock}
              {footer}
            </div>
          </>
        )}
      </div>
    </aside>
  )
}
