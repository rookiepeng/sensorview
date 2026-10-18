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
import { buildFrame } from './buildFrame'
import { useCloud } from './useCloud'
import { fixtureFrame } from './fixture'
import type { ScenePayload } from './frame'
import { useStore } from './store'
import { parseColor } from '@gl/sv_color.esm.js'

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
  const table = useStore((s) => s.table)
  const axes = useStore((s) => s.axes)
  const keys = useStore((s) => s.keys)
  const filters = useStore((s) => s.filters)
  const cloud = useStore((s) => s.cloud)
  const cloudDisplay = useStore((s) => s.cloudDisplay)

  // Keeps the cloud in step with the frame. Nothing is returned: the read
  // lands in the store, which is what the payload below is built from.
  useCloud()

  // Browser mode has no readers behind it, so it starts on the fixture. In
  // Electron the top bar's breadcrumb opens a real case.
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
      frames.push(
        table
          ? buildFrame(table, frame - i, {
              ...axes,
              filters,
              keys,
              withHover: !playing
            })
          : fixtureFrame(frame - i, { categorical: sizeVary, hidden })
      )
    }

    // The scene reads the cloud from the live frame only -- a decayed cloud
    // would be a second 11,000-point layer per trailed frame, and the Python
    // did not draw one either.
    const live = frames[0]
    if (live && cloudDisplay && cloud && cloud.frameId === table?.frameIds[frame]) {
      const [r, g, b] = parseColor(cloudDisplay.color)
      live.cloud = {
        position: cloud.position,
        count: cloud.count,
        rgb: [r!, g!, b!],
        size: cloudDisplay.size,
        opacity: cloudDisplay.opacity,
        name: cloudDisplay.name
      }
    }

    // Hiding a row is a mask over the built frame, so a click costs a rebuild
    // of one frame rather than a re-read of anything.
    if (table && hidden.size > 0) {
      for (const built of frames) {
        for (const group of built.groups) {
          const keep: number[] = []
          for (let i = 0; i < group.count; i++) {
            if (!hidden.has(group.ids![i]!)) {
              keep.push(i)
            }
          }
          if (keep.length === group.count) {
            continue
          }
          const position = new Float32Array(keep.length * 3)
          const ids = new Float64Array(keep.length)
          const value = group.value ? new Float32Array(keep.length) : null
          keep.forEach((src, dst) => {
            position.set(group.position.subarray(src * 3, src * 3 + 3), dst * 3)
            ids[dst] = group.ids![src]!
            if (value) {
              value[dst] = group.value![src]!
            }
          })
          const original = group.hover
          group.position = position
          group.ids = ids
          group.value = value
          group.count = keep.length
          group.hover = (row) => original(keep[row] ?? -1)
        }
      }
    }
    return {
      frames,
      colormap,
      sizeVary,
      // Hover text is only worth building for a view that is standing still,
      // which is the contract the Dash buffer had for the same reason.
      paused: !playing
    }
  }, [
    frame,
    frameCount,
    decay,
    colormap,
    sizeVary,
    playing,
    hidden,
    table,
    axes,
    keys,
    filters,
    cloud,
    cloudDisplay
  ])

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
