import type { HealthTerms } from '../data/types'
import { TERM_CAP, type TermKey } from '../lib/health'

const TERMS: { key: TermKey; label: string }[] = [
  { key: 'P_pred', label: 'Predation' },
  { key: 'P_frag', label: 'Fragility' },
  { key: 'P_clus', label: 'Cluster' },
  { key: 'P_bleed', label: 'Bleed' },
]

/** The four health-penalty terms as labelled bars (each scaled to its own cap). */
export function TermBars({ terms }: { terms: HealthTerms }) {
  return (
    <div className="grid min-w-[220px] gap-[0.2rem]" aria-label="health penalty terms">
      {TERMS.map(({ key, label }) => (
        <div className="grid grid-cols-[4.5rem_1fr_2rem] items-center gap-[0.4rem] text-[0.72rem] text-muted" key={key}>
          <span className="text-right">{label}</span>
          <span className="h-1.5 overflow-hidden rounded-[3px] bg-line">
            <span
              className="block h-full bg-[#5f7fd9]"
              style={{ width: `${(terms[key] / TERM_CAP[key]) * 100}%` }}
            />
          </span>
          <span className="tabular-nums text-[#c3c9d6]">{terms[key]}</span>
        </div>
      ))}
    </div>
  )
}
