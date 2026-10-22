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

/** The overlays down each side, each shown or hidden on its own. */
export const OVERLAYS = {
  left: ['display', 'filters'],
  right: ['camera', 'curves']
} as const

export interface LayoutState extends Layout {
  setSize: (key: 'railW' | 'inspectorW' | 'dockH', px: number | null) => void
  toggle: (key: 'dockCollapsed') => void
  /** Show an overlay, or take it away. */
  toggleHidden: (id: string) => void
  /** Show one analysis pane or two. */
  setPanes: (count: number) => void
  /** Replace everything persisted, on the one read at startup. */
  hydrate: (stored: Layout) => void
}

export const useLayout = create<LayoutState>((set) => ({
  ...DEFAULT_LAYOUT,
  setSize: (key, px) => set({ [key]: px } as Pick<LayoutState, typeof key>),
  toggle: (key) => set((s) => ({ [key]: !s[key] }) as Pick<LayoutState, typeof key>),
  toggleHidden: (id) =>
    set((s) => ({
      hidden: s.hidden.includes(id) ? s.hidden.filter((name) => name !== id) : [...s.hidden, id]
    })),
  setPanes: (count) => set({ dockPanes: count === 1 ? 1 : 2 }),
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
  inspector: { min: 280, max: () => Math.min(760, window.innerWidth * 0.5) },
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
    dockCollapsed: s.dockCollapsed,
    hidden: s.hidden,
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
