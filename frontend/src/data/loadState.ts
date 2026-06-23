/**
 * The shared load-state convention every view uses for its data binding.
 * One vocabulary for the four things a data read can be, so loading / empty /
 * error look consistent across the simulator, pit-boss views, lobby, and eval.
 */
export type LoadState<T> =
  | { status: 'loading' }
  | { status: 'ok'; data: T }
  | { status: 'empty' }
  | { status: 'error'; error: Error }

/**
 * Run a loader and resolve to a `LoadState` — this NEVER throws. A rejected
 * loader (e.g. a future `fetch()` against a down API) becomes
 * `{ status: 'error' }`; an `isEmpty` hit becomes `{ status: 'empty' }`. This is
 * what lets a view degrade gracefully on a missing source instead of crashing
 * (U1 verification / origin AE5).
 */
export async function safeLoad<T>(
  loader: () => Promise<T>,
  isEmpty: (data: T) => boolean = () => false,
): Promise<LoadState<T>> {
  try {
    const data = await loader()
    if (data == null) {
      return { status: 'error', error: new Error('loader returned no data') }
    }
    if (isEmpty(data)) {
      return { status: 'empty' }
    }
    return { status: 'ok', data }
  } catch (err) {
    return { status: 'error', error: err instanceof Error ? err : new Error(String(err)) }
  }
}
