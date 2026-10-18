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
  const stem = useStore((s) => s.stem)
  const table = useStore((s) => s.table)
  const frame = useStore((s) => s.frame)
  const setReference = useStore((s) => s.setReference)
  const setReferenceBounds = useStore((s) => s.setReferenceBounds)

  const token = useRef(0)

  useEffect(() => {
    setReferenceBounds(null)
    if (!dir || !stem) {
      return
    }
    let current = true
    void window.sensorview
      .data('logReferenceBounds', { dir, stem })
      .then((result) => {
        if (current && result.ok) {
          setReferenceBounds(result.data ?? null)
        }
      })
    return () => {
      current = false
    }
  }, [dir, stem, setReferenceBounds])

  useEffect(() => {
    const frameId = table?.frameIds[frame]
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
  }, [dir, stem, table, frame, setReference])
}
