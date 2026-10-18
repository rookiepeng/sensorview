// The shell: five regions over one scene.
//
// The scene is a fixed layer spanning the viewport, and every panel floats over
// it as glass. `styles/app.css` carries the region geometry and `styles/hud.css`
// the glass, both unchanged from the Dash app -- the layout was already right,
// it was only ever the framework underneath that was being replaced.
//
// The inspector and the analysis dock are P3 and P4; their regions are absent
// rather than stubbed, so the grid does not reserve space for something that
// is not there yet.

import { useEffect, useMemo } from 'react'

import { FilterRail } from './components/FilterRail'
import { GlStage } from './components/GlStage'
import { TopBar } from './components/TopBar'
import { Transport } from './components/Transport'
import { fixtureFrame } from './fixture'
import type { ScenePayload } from './frame'
import { useStore } from './store'

export function App() {
  const frame = useStore((s) => s.frame)
  const frameCount = useStore((s) => s.frameCount)
  const decay = useStore((s) => s.decay)
  const colormap = useStore((s) => s.colormap)
  const sizeVary = useStore((s) => s.sizeVary)
  const playing = useStore((s) => s.playing)
  const hidden = useStore((s) => s.hidden)
  const toggleHidden = useStore((s) => s.toggleHidden)
  const openCase = useStore((s) => s.openCase)

  // Browser mode has no case dialog worth using, so it starts on the fixture.
  // In Electron the top bar's breadcrumb opens one.
  useEffect(() => {
    if (window.sensorview.platform === 'browser') {
      openCase('(fixture)', 60)
    }
  }, [openCase])

  // The frame the scene draws, newest first: index 0 is live, the rest fade.
  // Built here rather than in the store because it is derived state -- storing
  // it would mean keeping it in step with six other fields by hand.
  const payload = useMemo<ScenePayload | null>(() => {
    if (frameCount === 0) {
      return null
    }
    const frames = []
    for (let i = 0; i <= decay && frame - i >= 0; i++) {
      frames.push(fixtureFrame(frame - i, { categorical: sizeVary, hidden }))
    }
    return {
      frames,
      colormap,
      sizeVary,
      // Hover text is only worth building for a view that is standing still,
      // which is the contract the Dash buffer had for the same reason.
      paused: !playing
    }
  }, [frame, frameCount, decay, colormap, sizeVary, playing, hidden])

  return (
    <div className="sv-shell">
      <GlStage payload={payload} onPick={toggleHidden} />

      <TopBar />

      <div className="sv-workspace">
        <div className="sv-upper">
          <FilterRail />
          <div id="rail-splitter" className="sv-splitter sv-splitter-col" />
          <div className="sv-center">
            <div className="sv-stage">
              <div className="sv-canvas" />
            </div>
            <Transport />
          </div>
        </div>
      </div>
    </div>
  )
}
