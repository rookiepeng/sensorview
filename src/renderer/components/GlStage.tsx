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

export interface GlStageProps {
  payload: ScenePayload | null
  /** Called with the table row index of a clicked point. */
  onPick?: (row: number) => void
  /** True when the WebGL context turned out to be a software rasteriser. */
  software?: boolean
}

export function GlStage({ payload, onPick, software }: GlStageProps) {
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
      software,
      onPick: (event) => pick.current?.(event.id)
    })
    scene.current = instance
    // Before the first frame: the colorway decides every categorical colour,
    // and the scene falls back to one flat blue without it.
    instance.setPalette(PALETTE)
    instance.setTheme()

    // The scene sizes itself to its host, and only a real resize changes that.
    const observer = new ResizeObserver(() => instance.resize())
    observer.observe(host.current)

    return () => {
      observer.disconnect()
      instance.dispose()
      scene.current = null
    }
  }, [software])

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
