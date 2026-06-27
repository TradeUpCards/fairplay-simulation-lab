import { useState } from 'react'
import type { OperatorTableDetail } from '../data/types'

/**
 * Two-stage table sidecar. Stage 1 is the player-safe **table preview** — a seat
 * ring + neutral facts (stakes, occupancy), what a player could see. Stage 2 is
 * the operator **curtain**, opened by an explicit Pit-boss button: it reveals the
 * seated archetypes, table health + term breakdown, seating-risk, and the reasons
 * a table is or isn't recommended. The player lobby never shows the curtain on its
 * own — it's an operator reveal.
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

/** Archetype chip tone — predators/sharks warm, vulnerable cool, rest neutral. */
function archTone(a: string): string {
  if (a === 'aggressive_predatory' || a === 'grinder' || a === 'solver_like')
    return 'border-[#8a3a3a] bg-[#2a1717] text-[#e3a08b]'
  if (a === 'new' || a === 'recreational' || a === 'promo_hunter')
    return 'border-[#2f6a8a] bg-[#16262f] text-[#8fd0ef]'
  return 'border-[#3a4757] bg-[#1c2028] text-[#b8c0cf]'
}

const ARCH_EMOJI: Record<string, string> = {
  aggressive_predatory: '🦈',
  grinder: '⚙️',
  solver_like: '🧮',
  new: '🐟',
  recreational: '🎉',
  promo_hunter: '🎟️',
  regular: '🪙',
  healthy_anchor: '⚓',
  shared_device_household: '📱',
  cluster_member: '🔗',
  bot_like: '🤖',
  unknown: '❔',
}

/**
 * Seat ring built from the seated composition. `reveal=false` shows neutral
 * occupied/empty seats (player-safe); `reveal=true` shows the archetype of each seat.
 */
function MiniTable({ detail, reveal }: { detail: OperatorTableDetail; reveal: boolean }) {
  const seated = detail.composition.flatMap((c) => Array<string>(c.count).fill(c.archetype))
  const n = Math.max(detail.max_seats, 1)
  return (
    <div className="relative mx-auto my-2 h-28 w-full max-w-[17rem]">
      <div className="absolute left-1/2 top-1/2 h-[66%] w-[78%] -translate-x-1/2 -translate-y-1/2 rounded-[999px] border border-[#2f5d3f] bg-[radial-gradient(ellipse_at_center,#1c4a30,#0e2a1b)]" />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center leading-tight">
        <div className="font-mono text-[0.62rem] text-[#cfe6d4]">{detail.table_id}</div>
        <div className="text-[0.6rem] text-[#8fbf9a]">
          {detail.seated_count}/{detail.max_seats}
        </div>
      </div>
      {Array.from({ length: n }).map((_, i) => {
        const ang = ((-90 + i * (360 / n)) * Math.PI) / 180
        const x = 50 + 44 * Math.cos(ang)
        const y = 50 + 42 * Math.sin(ang)
        const arch = seated[i]
        return (
          <div
            key={i}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${x}%`, top: `${y}%` }}
          >
            {!arch ? (
              <span className="flex h-7 w-7 items-center justify-center rounded-full border border-dashed border-[#3a4757] text-[0.7rem] text-[#5b626c]">
                +
              </span>
            ) : reveal ? (
              <span
                title={arch.replace(/_/g, ' ')}
                className={`flex h-7 w-7 items-center justify-center rounded-full border text-[0.9rem] ${archTone(arch)}`}
              >
                {ARCH_EMOJI[arch] ?? '•'}
              </span>
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

export function LobbySidecar({
  detail,
  onClose,
}: {
  detail: OperatorTableDetail
  onClose: () => void
}) {
  const [curtain, setCurtain] = useState(false)
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
      className="fixed right-0 top-0 z-50 flex h-screen w-[23rem] flex-col overflow-y-auto border-l border-[#2a2e36] bg-[#0e1014] shadow-[0_0_40px_rgba(0,0,0,0.6)]"
      aria-label="table detail"
    >
      <div className="flex items-start justify-between border-b border-[#23262d] px-4 py-3">
        <div>
          <div className="text-[0.66rem] uppercase tracking-[0.14em] text-[#8b8276]">
            {curtain ? 'Pit-boss view · the curtain' : 'Table preview'}
          </div>
          <div className="mt-0.5 font-mono text-[1.05rem] font-semibold text-[#f3ece0]">
            {detail.table_id}
          </div>
          <div className="text-[0.74rem] text-[#a9b0bb]">
            {detail.stakes} · {detail.seated_count}/{detail.max_seats} seated · {detail.open_seats}{' '}
            open
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="close"
          className="rounded-md border border-[#3a3f47] px-2 py-0.5 text-[0.9rem] text-[#b8c0cf] hover:border-brass hover:text-brass"
        >
          ×
        </button>
      </div>

      <div className="px-4 py-3 text-[0.8rem]">
        <MiniTable detail={detail} reveal={curtain} />

        {!curtain ? (
          <div className="mt-1 space-y-3">
            <p className="text-[0.74rem] text-[#a9b0bb]">
              {detail.seated_count} seated · {detail.open_seats} open seat
              {detail.open_seats === 1 ? '' : 's'}
              {detail.full ? ' · table full' : ''}
            </p>
            <button
              type="button"
              onClick={() => setCurtain(true)}
              className="w-full rounded-md border border-brass bg-[rgba(224,189,118,0.12)] px-3 py-2 text-[0.78rem] font-semibold text-brass transition hover:bg-[rgba(224,189,118,0.2)]"
            >
              🔍 Pit-boss view — why this seating?
            </button>
            <p className="text-[0.68rem] leading-snug text-[#6f7682]">
              Players see only this neutral preview. The pit-boss reveal is operator-only.
            </p>
          </div>
        ) : (
          <div className="mt-1 space-y-4">
            <button
              type="button"
              onClick={() => setCurtain(false)}
              className="text-[0.72rem] text-[#8b8276] hover:text-brass"
            >
              ‹ back to table preview
            </button>

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
              <div className="mb-1 text-[#8b8276]">Who's seated</div>
              <div className="flex flex-wrap gap-1.5">
                {detail.composition.length === 0 && (
                  <span className="text-[0.74rem] text-[#6f7682]">empty table</span>
                )}
                {detail.composition.map((c) => (
                  <span
                    key={c.archetype}
                    className={`rounded-full border px-1.5 py-[0.05rem] text-[0.7rem] ${archTone(c.archetype)}`}
                  >
                    {ARCH_EMOJI[c.archetype] ?? ''} {c.count}× {c.archetype.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
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
              Operator-only — the reasoning behind the lobby ranking. Players never see scores or
              risk language.
            </p>
          </div>
        )}
      </div>
    </aside>
  )
}
