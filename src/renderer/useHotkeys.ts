// Keys for the transport.
//
// The app had none. Scrubbing a 300-frame log meant dragging a slider or
// clicking a 28px button three hundred times, in a window whose whole point
// is looking at one frame after another.
//
// Mounted once, from `App`. The verbs are the store's own and already clamp,
// so this adds no rule about what a frame number may be -- it only says which
// key means which verb.

import { useEffect } from 'react'

import { useStore } from './store'

/** How far a shifted arrow goes. Ten frames is two seconds of a 5Hz log. */
const STRIDE = 10

/**
 * True when the key should go to whatever has focus instead.
 *
 * This is the whole difficulty of a global key handler here: the rail alone
 * has a select and seven range inputs, and arrows are how you use both. Space
 * is worse -- it activates every button, and the Play button is one of them,
 * so an unguarded Space binding would toggle playback twice per press.
 */
function typing(target: EventTarget | null, key: string): boolean {
  if (!(target instanceof HTMLElement)) {
    return false
  }
  if (target.isContentEditable) {
    return true
  }
  const tag = target.tagName
  if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') {
    return true
  }
  // A focused button already answers Space itself; it has no answer for an
  // arrow, so those still reach the transport.
  return key === ' ' && (tag === 'BUTTON' || target.getAttribute('role') === 'button')
}

export function useHotkeys(): void {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      // Somebody nearer the key already answered it. This listener is on the
      // window, so every handler between here and the target has had its
      // turn: a resize handle that took an arrow, a slider thumb that took
      // Home. They all call `preventDefault`, and none of them should also
      // step the frame.
      //
      // `typing()` below is not made redundant by this -- a native select or
      // range input answers an arrow internally, without preventing the
      // default, so the tag check is still what stands aside for those.
      if (event.defaultPrevented) {
        return
      }
      // A modifier means the key belongs to the window, the menu bar or the
      // platform -- Ctrl+O opens a case, and must not also step a frame.
      if (event.ctrlKey || event.metaKey || event.altKey) {
        return
      }
      if (typing(event.target, event.key)) {
        return
      }

      const { frameCount, setFrame, stepFrame, togglePlaying } = useStore.getState()
      if (frameCount === 0) {
        return
      }

      switch (event.key) {
        case ' ':
          togglePlaying()
          break
        case 'ArrowLeft':
          stepFrame(event.shiftKey ? -STRIDE : -1)
          break
        case 'ArrowRight':
          stepFrame(event.shiftKey ? STRIDE : 1)
          break
        case 'Home':
          setFrame(0)
          break
        case 'End':
          setFrame(frameCount - 1)
          break
        default:
          return
      }

      // Only once a key has been claimed: Space scrolls and Home/End jump,
      // and preventing those for keys we ignored would break the panels.
      event.preventDefault()
    }

    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}
