// The shell: five regions over one scene.
//
// The scene is a fixed layer spanning the viewport, and every panel floats over
// it as glass. `styles/app.css` carries the region geometry and `styles/hud.css`
// the glass, both unchanged from the Dash app -- the layout was already right,
// it was only ever the framework underneath that was being replaced.
//
// Each region draws nothing when it has nothing: the inspector for a log with
// neither a recording nor curves, the dock until a case is open. A region that
// reserved its space empty would make the scene smaller to say nothing.

import { useEffect, useMemo } from 'react'

import { FilterRail } from './components/FilterRail'
import { Splitter } from './components/Splitter'
import { GlStage } from './components/GlStage'
import { AnalysisDock } from './components/AnalysisDock'
import { Inspector } from './components/Inspector'
import { TopBar } from './components/TopBar'
import { Transport } from './components/Transport'
import { buildFrame } from './buildFrame'
import { useLayout, useLayoutPersistence } from './layout'
import { useCloud } from './useCloud'
import { useHotkeys } from './useHotkeys'
import { useReference } from './useReference'
import { fixtureFrame } from './fixture'
import type { ScenePayload } from './frame'
import { useStore } from './store'
import { useTheme } from './useTheme'
import { parseColor } from '@gl/sv_color.esm.js'

/** Pixel bounds for each region. A floor that keeps a panel grabbable, and
 *  a ceiling that keeps the scene the biggest thing on screen. The dock's
 *  floor is its own head plus `--sv-pane-plot-min`, below which a figure is
 *  axes and nothing else. */
const BOUNDS = {
  rail: { min: 200, max: () => Math.min(480, window.innerWidth * 0.4) },
  inspector: { min: 280, max: () => Math.min(640, window.innerWidth * 0.5) },
  dock: { min: 218, max: () => window.innerHeight * 0.6 }
}

const sizeOf = (selector: string, axis: 'width' | 'height') => () =>
  document.querySelector(selector)?.getBoundingClientRect()[axis] ?? 0

