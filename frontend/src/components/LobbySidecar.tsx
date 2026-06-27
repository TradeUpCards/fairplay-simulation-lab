import type { OperatorTableDetail } from '../data/types'

/**
 * "Pull back the curtain" — the operator-side reasoning for a table the player
 * clicked in the lobby: composition, health score + term breakdown, seating-risk,
 * and why it's ranked where it is. This is OPERATOR content, shown only when an
 * operator opens it from the demo (the player lobby itself never shows scores).
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

export function LobbySidecar({
  detail,
  onClose,
}: {
  detail: OperatorTableDetail
  onClose: () => void
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

  return (
    <aside
      className="fixed right-0 top-0 z-50 flex h-screen w-[23rem] flex-col overflow-y-auto border-l border-[#2a2e36] bg-[#0e1014] shadow-[0_0_40px_rgba(0,0,0,0.6)]"
      aria-label="pit-boss table detail"
    >
      <div className="flex items-start justify-between border-b border-[#23262d] px-4 py-3">
        <div>
          <div className="text-[0.66rem] uppercase tracking-[0.14em] text-[#8b8276]">
            Pit-boss view · the curtain
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

      <div className="space-y-4 px-4 py-3 text-[0.8rem]">
        {/* recommendation */}
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

        {/* health */}
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

        {/* composition */}
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
                {c.count}× {c.archetype.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>

        {/* reasons */}
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
          risk language; this view is for the pit boss.
        </p>
      </div>
    </aside>
  )
}
