// Reading the dense cloud for whatever frame is showing.
//
// This is the one thing in the renderer that costs a read per frame. The table
// is in memory and scrubbing it is free, but a cloud frame is ~130 KB of HDF5
// that has to be decompressed, so it is read on demand and only while the
// cloud is switched on.
//
// Responses can arrive out of order -- dragging the slider starts a read per
// position and a later frame's can land first. Each read carries the frame it
// was for and a token; anything but the newest token is dropped, so the cloud
// on screen always belongs to the frame on screen rather than to whichever
// read happened to finish last.

import { useEffect, useRef } from 'react'

import { useStore } from './store'

export function useCloud(): void {
  const dir = useStore((s) => s.dir)
  const stem = useStore((s) => s.stem)
  const table = useStore((s) => s.table)
  const frame = useStore((s) => s.frame)
  const cloudOn = useStore((s) => s.cloudOn)
  const cloudDisplay = useStore((s) => s.cloudDisplay)
  const setCloud = useStore((s) => s.setCloud)

  const token = useRef(0)

  useEffect(() => {
    const frameId = table?.frameIds[frame]
    if (!cloudOn || !cloudDisplay || !dir || !stem || frameId === undefined) {
      return
    }

    const mine = ++token.current
    void window.sensorview
      .data('logCloudFrame', { dir, stem, frameId })
      .then((result) => {
        if (mine !== token.current) {
          return
        }
        setCloud(
          result.ok && result.data
            ? { frameId, position: result.data.position, count: result.data.count }
            : null
        )
      })
  }, [dir, stem, table, frame, cloudOn, cloudDisplay, setCloud])
}
