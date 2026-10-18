// Reading the reference pose for whatever frame is showing.
//
// Same shape as `useCloud`, and for the same reason: a pose is per frame, so
// it is a read per frame, and reads can land out of order while the slider is
// being dragged. The bounds are read once per log instead -- they cover every
// frame by definition, and the scene needs them before the first frame so the
// axis box is wide enough to contain a reference that travels.

import { useEffect, useRef } from 'react'

import { useStore } from './store'

export function useReference(): void {
  const dir = useStore((s) => s.dir)
  const primary = useStore((s) => s.stem)
  const ownerSets = useStore((s) => s.ownerSets)
  const table = useStore((s) => s.table)
  const frame = useStore((s) => s.frame)
  const setReference = useStore((s) => s.setReference)
  const setReferenceBounds = useStore((s) => s.setReferenceBounds)

  const token = useRef(0)

  useEffect(() => {
    setReferenceBounds(null)
    // The bounds widen the axis box for the whole load, so they come from
    // the primary: a box fitted to one log's journey and then widened by
    // another's would be the union of two unrelated drives.
    if (!dir || !primary) {
      return
    }
    let current = true
    void window.sensorview
      .data('logReferenceBounds', { dir, stem: primary })
      .then((result) => {
        if (current && result.ok) {
          setReferenceBounds(result.data ?? null)
        }
      })
    return () => {
      current = false
    }
  }, [dir, primary, setReferenceBounds])

  useEffect(() => {
    const frameId = table?.frameIds[frame]
    // One pose can be drawn, so it is the frame's own leading log's.
    const stem = ownerSets[frame]?.[0] ?? primary
    if (!dir || !stem || frameId === undefined) {
      return
    }

    const mine = ++token.current
    void window.sensorview
      .data('logReference', { dir, stem, frameId })
      .then((result) => {
        if (mine !== token.current) {
          return
        }
        // A frame the sidecar has no row for draws nothing, rather than
        // stranding the reference at its last known pose.
        setReference(result.ok ? (result.data ?? null) : null)
      })
  }, [dir, ownerSets, primary, table, frame, setReference])
}
