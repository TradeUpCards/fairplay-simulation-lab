import logo from '../assets/fairplay-iq-logo-brass.svg'

export type ViewMode = 'operator' | 'player'

/**
 * App header — the brass rail atop the console. The FairPlay IQ wordmark anchors
 * it; the Operator|Player toggle is the app's primary navigation and makes the
 * player/operator wall a visible boundary (player screens never expose scores).
 * A monospace "synthetic data" status states the responsible-use framing up
 * front. Deliberately quiet — the app's signature is the seat-ring, not the chrome.
 */
export function Header({
  mode,
  onModeChange,
}: {
  mode: ViewMode
  onModeChange: (mode: ViewMode) => void
}) {
  return (
    <header className="app-header" role="banner">
      <div className="app-header-inner">
        <div className="brand">
          <img className="brand-logo" src={logo} alt="FairPlay IQ" />
          <span className="brand-divider" aria-hidden="true" />
          <span className="brand-descriptor">Simulation Lab</span>
        </div>

        <div className="mode-toggle" role="tablist" aria-label="Audience view">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'operator'}
            className={`mode-tab${mode === 'operator' ? ' is-active' : ''}`}
            onClick={() => onModeChange('operator')}
          >
            Pit Boss
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'player'}
            className={`mode-tab${mode === 'player' ? ' is-active' : ''}`}
            onClick={() => onModeChange('player')}
          >
            Player
          </button>
        </div>

        <p className="header-status">
          <span className="status-dot" aria-hidden="true" />
          Synthetic data
        </p>
      </div>
    </header>
  )
}
