// Where the panels are, and whether they are open.
//
// A second store, deliberately. The case store resets itself wholesale on
// `openCase` and `closeCase` -- `set({ ...initial })` -- which is right for
// everything that describes a case and wrong for everything that describes
// the window. Layout kept there would be thrown away every time a case was
// opened, which is the moment a user is least expecting their panels to move.
//
// Sizes are pixels or null. Null means "whatever the stylesheet says", which
// is how a panel that has never been dragged keeps `--sv-rail-w` and its
// `34vh` dock without this file having to know those numbers.

import { useEffect } from 'react'
import { create } from 'zustand'

import { DEFAULT_LAYOUT, sanitiseLayout, type Layout } from '@shared/types'

/** Which of the three foldable panels were away. */
interface Folded {
  rail: boolean
  inspector: boolean
  dock: boolean
}

export interface LayoutState extends Layout {
  /**
   * What the panels were before `focusScene` folded them, or null when it
   * did not. Deliberately not persisted: it is the way back from one click,
   * not a description of the window, and a stale one read off disk would
   * reopen panels the user had folded by hand.
   */
  restore: Folded | null
  setSize: (key: 'railW' | 'inspectorW' | 'dockH', px: number | null) => void
  toggle: (key: 'railCollapsed' | 'inspectorCollapsed' | 'dockCollapsed') => void
  /** Fold a panel card away, or bring it back. */
  toggleFold: (id: string) => void
  /** Show one analysis pane or two. */
  setPanes: (count: number) => void
  /** Fold all three panels away, or put back the ones that were open. */
  focusScene: () => void
  /** Replace everything persisted, on the one read at startup. */
  hydrate: (stored: Layout) => void
}

export const useLayout = create<LayoutState>((set) => ({
  ...DEFAULT_LAYOUT,
  restore: null,
  setSize: (key, px) => set({ [key]: px } as Pick<LayoutState, typeof key>),
  toggle: (key) => set((s) => ({ [key]: !s[key] }) as Pick<LayoutState, typeof key>),
  toggleFold: (id) =>
    set((s) => ({
      folded: s.folded.includes(id) ? s.folded.filter((name) => name !== id) : [...s.folded, id]
    })),
  setPanes: (count) => set({ dockPanes: count === 1 ? 1 : 2 }),
  focusScene: () =>
    set((s) => {
      if (!s.railCollapsed || !s.inspectorCollapsed || !s.dockCollapsed) {
        return {
          restore: {
            rail: s.railCollapsed,
            inspector: s.inspectorCollapsed,
            dock: s.dockCollapsed
          },
          railCollapsed: true,
          inspectorCollapsed: true,
          dockCollapsed: true
        }
      }
      // All three are already away. Put back whatever was open before --
      // or open all three, for a window that came up collapsed and has
      // nothing remembered.
      const was = s.restore ?? { rail: false, inspector: false, dock: false }
      return {
        restore: null,
        railCollapsed: was.rail,
        inspectorCollapsed: was.inspector,
        dockCollapsed: was.dock
      }
    }),
  hydrate: (stored) => set(stored)
}))

/**
 * Pixel bounds for each region.
 *
 * A floor that keeps a panel grabbable, and a ceiling that keeps the scene the
 * biggest thing on screen. The dock's floor is its own head plus
 * `--sv-pane-plot-min`, below which a figure is axes and nothing else; its
 * ceiling is a fraction of the centre column, which is the only thing it can
 * take height from now that it sits inside it.
 *
 * Here rather than in `App.tsx` because the dock's splitter is rendered by
 * `AnalysisDock`, which used to carry a second copy of these numbers.
 */
export const BOUNDS = {
  rail: { min: 200, max: () => Math.min(480, window.innerWidth * 0.4) },
  inspector: { min: 280, max: () => Math.min(640, window.innerWidth * 0.5) },
  dock: {
    min: 218,
    max: () =>
      Math.max(
        218,
        (document.querySelector('.sv-center')?.getBoundingClientRect().height ??
          window.innerHeight) * 0.65
      )
  }
}

/** The persisted fields alone, for writing back. */
export function layoutOf(s: LayoutState): Layout {
  return {
    railW: s.railW,
    inspectorW: s.inspectorW,
    dockH: s.dockH,
    railCollapsed: s.railCollapsed,
    inspectorCollapsed: s.inspectorCollapsed,
    dockCollapsed: s.dockCollapsed,
    folded: s.folded,
    dockPanes: s.dockPanes
  }
}

/**
 * Read the stored layout once, then write changes back.
 *
 * A hook rather than a module-level effect, because `window.sensorview` is
 * installed by `installWebBridge()` in `main.tsx` and this module is imported
 * before that runs -- an effect is the first point at which the bridge is
 * certainly there.
 *
 * The write is debounced because the loudest writer is a splitter drag, which
 * produces one change per pointer event and would otherwise mean a JSON write
 * per pixel.
 */
export function useLayoutPersistence(): void {
  useEffect(() => {
    let live = true
    void window.sensorview.settings.get().then((stored) => {
      // Not if the user has already moved something: the read is a round trip
      // through the main process, and a drag can land first.
      if (live && stored.ok && stored.data && !touched) {
        useLayout.getState().hydrate(sanitiseLayout(stored.data.layout))
      }
    })

    let timer: ReturnType<typeof setTimeout> | undefined
    const stop = useLayout.subscribe((state) => {
      touched = true
      clearTimeout(timer)
      timer = setTimeout(() => {
        void window.sensorview.settings.set({ layout: layoutOf(state) })
      }, WRITE_AFTER_MS)
    })

    return () => {
      live = false
      clearTimeout(timer)
      stop()
    }
  }, [])
}

/** Long enough that a drag is one write, short enough to survive a quit. */
const WRITE_AFTER_MS = 400

/** Set by the first local change, so a late read cannot undo it. */
let touched = false
