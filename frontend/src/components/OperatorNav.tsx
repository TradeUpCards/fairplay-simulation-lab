export type OperatorView = 'console' | 'simulator' | 'eval'

/**
 * The order is the demo spine inside the back of house: the lobby hands off to
 * the pit-boss **Console** (review/override), which opens the **Simulator**
 * (Standard vs FairPlay), which is proven out in **Eval**. A quiet tab bar under
 * the brass header — subordinate to the Operator|Player toggle, which is still
 * the primary nav.
 */
const TABS: { id: OperatorView; label: string; hint: string }[] = [
  { id: 'console', label: 'Console', hint: 'Pit-boss review' },
  { id: 'simulator', label: 'Simulator', hint: 'Standard vs FairPlay' },
  { id: 'eval', label: 'Eval', hint: 'Evidence & proof' },
]

export function OperatorNav({
  view,
  onViewChange,
}: {
  view: OperatorView
  onViewChange: (view: OperatorView) => void
}) {
  return (
    <nav className="operator-nav" aria-label="Operator views">
      <div className="operator-tabs" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={view === tab.id}
            className={`operator-tab${view === tab.id ? ' is-active' : ''}`}
            onClick={() => onViewChange(tab.id)}
          >
            <span className="operator-tab-label">{tab.label}</span>
            <span className="operator-tab-hint">{tab.hint}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}
