import type { Palette } from '@shared/palette'

// Types for the scene module.
//
// The GL modules are still JavaScript -- they were moved across from the Dash
// app working, and rewriting them to TypeScript in the same change as moving
// them would have made the diff impossible to read. This declares the surface
// the renderer actually touches, so everything on the React side is typed
// against something real; the modules themselves become `.ts` one at a time.

import type { ScenePayload } from '../frame'

export interface SceneOptions {
  /** True when the WebGL context turned out to be a software rasteriser. */
  software?: boolean
  /** Told which row was clicked, with a counter so repeats are distinguishable. */
  onPick?: (event: { id: number; n: number }) => void
}

export interface Scene {
  /** Draw a frame. `frames[0]` is live; the rest are the decay trail. */
  setFrame(payload: ScenePayload): void
  /** Park or resume the on-demand render loop. */
  setActive(on: boolean): void
  /** Re-read the palette from the document's custom properties. */
  setTheme(): void
  setPalette(palette: Palette): void
  setColormap(name: string): void
  /** Show a message over the scene, or clear it with null. */
  setPending(pending: boolean): void
  setSizeVary(on: boolean): void
  /** Re-measure against the host element. */
  resize(): void
  /** Move the camera to a named view: iso, top, front, side. */
  preset(id: string): void
  /** Fit the camera to the next frame, as the first frame is fitted. */
  reframe(): void
  /** A PNG data URL of the scene, rendered fresh. Empty before it mounts. */
  snapshot(): string
  /** The canvas, for a recorder to capture a stream of. */
  canvas(): HTMLCanvasElement | null
  isMounted(): boolean
  isActive(): boolean
  /** Tear down and release GPU resources. */
  dispose(): void
}

/**
 * Build the renderer inside a host element.
 *
 * The host must be positioned: the CSS2D label layer is absolutely placed over
 * the canvas inside it.
 */
export function create(host: HTMLElement, options?: SceneOptions): Scene
