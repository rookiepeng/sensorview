// Where the one scene can be found from outside the component that owns it.
//
// `GlStage` builds the scene and is the only thing that talks to it per
// frame. The exports need it too -- a still and an animation both come off
// that canvas -- and threading a ref down through the tree to a menu in the
// top bar would make every component in between know about something none of
// them use.
//
// A module-level slot rather than context, because there is exactly one scene
// and its lifetime is the app's. It is null before the stage mounts and again
// after it unmounts, and callers check.

import type { Scene } from '@gl/sv_scene.esm.js'

let current: Scene | null = null

export function setScene(scene: Scene | null): void {
  current = scene
}

export function getScene(): Scene | null {
  return current
}
