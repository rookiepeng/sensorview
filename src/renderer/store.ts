// Application state.
//
// Zustand rather than context or a reducer, for one reason: the filter state is
// read by the frame builder on every slider tick and by the rail on every
// keystroke, and those are different components at different depths. A context
// would re-render the tree on each change; a store lets each subscriber pick
// the slice it cares about.
//
// Nothing here is async. Reads go through the bridge and land as plain values,
// so there is no loading machinery in the store itself -- a case is either open
// or it is not.

import { create } from 'zustand'

import {
  initialFilters,
  type ColumnMeta,
  type FilterState,
  type Table
} from '@shared/table'

import type { ScenePayload } from './frame'

export interface CaseState {
  /** Directory of the open case, or null. */
  dir: string | null
  /** The open log, once its table has been read. */
  table: Table | null
  /** Stem of the open log. */
  stem: string | null
  /** Column metadata from the manifest, driving labels, hover and the rail. */
  keys: Record<string, ColumnMeta>
  /** Per-column filters, one per declared key. */
  filters: FilterState
  /** Axis and colour columns. */
  axes: { x: string; y: string; z: string; colour: string }
  /** Slider position, which indexes the frame list -- not a frame id. */
  frame: number
  /** How many frames the open case has. */
  frameCount: number
  /** Past frames trailed behind the current one. */
  decay: number
  /** Whether the transport is playing. */
  playing: boolean
  /** Colormap name, as `sv_color` knows it. */
  colormap: string
  /** Point size varies by category when a categorical colour key is chosen. */
  sizeVary: boolean
  /** Rows hidden by clicking them, keyed by the table's own row index. */
  hidden: Set<number>
  /** The frame currently handed to the scene, or null before the first. */
  payload: ScenePayload | null
}

export interface Actions {
  openCase(dir: string, frameCount: number): void
  openLog(payload: {
    dir: string
    stem: string
    table: Table
    keys: CaseState['keys']
    axes: CaseState['axes']
  }): void
  setAxis(axis: keyof CaseState['axes'], column: string): void
  setNumericFilter(column: string, min: number, max: number): void
  setCategoryFilter(column: string, allowed: string[]): void
  resetFilters(): void
  closeCase(): void
  setFrame(frame: number): void
  stepFrame(delta: number): void
  setDecay(decay: number): void
  togglePlaying(): void
  setColormap(name: string): void
  setSizeVary(on: boolean): void
  toggleHidden(row: number): void
  setPayload(payload: ScenePayload | null): void
}

const initial: CaseState = {
  dir: null,
  table: null,
  stem: null,
  keys: {},
  filters: { numeric: [], categorical: [] },
  axes: { x: 'X', y: 'Y', z: 'Z', colour: 'X' },
  frame: 0,
  frameCount: 0,
  decay: 0,
  playing: false,
  colormap: 'Portland',
  sizeVary: false,
  hidden: new Set(),
  payload: null
}

export const useStore = create<CaseState & Actions>((set) => ({
  ...initial,

  openCase: (dir, frameCount) => set({ ...initial, dir, frameCount }),

  openLog: ({ dir, stem, table, keys, axes }) =>
    set({
      ...initial,
      dir,
      stem,
      table,
      keys,
      axes,
      filters: initialFilters(table, keys),
      frameCount: table.frameIds.length
    }),

  setAxis: (axis, column) => set((s) => ({ axes: { ...s.axes, [axis]: column } })),

  // Each setter replaces one entry and leaves the rest identical, so a frame
  // rebuild compares the array by reference and the untouched filters cost
  // nothing. Dragging a slider is the hot path here.
  setNumericFilter: (column, min, max) =>
    set((s) => ({
      filters: {
        ...s.filters,
        numeric: s.filters.numeric.map((entry) =>
          entry.column === column ? { column, min, max } : entry
        )
      }
    })),

  setCategoryFilter: (column, allowed) =>
    set((s) => ({
      filters: {
        ...s.filters,
        categorical: s.filters.categorical.map((entry) =>
          entry.column === column ? { column, allowed } : entry
        )
      }
    })),

  resetFilters: () =>
    set((s) => ({ filters: s.table ? initialFilters(s.table, s.keys) : initial.filters })),

  closeCase: () => set({ ...initial }),

  // Clamped rather than guarded at the call sites: loading a shorter case with
  // the slider parked near the end of a longer one is the case that produced
  // `clamp_frame_index` in the Python, and it is easier to make unrepresentable
  // here than to remember it at each caller.
  setFrame: (frame) =>
    set((s) => ({ frame: Math.min(Math.max(0, frame), Math.max(0, s.frameCount - 1)) })),
  stepFrame: (delta) =>
    set((s) => ({
      frame: Math.min(Math.max(0, s.frame + delta), Math.max(0, s.frameCount - 1))
    })),

  setDecay: (decay) => set({ decay: Math.max(0, decay) }),
  togglePlaying: () => set((s) => ({ playing: !s.playing })),
  setColormap: (colormap) => set({ colormap }),
  setSizeVary: (sizeVary) => set({ sizeVary }),

  toggleHidden: (row) =>
    set((s) => {
      // A new Set, not a mutation: subscribers compare by reference.
      const hidden = new Set(s.hidden)
      if (!hidden.delete(row)) {
        hidden.add(row)
      }
      return { hidden }
    }),

  setPayload: (payload) => set({ payload })
}))
