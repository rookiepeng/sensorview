// The shell: the scene, and everything else floating over it.
//
// Nothing here is laid out beside the scene. `#gl-stage` spans the viewport and
// `.sv-view` lies over it taking no pointer events, with three things inside:
// a column of panels down each side, and the gap between them. The columns are
// as tall as what they hold and no taller, so the scene shows through under a
// short one instead of being walled off by a panel reserving height it is not
// using.
//
// The gap is a region in its own right -- `.sv-center`, placed from the insets
// the HUD measures -- and it holds the top bar as a plate at its head and the
// transport and the dock at its foot. The scene frames its data in the same
// gap, so what is drawn and what can be seen are the same rectangle.
//
// `styles/app.css` carries the geometry and `styles/hud.css` the glass.
//
// Each region draws nothing when it has nothing: the inspector for a log with
// neither a recording nor curves, the dock until a case is open. A region that
// reserved its space empty would make the scene smaller to say nothing.

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Group as Panes,
  Panel,
  Separator,
  type PanelImperativeHandle
} from 'react-resizable-panels'

import { FilterRail } from './components/FilterRail'
import { GlStage } from './components/GlStage'
import { AnalysisDock } from './components/AnalysisDock'
import { Inspector } from './components/Inspector'
import { LoadingOverlay } from './components/LoadingOverlay'
import { TopBar } from './components/TopBar'
import { Transport } from './components/Transport'
import { buildFrame } from './buildFrame'
import {
  BOUNDS,
  OVERLAYS,
  pixelsOf,
  useLayout,
  useLayoutPersistence,
  type Presence
} from './layout'
import { useViewPersistence } from './view'
import { useCloud } from './useCloud'
import { useHotkeys } from './useHotkeys'
import { useReference } from './useReference'
import { fixtureFrame } from './fixture'
import type { ScenePayload } from './frame'
import { caseKey, useSettling, useStore } from './store'
import { useTheme } from './useTheme'
import { parseColor } from '@gl/sv_color.esm.js'

/**
 * The width of a tray on its own: a 26px icon button, 3px of padding and a
 * 1px border either side, as `.sv-tray` draws it in `app.css`.
 *
 * A number here because a panel's constraints are numbers. If the tray's
 * styling changes this has to follow it, and `smoke.ts` checks that a column
 * folded to its tray still shows the whole tray and nothing lies over it.
 */
const TRAY_W = 34

/**
 * The constraints a side panel takes for the shape its column is in.
 *
 * Pinned rather than collapsed. A collapsed panel has one width to collapse
 * to, and the inspector needs two -- its tray, or nothing at all for a log
 * with nothing to show -- so `minSize` and `maxSize` are set equal to
 * whichever width that is. Widths are the column plus the gap it keeps from
 * the window and from its splitter, which the panel carries as padding.
 */
function pinned(presence: Presence, min: number, max: number, gap: number) {
  if (presence === 'cards') {
    return { minSize: min + gap, maxSize: Math.max(min, max) + gap }
  }
  const width = presence === 'tray' ? TRAY_W + gap : 0
  return { minSize: width, maxSize: width }
}

/** Resize a side panel to `want` if it shows its cards and is not there yet. */
function putBack(pane: PanelImperativeHandle | null, presence: Presence, want: number) {
  if (!pane || presence !== 'cards') {
    return
  }
  if (Math.abs(pane.getSize().inPixels - want) > 1) {
    pane.resize(want)
  }
}

/**
 * Store a side column's width after a layout settles.
 *
 * Only while it shows its cards, and only a width at or above its floor: a
 * pinned tray or an empty column is never a width someone chose, and either
 * stored would come back as a column too narrow to use.
 */
function remember(
  px: number | null,
  presence: Presence,
  stored: number | null,
  floor: number,
  gap: number,
  store: (width: number) => void
) {
  if (px === null || presence !== 'cards') {
    return
  }
  const column = Math.round(px) - gap
  if (column >= floor && column !== stored) {
    store(column)
  }
}

/**
 * The strip a folded dock keeps, which is `--sv-dock-tabs-h` in `app.css`.
 *
 * Here as a number because the panel's `collapsedSize` is one, and the two
 * `!important` rules that used to force this height existed only to beat the
 * inline token a drag left behind. Nothing writes that token now.
 */
const DOCK_TABS_H = 38

