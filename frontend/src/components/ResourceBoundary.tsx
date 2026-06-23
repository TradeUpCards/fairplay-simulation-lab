import type { ReactNode } from 'react'
import type { LoadState } from '../data/loadState'

interface ResourceBoundaryProps<T> {
  state: LoadState<T>
  /** Rendered only when data has loaded. */
  children: (data: T) => ReactNode
  loading?: ReactNode
  empty?: ReactNode
  error?: (error: Error) => ReactNode
  /** Noun used in the default loading/empty/error copy (e.g. "table health"). */
  label?: string
}

/**
 * The single place the four load states render, so loading / empty / error look
 * consistent across every view and a failed source degrades gracefully instead
 * of throwing. Views supply only the success branch via `children`.
 */
export function ResourceBoundary<T>({
  state,
  children,
  loading,
  empty,
  error,
  label = 'data',
}: ResourceBoundaryProps<T>): ReactNode {
  switch (state.status) {
    case 'loading':
      return loading ?? <p className="text-muted">Loading {label}…</p>
    case 'empty':
      return empty ?? <p className="text-muted">No {label} available.</p>
    case 'error':
      return error
        ? error(state.error)
        : (
            <p className="text-[#ff9b9b]" role="alert">
              Couldn’t load {label}: {state.error.message}
            </p>
          )
    case 'ok':
      return children(state.data)
  }
}
