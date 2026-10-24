// How the open case is being looked at, remembered per case.
//
// The sibling of `useLayoutPersistence`, and separate from it for the reason
// the two stores are separate: the layout describes the window and outlives
// every case, while this describes one case and is meaningless away from it.
// Reopening a case with the rail's settings from the last one would be worse
// than defaults, because most of these name columns.
//
// `openLog` resets the case store to its initial state -- which is right,
// since a log can gain and lose columns -- so a restore has to happen after
// it, not instead of it. That is what makes this a hook on `table` rather
// than something the loader passes in.

import { useEffect, useRef } from 'react'

import type { CaseView } from '@shared/types'

import { useStore, type CaseState } from './store'

/** The persisted fields alone, for writing back. */
export function viewOf(s: CaseState): CaseView {
  return {
    axes: s.axes,
    colormap: s.colormap,
    decay: s.decay,
    overlay: s.overlay,
    cloudOn: s.cloudOn,
    sizeVary: s.sizeVary,
    clickToHide: s.clickToHide
  }
}

/**
 * Read this case's stored view when it opens, then write changes back.
 *
 * Once per case, not once per log. `openLog` resets the store, so a log
 * switch does need the settings put back -- but reading them again is a
 * different thing: it would answer with whatever was last written, and a
 * write in flight when the log changed would put the state before it back
 * on screen. The case is the unit the user thinks in, and the stored view
 * is applied when they open it.
 *
 * The write is debounced for the same reason the layout's is -- the decay
 * slider produces one change per pointer event -- and compared before it is
 * scheduled, because this store changes on every frame the transport plays
 * and none of that is worth a write.
 *
 * The analysis dock's panes are the other half of a stored view, and are
 * written by `AnalysisDock` itself: they live in its own state, and
 * `rememberView` merges a patch so the two halves cannot overwrite each
 * other.
 */
export function useViewPersistence(): void {
  const dir = useStore((s) => s.dir)
  const table = useStore((s) => s.table)
  /** The case whose stored view has been put on screen. */
  const applied = useRef<string | null>(null)
  /** That view as it stands, which a log switch has to put back. */
  const held = useRef<CaseView>({})

  useEffect(() => {
    if (!dir || !table) {
      return
    }
    let live = true
    // Nothing is written until the read has landed, or the defaults this log
    // opened with would be saved over the settings being read.
    let ready = false
    // The view as this log opened, so the subscriber below can tell a change
    // of the user's from the dozens a playing transport makes.
    let last = JSON.stringify(viewOf(useStore.getState()))
    let timer: ReturnType<typeof setTimeout> | undefined

    if (applied.current === dir) {
      // A log switch inside the case this already restored. `openLog` has
      // put the defaults back, and what the user has since chosen is in
      // hand -- fresher than anything the settings file could answer with.
      useStore.getState().applyView(held.current)
      last = JSON.stringify(viewOf(useStore.getState()))
      ready = true
    } else {
      void window.sensorview.settings.get().then((stored) => {
        if (!live) {
          return
        }
        const saved = stored.ok ? stored.data?.views[dir] : undefined
        // Not if the user has already changed something: the read is a round
        // trip, and a click on the colormap can land first.
        if (saved && !ready) {
          useStore.getState().applyView(saved)
        }
        applied.current = dir
        ready = true
        held.current = viewOf(useStore.getState())
        last = JSON.stringify(held.current)
      })
    }

    const stop = useStore.subscribe((state) => {
      // A different log opening. `openLog` resets the store, and this
      // listener -- still the previous log's until React gets to the cleanup
      // -- took that reset for a change of the user's: it overwrote the view
      // held for the case with the defaults, which the next log then put
      // back, and saved them over the stored view too. So switching logs
      // reset the color and the colormap. Not this log's state, not ours.
      if (state.table !== table || state.dir !== dir) {
        return
      }
      const now = JSON.stringify(viewOf(state))
      if (now === last) {
        return
      }
      last = now
      held.current = viewOf(state)
      if (!ready) {
        // A change of the user's own, before the read came back. Theirs wins:
        // the read above now leaves the store alone.
        ready = true
        return
      }
      clearTimeout(timer)
      timer = setTimeout(() => {
        void window.sensorview.settings.rememberView(dir, viewOf(state))
      }, WRITE_AFTER_MS)
    })

    return () => {
      live = false
      clearTimeout(timer)
      stop()
    }
  }, [dir, table])
}

/** As the layout's: long enough that a drag is one write. */
const WRITE_AFTER_MS = 400
