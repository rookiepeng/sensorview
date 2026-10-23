// What a load is doing, over the scene it is about to replace.
//
// A large table is seconds of reading and indexing, and until it lands the
// window still shows the previous log -- which reads as a click that did
// nothing. The welcome plate already says "Opening …" on an empty window, so
// this only shows once a case is open.

import { useStore } from '../store'

export function LoadingOverlay() {
  const loading = useStore((s) => s.loading)
  const frameCount = useStore((s) => s.frameCount)
  if (!loading || frameCount === 0) {
    return null
  }
  return (
    <div className="sv-loading" role="status" aria-live="polite">
      <div className="sv-loading-plate">
        <span className="sv-loading-ring" aria-hidden="true" />
        <span className="sv-loading-text" title={loading}>
          {loading} …
        </span>
        <span className="sv-loading-bar" aria-hidden="true" />
      </div>
    </div>
  )
}
