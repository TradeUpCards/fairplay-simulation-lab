import logo from '../assets/fairplay-iq-logo-brass.svg'

/**
 * App header — the brass rail at the top of the operator console. The FairPlay
 * IQ wordmark anchors it on the left; a monospace status on the right states the
 * one thing a reviewer should know up front: this runs on synthetic data
 * (responsible-use framing, never real detection). Deliberately quiet — the
 * app's signature element is the seat-ring, not the chrome.
 */
export function Header() {
  return (
    <header className="app-header" role="banner">
      <div className="app-header-inner">
        <div className="brand">
          <img className="brand-logo" src={logo} alt="FairPlay IQ" />
          <span className="brand-divider" aria-hidden="true" />
          <span className="brand-descriptor">Simulation Lab</span>
        </div>
        <p className="header-status">
          <span className="status-dot" aria-hidden="true" />
          Synthetic data
        </p>
      </div>
    </header>
  )
}