/** The longest a newly opened case is kept hidden waiting for its inspector. */
const REVEAL_CAP_MS = 3000

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

  // The widths a column starts from when nothing has been dragged, read
  // once from the stylesheet so the numbers live in one place. `--sv-gap` is
  // the inset each column keeps from the window's edge, and
  // `--sv-handle-clear` the room it keeps from its splitter; a panel carries
  // both as padding, so `gap` here is their sum.
  const tokens = useRef<{ rail: number; inspector: number; gap: number } | null>(null)
  if (tokens.current === null) {
    const root = getComputedStyle(document.documentElement)
    const read = (name: string, fallback: number) =>
      parseFloat(root.getPropertyValue(name)) || fallback
    tokens.current = {
      rail: read('--sv-rail-w', 288),
      inspector: read('--sv-inspector-w', 480),
      gap: read('--sv-gap', 10) + read('--sv-handle-clear', 6)
    }
  }
  const { gap } = tokens.current

  // The side columns' ceilings are shares of the window as well as pixel
  // caps, so they are worked out again whenever the window changes.
  const [windowW, setWindowW] = useState(() => window.innerWidth)
  useEffect(() => {
    const onResize = () => setWindowW(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const railPane = useRef<PanelImperativeHandle | null>(null)
  const inspectorPane = useRef<PanelImperativeHandle | null>(null)
  // The two groups' own boxes, which turn a layout's percentages back into
  // pixels -- see `pixelsOf`.
  const row = useRef<HTMLDivElement | null>(null)
  const column = useRef<HTMLDivElement | null>(null)
  // What `defaultSize` gets, read once. As with the dock: a `defaultSize`
  // that follows the store re-registers the panel on every write, and the
  // re-layout writes again.
  const startRailAt = useRef((railW ?? tokens.current.rail) + gap)
  const startInspectorAt = useRef((inspectorW ?? tokens.current.inspector) + gap)
  // The inspector says which shape it is in; whether it has anything to
  // show depends on reads only it makes.
  const [inspectorPresence, setInspectorPresence] = useState<Presence>('none')
  const dockH = useLayout((s) => s.dockH)
  const dockCollapsed = useLayout((s) => s.dockCollapsed)
  const toggleLayout = useLayout((s) => s.toggle)
  const dockPane = useRef<PanelImperativeHandle | null>(null)
  // Read once. Feeding the stored height back into `defaultSize` is the loop
  // that took the window in the inspector's split: the write re-renders, the
  // new prop re-lays out, and the layout writes again.
  const startDockAt = useRef(dockH)
  const hidden = useLayout((s) => s.hidden)
  const setSize = useLayout((s) => s.setSize)
  const cloud = useStore((s) => s.cloud)
  const cloudDisplay = useStore((s) => s.cloudDisplay)
  const reference = useStore((s) => s.reference)
  const referenceBounds = useStore((s) => s.referenceBounds)
  // The manifest's position columns, which the reference's pose is in.
  const positionAxes = useStore((s) => s.summary?.axes)

  // Keeps the cloud in step with the frame. Nothing is returned: the read
  // lands in the store, which is what the payload below is built from.
  useCloud()
  useReference()

  // Space, arrows, Home and End drive the transport. Mounted here because
  // this is the one component that is always on screen.
  useHotkeys()
  useLayoutPersistence()
  useViewPersistence()

  // With nothing open there is nothing for the HUD furniture to report, and
  // a colorbar with no range, a legend with no groups and a transport that
  // reads "-- / --" are worse than an empty window: they look like an app
  // that has failed rather than one that is waiting. On the document because
  // the furniture lives inside the scene's own element, not in this tree.
  useEffect(() => {
    document.documentElement.classList.toggle('sv-no-case', frameCount === 0)
  }, [frameCount])

  // A newly opened case stays hidden behind the "Opening ..." plate until the
  // inspector knows its shape, then is shown two frames later, once the
  // panels have been laid out for it and the column put back to its stored
  // width. Otherwise the first frame of a case is drawn without its
  // inspector and everything shifts when the column arrives. Capped, so a
  // slow read -- a recording being transcoded -- cannot hold the case back.
  const settling = useSettling()
  const dir = useStore((s) => s.dir)
  const stems = useStore((s) => s.stems)
  const settledFor = useStore((s) => s.settledFor)
  const setRevealed = useStore((s) => s.setRevealed)
  useEffect(() => {
    if (!settling) {
      return
    }
    const key = caseKey(dir, stems)
    const cap = setTimeout(() => setRevealed(key), REVEAL_CAP_MS)
    let second = 0
    const first =
      settledFor === key
        ? requestAnimationFrame(() => {
            second = requestAnimationFrame(() => setRevealed(key))
          })
        : 0
    return () => {
      clearTimeout(cap)
      cancelAnimationFrame(first)
      cancelAnimationFrame(second)
    }
  }, [settling, settledFor, dir, stems, setRevealed])

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
              position: positionAxes,
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
    referenceBounds,
    positionAxes
  ])

  // A dragged size overrides the token the region already sizes itself from,
  // so the geometry stays in app.css and this only supplies a number. Unset
  // means the stylesheet's own value, which is how a panel nobody has touched
  // keeps its 288px and its 34vh without those numbers being written here.
  // The store stays the one answer to whether the dock is folded: it is
  // persisted, the head's chevron reads it, and the panel is told rather
  // than asked. Both directions are guarded on disagreement, so neither can
  // chase the other.
  useEffect(() => {
    const pane = dockPane.current
    if (!pane) {
      return
    }
    if (dockCollapsed !== pane.isCollapsed()) {
      if (dockCollapsed) {
        pane.collapse()
      } else {
        pane.expand()
      }
    }
  }, [dockCollapsed])

  // The rail's shape needs no reporting: no case means no rail, and the
  // rest is which of its two overlays are away.
  const railPresence: Presence =
    frameCount === 0
      ? 'none'
      : OVERLAYS.left.some((id) => !hidden.includes(id))
        ? 'cards'
        : 'tray'

  // Back to the dragged width whenever a column returns to its cards. While
  // it was away its constraints were pinned to the tray or to nothing, and
  // widening them again lands the panel on the new floor rather than where
  // it was -- so it is put back. Also when the stored width arrives late,
  // from the settings read at startup. Not on a drag: that stores the width
  // the panel already has, so the two agree and this does nothing.
  //
  // A frame later, not now. Changing a panel's `minSize` or `maxSize`
  // re-registers it, and the group rebuilds its whole axis in a render after
  // this one -- laying the panel out from `defaultSize`. A resize from this
  // effect acts on the old constraints and is then laid over: a cold start
  // came up at the default width with the stored one ignored, and a column
  // back from its tray at the default rather than where it had been.
  //
  // Both columns, whichever one changed. A panel whose constraints change
  // re-registers, and the group then rebuilds the whole row, not just that
  // panel -- so the inspector reporting its shape, which it does only once
  // its reads come back and so at no fixed point in a startup, could knock a
  // rail that had already been put back down onto its floor. With each
  // column put back only on its own changes, nothing put it back again.
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      putBack(railPane.current, railPresence, (railW ?? tokens.current!.rail) + gap)
      putBack(
        inspectorPane.current,
        inspectorPresence,
        (inspectorW ?? tokens.current!.inspector) + gap
      )
    })
    return () => cancelAnimationFrame(frame)
  }, [railPresence, inspectorPresence, railW, inspectorW, gap])

  // Read through refs in the layout handler below. The library keeps the
  // handler it was given on a ref of its own, refreshed after the commit
  // that re-registers a panel -- so on the very layout a presence change
  // causes, the handler it calls can be the one from before the change, and
  // would store a tray's width as if someone had dragged to it.
  const railPresenceNow = useRef(railPresence)
  railPresenceNow.current = railPresence
  const inspectorPresenceNow = useRef(inspectorPresence)
  inspectorPresenceNow.current = inspectorPresence

  return (
    <div className={settling ? 'sv-shell sv-settling' : 'sv-shell'}>
      {/* No handler at all when the toggle is off, so a click reaches the
          picker and does nothing rather than being read and discarded. */}
      <GlStage
        payload={payload}
        onPick={clickToHide ? toggleHidden : undefined}
        subject={stem}
      />

      <div className="sv-view">
        {/* Three columns: the rail, the gap, the inspector. The side ones keep
            their pixel width when the window changes and the gap takes the
            difference, which is what absolutely placed columns used to do
            without anything deciding it. The insets `Hud.reflow()` measures
            off the rail and the inspector no longer place anything here --
            they frame the scene and park the HUD furniture, as before. */}
        <Panes
          orientation="horizontal"
          className="sv-hud-row"
          elementRef={row}
          style={{ overflow: 'visible' }}
          onLayoutChanged={(layout, meta) => {
            // Only what a person did. The library calls this after every layout --
            // mount, a constraint changing, the imperative resizes this file makes --
            // and storing those is a loop: the panels' own restore runs, its layout
            // lands here, and the store moves the target the restore aims at. It also
            // stored a dock 0px tall, from the first layout of a group whose panel
            // had no height yet.
            if (!meta.isUserInteraction) {
              return
            }
            remember(
              pixelsOf(layout, 'rail', row.current, 'width'),
              railPresenceNow.current,
              railW,
              BOUNDS.rail.min,
              gap,
              (width) => setSize('railW', width)
            )
            remember(
              pixelsOf(layout, 'inspector', row.current, 'width'),
              inspectorPresenceNow.current,
              inspectorW,
              BOUNDS.inspector.min,
              gap,
              (width) => setSize('inspectorW', width)
            )
          }}
        >
          <Panel
            id="rail"
            // Which shape the column is in, on the panel's own element: what
            // the constraints below are pinned to, readable from outside.
            data-presence={railPresence}
            panelRef={railPane}
            className="sv-hud-col sv-hud-left"
            style={{ overflow: 'visible' }}
            groupResizeBehavior="preserve-pixel-size"
            defaultSize={startRailAt.current}
            {...pinned(railPresence, BOUNDS.rail.min, BOUNDS.rail.max(windowW), gap)}
          >
            <FilterRail />
          </Panel>

          {/* Double-click is ours, as on the other handles: the library's
              would restore `defaultSize`, which is the dragged width. */}
          <Separator
            className="sv-splitter sv-splitter-col"
            aria-label="Filter rail width"
            disabled={railPresence !== 'cards'}
            disableDoubleClick
            onDoubleClick={() => {
              railPane.current?.resize(tokens.current!.rail + gap)
              setSize('railW', null)
            }}
          />

          <Panel id="gap" className="sv-hud-centre" style={{ overflow: 'visible' }} minSize="20">
            <Panes
              orientation="vertical"
              className="sv-center"
              elementRef={column}
              // The library writes `width: 100%; height: 100%; overflow: hidden`
              // inline. The panel this sits in is a column and this grows to fill
              // it, so `auto` lets that decide. Overflow stays open for the menus
              // that hang off the top bar; the dock clips its own charts.
              style={{ width: 'auto', height: 'auto', overflow: 'visible' }}
              onLayoutChanged={(layout, meta) => {
                // Only what a person did -- see the row's handler above.
                if (!meta.isUserInteraction) {
                  return
                }
                const tall = pixelsOf(layout, 'dock', column.current, 'height')
                if (tall === null) {
                  return
                }
                // A drag past the threshold folds the dock without going
                // through its head, so the store hears about the fold here --
                // and only here, behind the check above. It used to be heard
                // from the panel's onResize, which also fires for the group
                // laying itself out: inside its panel the column is no height
                // at all on its first layout, a dock of no height reads as
                // folded, and that one write marked the layout as touched
                // before the settings had been read. A cold start then never
                // read them, and came up at every default.
                const folded = tall <= DOCK_TABS_H + 1
                if (folded !== dockCollapsed) {
                  toggleLayout('dockCollapsed')
                }
                // Folded is not a height anyone chose.
                if (folded) {
                  return
                }
                const px = Math.round(tall)
                if (px !== dockH) {
                  setSize('dockH', px)
                }
              }}
            >
              <Panel className="sv-center-gap" style={{ overflow: 'visible' }} minSize="20">
                <TopBar />
                <LoadingOverlay />
                <div className="sv-center-foot">{frameCount > 0 && <Transport />}</div>
              </Panel>

              <Separator
                className="sv-splitter sv-splitter-row"
                disabled={dockCollapsed}
                disableDoubleClick
                onDoubleClick={() => {
                  dockPane.current?.resize('34')
                  setSize('dockH', null)
                }}
              />

              <Panel
                id="dock"
                panelRef={dockPane}
                // Not `sv-dock-pane`: that is each of the dock's two chart slots,
                // hidden unless it is one of the two in use. Borrowing it hid the
                // whole dock.
                className="sv-dock-region"
                style={{ overflow: 'visible' }}
                // `--sv-dock-h` is `34vh` and this gap is the window's height,
                // so the token transfers as a percentage. The floor stays in
                // pixels: it is a head plus `--sv-pane-plot-min`, which is a
                // number of pixels and not a share of anything.
                defaultSize={startDockAt.current ?? '34'}
                minSize={BOUNDS.dock.min}
                maxSize="65"
                collapsible
                collapsedSize={DOCK_TABS_H}
              >
                <AnalysisDock theme={theme} />
              </Panel>
            </Panes>
          </Panel>

          <Separator
            className="sv-splitter sv-splitter-col"
            aria-label="Inspector width"
            disabled={inspectorPresence !== 'cards'}
            disableDoubleClick
            onDoubleClick={() => {
              inspectorPane.current?.resize(tokens.current!.inspector + gap)
              setSize('inspectorW', null)
            }}
          />

          {/* Always mounted, even with nothing to show: the inspector is what
              reads whether there is anything, so unmounting it would leave
              nothing to say so when there is something again. Pinned to zero
              instead, which `:has()` used to manage with `display`. */}
          <Panel
            id="inspector"
            // Which shape the column is in, on the panel's own element: what
            // the constraints below are pinned to, readable from outside.
            data-presence={inspectorPresence}
            panelRef={inspectorPane}
            className="sv-hud-col sv-hud-right"
            style={{ overflow: 'visible' }}
            groupResizeBehavior="preserve-pixel-size"
            defaultSize={startInspectorAt.current}
            {...pinned(
              inspectorPresence,
              BOUNDS.inspector.min,
              BOUNDS.inspector.max(windowW),
              gap
            )}
          >
            <Inspector onPresence={setInspectorPresence} />
          </Panel>
        </Panes>
      </div>
    </div>
  )
}
