import { useEffect, useState } from 'react'

/**
 * Tiny hash router. The app is a static, `base: './'` bundle (a presenter opens
 * it from any host path or `file://`), so a hash route is the portable way to
 * give the dashboard its own URL — `#/dashboard` — without a server rewrite.
 */
export type Route = 'home' | 'dashboard'

function parse(): Route {
  return window.location.hash.replace(/^#\/?/, '') === 'dashboard' ? 'dashboard' : 'home'
}

export function navigate(route: Route): void {
  window.location.hash = route === 'dashboard' ? '#/dashboard' : '#/'
}

export function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(parse)
  useEffect(() => {
    const onChange = () => setRoute(parse())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}
