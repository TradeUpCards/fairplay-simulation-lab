import { useEffect, useState } from 'react'

/**
 * Tiny hash router. The app is a static, `base: './'` bundle (a presenter opens
 * it from any host path or `file://`), so a hash route is the portable way to
 * give the dashboard its own URL — `#/dashboard` — without a server rewrite.
 */
export type Route = 'home' | 'dashboard' | 'slideshow'

function parse(): Route {
  const path = window.location.hash.replace(/^#\/?/, '')
  if (path === 'dashboard') return 'dashboard'
  // The slideshow deep-links a slide index as `#/slideshow/3`, so match the
  // prefix too — the deck reads the trailing number itself (see views/Slideshow).
  if (path === 'slideshow' || path.startsWith('slideshow/')) return 'slideshow'
  return 'home'
}

export function navigate(route: Route): void {
  if (route === 'dashboard') window.location.hash = '#/dashboard'
  else if (route === 'slideshow') window.location.hash = '#/slideshow'
  else window.location.hash = '#/'
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
