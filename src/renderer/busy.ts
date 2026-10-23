// Saying "working on it" before a long synchronous step, not after.
//
// The slow things here -- indexing a table, redrawing a scatter of every
// frame, hiding a selection out of one -- are synchronous: once they start,
// nothing paints until they finish. So the loading message has to be set and
// *painted* first, which is what waiting two frames buys. The plate's ring and
// sweep animate on the compositor, so they keep moving while the main thread
// is busy.

import { useStore } from './store'

/** Above this many rows a redraw is slow enough to deserve the overlay. */
export const LARGE_ROWS = 20_000

/** Resolve after `n` animation frames, so a state change paints first. */
export function nextFrames(n: number): Promise<void> {
  return new Promise((done) => {
    // A hidden window gets no frames; the timeout keeps the work moving.
    const timer = setTimeout(done, 100)
    const step = (left: number) =>
      left === 0
        ? (clearTimeout(timer), done())
        : requestAnimationFrame(() => step(left - 1))
    step(n)
  })
}

/** Clear `label`, unless something else has put up its own message since. */
export function clearLoading(label: string): void {
  const { loading, setLoading } = useStore.getState()
  if (loading === label) {
    setLoading(null)
  }
}

/**
 * Run `work` with the loading overlay showing `label`.
 *
 * Shows the message, lets it paint, runs the work, and gives React and
 * Plotly the frames to draw what it changed before taking the message down.
 */
export async function withLoading<T>(label: string, work: () => T | Promise<T>): Promise<T> {
  useStore.getState().setLoading(label)
  await nextFrames(2)
  try {
    return await work()
  } finally {
    await nextFrames(2)
    clearLoading(label)
  }
}

/** `1234567` -> `1.2M`, `45678` -> `45.7k`: a count for a one-line message. */
export function countOf(n: number): string {
  if (n >= 1e6) {
    return `${(n / 1e6).toFixed(1)}M`
  }
  if (n >= 1e4) {
    return `${(n / 1e3).toFixed(1)}k`
  }
  return n.toLocaleString()
}
