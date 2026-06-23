import { useEffect, useState } from 'react'
import { safeLoad } from '../data/shim'
import type { LoadState } from '../data/loadState'

/**
 * React binding for the data layer. Starts in `loading`, then resolves to the
 * shared `LoadState` via `safeLoad` (so a failed source never crashes a view).
 *
 * Contract-2 is frozen, so this is a one-shot load on mount; pass a stable
 * module-level `loader` reference — it is intentionally not in the dep array.
 */
export function useResource<T>(
  loader: () => Promise<T>,
  isEmpty?: (data: T) => boolean,
): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ status: 'loading' })

  useEffect(() => {
    let alive = true
    void safeLoad(loader, isEmpty).then((next) => {
      if (alive) setState(next)
    })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return state
}
