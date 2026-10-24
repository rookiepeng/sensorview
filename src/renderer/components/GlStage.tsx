// The seam between React and the three.js scene.
//
// React owns the host element and nothing inside it. The scene keeps its own
// on-demand render loop -- `invalidate()` on change, damping-aware, idle at
// zero cost -- because a component that re-rendered per frame would be the one
// thing guaranteed to make a 100k-point view stutter.
//
// So this component renders exactly once per mount. Frames reach the scene
// through an effect calling `setFrame`, not through props the tree diffs.

import { useEffect, useRef } from 'react'

import { create, type Scene } from '@gl/sv_scene.esm.js'

import { PALETTE } from '@shared/palette'

import type { ScenePayload } from '../frame'
import { setScene } from '../sceneHandle'

export interface GlStageProps {
  payload: ScenePayload | null
  /** Called with the table row index of a clicked point. */
  onPick?: (row: number) => void
  /**
   * True when the WebGL context turned out to be a software rasteriser,
   * which the stats readout surfaces. Detected when not given -- nothing
   * ever gave it, so the warning the scene can draw was never drawn.
   */
  software?: boolean
  /**
   * What the scene is showing -- the open log's stem.
   *
   * Changing it refits the camera. Within one log the camera is the user's
   * and a new frame must not move it; a different log is a different box, and
   * keeping the old camera leaves its data off-screen.
   */
  subject?: string | null
}

/** The floating panels the HUD has to stay clear of. */
// The trays too: one hanging outside its column moves the corner HUD, and
// appears or goes without the column itself changing size.
const PANELS = '.sv-rail, .sv-inspector, .sv-transport, .sv-dock, .sv-tray'

/**
 * Whether this machine is drawing WebGL on the CPU.
 *
 * Worth saying out loud: a software rasteriser turns a 100k-point view into
 * single-digit frames per second, and without the stats readout admitting
 * it the app just looks slow. A remote session or a driver without hardware
 * acceleration is the usual reason.
 */
function rasterisesInSoftware(): boolean {
  try {
    const probe = document.createElement('canvas').getContext('webgl2')
    if (!probe) {
      return false
    }
    const info = probe.getExtension('WEBGL_debug_renderer_info')
    const name = info
      ? String(probe.getParameter(info.UNMASKED_RENDERER_WEBGL))
      : String(probe.getParameter(probe.RENDERER))
    probe.getExtension('WEBGL_lose_context')?.loseContext()
    return /swiftshader|llvmpipe|software|basic render/i.test(name)
  } catch {
    // A probe that cannot be made says nothing about the real context.
    return false
  }
}

export function GlStage({ payload, onPick, software, subject }: GlStageProps) {
  const host = useRef<HTMLDivElement>(null)
  const scene = useRef<Scene | null>(null)

  // The callback goes through a ref so the scene is built once: passing it
  // straight to `create` would rebuild the whole renderer whenever the parent
  // re-rendered with a new closure.
  const pick = useRef(onPick)
  pick.current = onPick

  useEffect(() => {
    if (!host.current) {
      return
    }
    const instance = create(host.current, {
      software: software ?? rasterisesInSoftware(),
      onPick: (event) => pick.current?.(event.id)
    })
    scene.current = instance
    // Published for the exports, which read the canvas directly.
    setScene(instance)
    // Before the first frame: the colorway decides every categorical color,
    // and the scene falls back to one flat blue without it.
    instance.setPalette(PALETTE)
    instance.setTheme()

    // The scene sizes itself to its host, and only a real resize changes
    // that. `resize` also reflows the HUD, which is the reason the panels are
    // watched as well: the HUD measures where they end, #gl-stage is fixed to
    // the viewport, and so a collapse or a splitter drag changes nothing this
    // would otherwise see. Watching them also follows the collapse animation
    // frame by frame rather than measuring once, mid-slide.
    const observer = new ResizeObserver(() => instance.resize())
    observer.observe(host.current)

    const watchPanels = () => {
      for (const panel of document.querySelectorAll(PANELS)) {
        observer.observe(panel)
      }
    }
    watchPanels()
    // The inspector is absent for a log with neither a recording nor curves,
    // so it is often not in the document when this runs. Re-observing on a
    // child change costs nothing -- observing an element twice is a no-op.
    const appearing = new MutationObserver(watchPanels)
    // The shell rather than a region inside it: every panel lives under it,
    // and it is the one wrapper that is never conditional.
    const shell = document.querySelector('.sv-shell')
    if (shell) {
      appearing.observe(shell, { childList: true, subtree: true })
    }

    return () => {
      appearing.disconnect()
      observer.disconnect()
      instance.dispose()
      scene.current = null
      setScene(null)
    }
  }, [software])

  // Before the frame effect below, so the frame that arrives with a new
  // subject is the one that fits the camera.
  useEffect(() => {
    scene.current?.reframe()
  }, [subject])

  useEffect(() => {
    if (payload) {
      scene.current?.setFrame(payload)
    }
  }, [payload])

  // The theme lives on <html> as an attribute, so the scene is told to re-read
  // it rather than being passed a palette it would then have to keep in step.
  useEffect(() => {
    const observer = new MutationObserver(() => scene.current?.setTheme())
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-bs-theme']
    })
    return () => observer.disconnect()
  }, [])

  return <div id="gl-stage" ref={host} />
}