export function App() {
  const frame = useStore((s) => s.frame)
  const frameCount = useStore((s) => s.frameCount)
  const decay = useStore((s) => s.decay)
  const overlay = useStore((s) => s.overlay)
  const colormap = useStore((s) => s.colormap)
  const sizeVary = useStore((s) => s.sizeVary)
  const playing = useStore((s) => s.playing)
  // Hidden rows are excluded by `filterAll` before a frame is built, so
  // there is nothing to mask here. This only has to know *that* the
  // visibility changed, since it lives in a typed array a memo cannot see.
  const visibleRev = useStore((s) => s.visibleRev)
  const toggleHidden = useStore((s) => s.toggleHidden)
  const clickToHide = useStore((s) => s.clickToHide)
  const openCase = useStore((s) => s.openCase)
  const table = useStore((s) => s.table)
  const axes = useStore((s) => s.axes)
  const keys = useStore((s) => s.keys)
  const stem = useStore((s) => s.stem)
  const theme = useTheme()
  const filters = useStore((s) => s.filters)
  const railW = useLayout((s) => s.railW)
  const inspectorW = useLayout((s) => s.inspectorW)
  const dockH = useLayout((s) => s.dockH)
  const railCollapsed = useLayout((s) => s.railCollapsed)
  const setSize = useLayout((s) => s.setSize)
  const cloud = useStore((s) => s.cloud)
  const cloudDisplay = useStore((s) => s.cloudDisplay)
  const reference = useStore((s) => s.reference)
  const referenceBounds = useStore((s) => s.referenceBounds)

  // Keeps the cloud in step with the frame. Nothing is returned: the read
  // lands in the store, which is what the payload below is built from.
  useCloud()
  useReference()

  // Space, arrows, Home and End drive the transport. Mounted here because
  // this is the one component that is always on screen.
  useHotkeys()
  useLayoutPersistence()

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
    // `visibleRev` is a real dependency: the visibility it stands for lives
    // in a typed array that is mutated in place, which a memo cannot see.
    // Referenced rather than only listed, so the rule agrees.
    void visibleRev
    if (frameCount === 0) {
      return null
    }
    // Overlay is one frame holding every filtered row, so there is no trail
    // to build: decay and overlay are two answers to the same question.
    const trail = overlay ? 0 : decay
    const frames = []
    for (let i = 0; i <= trail && frame - i >= 0; i++) {
      frames.push(
        table
          ? buildFrame(table, frame - i, {
              ...axes,
              filters,
              keys,
              // The box has to contain the reference's whole journey, not
              // just the detections: it is fixed for the log, and a pose
              // outside it would simply be clipped.
              refBounds: referenceBounds,
              overlay,
              withHover: !playing
            })
          : fixtureFrame(frame - i, { categorical: sizeVary, hidden: new Set() })
      )
    }

    // The scene reads the cloud from the live frame only -- a decayed cloud
    // would be a second 11,000-point layer per trailed frame, and the Python
    // did not draw one either.
    const live = frames[0]
    // Overlaying every frame at once leaves no single frame for a per-frame
    // pose to belong to, so a sidecar-placed reference draws nothing here --
    // and neither does the cloud, which is per frame for the same reason.
    if (live && reference && !overlay) {
      const rgb = parseColor(reference.color) as [number, number, number]
      live.ref = {
        mesh: reference.mesh
          ? {
              position: reference.mesh,
              // Expanded triangles rather than indexed: the mesh is twenty
              // of them, and `flatShading` wants per-face normals anyway.
              index: new Uint32Array(0),
              rgb,
              opacity: reference.opacity
            }
          : null,
        edges: reference.edges
          ? { position: reference.edges, rgb: parseColor(reference.edgeColor) as [number, number, number] }
          : null,
        marker: null,
        name: reference.name
      }
    }
    if (live && !overlay && cloudDisplay && cloud && cloud.frameId === table?.frameIds[frame]) {
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
    overlay,
    colormap,
    sizeVary,
    playing,
    visibleRev,
    table,
    axes,
    keys,
    filters,
    cloud,
    cloudDisplay,
    reference,
    referenceBounds
  ])

  // A dragged size overrides the token the region already sizes itself from,
  // so the geometry stays in app.css and this only supplies a number. Unset
  // means the stylesheet's own value, which is how a panel nobody has touched
  // keeps its 288px and its 34vh without those numbers being written here.
  const sizes = {
    ...(railW !== null && { '--sv-rail-w': `${railW}px` }),
    ...(inspectorW !== null && { '--sv-inspector-w': `${inspectorW}px` }),
    ...(dockH !== null && { '--sv-dock-h': `${dockH}px` })
  } as React.CSSProperties

  return (
    <div className="sv-shell" style={sizes}>
      {/* No handler at all when the toggle is off, so a click reaches the
          picker and does nothing rather than being read and discarded. */}
      <GlStage
        payload={payload}
        onPick={clickToHide ? toggleHidden : undefined}
        subject={stem}
      />

      <TopBar />

      <div className="sv-workspace">
        <div className="sv-upper">
          <FilterRail />
          {!railCollapsed && (
            <Splitter
              id="rail-splitter"
              axis="col"
              label="Filter rail width"
              measure={sizeOf('.sv-rail', 'width')}
              onResize={(px) => setSize('railW', px)}
              onReset={() => setSize('railW', null)}
              value={railW}
              {...BOUNDS.rail}
            />
          )}
          <div className="sv-center">
            <div className="sv-stage">
              <div className="sv-canvas" />
            </div>
            <Transport />
          </div>
          {/* The inspector draws nothing for a log with neither a recording
              nor curves, and `.sv-upper > .sv-splitter:last-child` is what
              takes its handle away with it -- React cannot see from here
              whether the component returned null. */}
          <Splitter
            id="inspector-splitter"
            axis="col"
            label="Inspector width"
            measure={sizeOf('.sv-inspector', 'width')}
            onResize={(px) => setSize('inspectorW', px)}
            onReset={() => setSize('inspectorW', null)}
            value={inspectorW}
            invert
            {...BOUNDS.inspector}
          />
          <Inspector />
        </div>
        <AnalysisDock theme={theme} />
      </div>
    </div>
  )
}
