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
    <div className="term-bars" aria-label="health penalty terms">
      {TERMS.map(({ key, label }) => (
        <div className="term-row" key={key}>
          <span className="term-name">{label}</span>
          <span className="term-track">
            <span className="term-fill" style={{ width: `${(terms[key] / TERM_CAP[key]) * 100}%` }} />
          </span>
          <span className="term-num">{terms[key]}</span>
        </div>
      ))}
    </div>
  )
}
