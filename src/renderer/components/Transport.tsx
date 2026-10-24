// Frame scrubbing and playback.
//
// A floating glass bar over the scene, as the HUD stylesheet already draws it.
// Playback is a timer here rather than in the scene, because what advances is
// application state -- the scene only ever draws the frame it is handed.

import { useEffect } from 'react'

import { IconButton } from './Controls'
import { useStore } from '../store'

// Matches the Dash transport's interval. Fast enough to read as motion, slow
// enough that a frame's worth of work lands between ticks.
const TICK_MS = 200

export function Transport() {
  const frame = useStore((s) => s.frame)
  const frameCount = useStore((s) => s.frameCount)
  const playing = useStore((s) => s.playing)
  const setFrame = useStore((s) => s.setFrame)
  const stepFrame = useStore((s) => s.stepFrame)
  const togglePlaying = useStore((s) => s.togglePlaying)

  useEffect(() => {
    if (!playing || frameCount === 0) {
      return
    }
    const timer = setInterval(() => {
      // Wrapping rather than stopping at the end: the Dash transport looped,
      // and a scene that halts on the last frame looks like a stall.
      const next = useStore.getState().frame + 1
      useStore.getState().setFrame(next >= frameCount ? 0 : next)
    }, TICK_MS)
    return () => clearInterval(timer)
  }, [playing, frameCount])

  const last = Math.max(0, frameCount - 1)

  return (
    <div className="sv-transport">
      <div className="sv-transport-buttons">
        <IconButton
          icon="previous-frame"
          title="Previous frame"
          onClick={() => stepFrame(-1)}
          disabled={frameCount === 0}
        />
        <IconButton
          icon={playing ? 'pause' : 'play'}
          title={playing ? 'Pause' : 'Play'}
          onClick={togglePlaying}
          disabled={frameCount === 0}
          className="sv-transport-play"
        />
        <IconButton
          icon="next-frame"
          title="Next frame"
          onClick={() => stepFrame(1)}
          disabled={frameCount === 0}
        />
      </div>

      <div className="sv-transport-slider">
        <input
          type="range"
          min={0}
          max={last}
          step={1}
          value={frame}
          aria-label="Frame"
          onChange={(event) => setFrame(Number(event.target.value))}
          disabled={frameCount === 0}
        />
      </div>

      {/* An empty app and a single-frame log both used to read "0 / 0".
          There is no position to report when nothing is open, so say that. */}
      <div className={`sv-frame-readout${frameCount === 0 ? ' sv-frame-readout-empty' : ''}`}>
        {frameCount === 0 ? (
          <span>— / —</span>
        ) : (
          <>
            <b>{frame}</b>
            <span> / {last}</span>
          </>
        )}
      </div>
    </div>
  )
}
