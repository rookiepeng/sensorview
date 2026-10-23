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

import type { CaseSummary, CaseView, CloudDisplay, ReferenceFrame } from '@shared/types'
import type { Visibility } from '@shared/table'
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
  /**
   * The open case, which outlives the log inside it.
   *
   * Kept so that switching logs reads a table and nothing else -- the
   * directory, the manifest and the column metadata are the case's, not the
   * log's, and re-reading them per switch would be work for an answer that
   * cannot have changed.
   */
  summary: CaseSummary | null
  /** The open log, once its table has been read. */
  table: Table | null
  /** Stem of the primary log -- the one views with room for one answer use. */
  stem: string | null
  /** Every open log's stem, primary first. */
  stems: string[]
  /**
   * Every log that recorded each slider position, the primary first.
   *
   * Combining logs concatenates their rows, so a frame id is the only thing
   * tying a position back to the log whose sidecars hold its cloud, pose,
   * curves and video -- and two logs are free to number their frames the
   * same way.
   */
  ownerSets: string[][]
  /** Column metadata from the manifest, driving labels, hover and the rail. */
  keys: Record<string, ColumnMeta>
  /** Per-column filters, one per declared key. */
  filters: FilterState
  /** How this case draws its cloud, or null when it declares none. */
  cloudDisplay: CloudDisplay | null
  /** Whether the cloud is drawn. Off until the user asks: it is the one thing
   *  here that costs a read per frame. */
  cloudOn: boolean
  /** The cloud already read, and which frame it belongs to. */
  cloud: { frameId: number; position: Float32Array; count: number } | null
  /**
   * Why the last cloud read failed, if it did.
   *
   * A failed read used to be indistinguishable from an empty frame: the
   * cloud blinked out and the rail's switch went on saying it was enabled.
   */
  cloudError: string | null
  /** Why the last reference read failed, if it did. */
  referenceError: string | null
  /** Where the reference sits in the open frame, or null when it has no row. */
  reference: ReferenceFrame | null
  /**
   * The reference's extent across the whole log.
   *
   * The axis box is fixed from the filters, so without this a reference that
   * travels outside them is clipped away rather than widening them.
   */
  referenceBounds: Record<'x' | 'y' | 'z', [number, number]> | null
  /** Axis and colour columns. */
  axes: { x: string; y: string; z: string; colour: string }
  /**
   * A frame column the user chose that the open table is not indexed on.
   *
   * Re-indexing means rebuilding the table, which only the loader can do --
   * so this is a request, picked up by `TopBar` and cleared once honoured.
   * The alternative was a second copy of the loader here.
   */
  pendingFrameKey: string | null
  /** Slider position, which indexes the frame list -- not a frame id. */
  frame: number
  /** How many frames the open case has. */
  frameCount: number
  /** Past frames trailed behind the current one. */
  decay: number
  /**
   * Draw every filtered frame at once.
   *
   * Distinct from decay, which trails a fixed number behind the current
   * frame. Overlay ignores the slider entirely.
   */
  overlay: boolean
  /** Whether the transport is playing. */
  playing: boolean
  /** Colormap name, as `sv_color` knows it. */
  colormap: string
  /** Point size varies by category when a categorical colour key is chosen. */
  sizeVary: boolean
  /**
   * How many rows the user has hidden.
   *
   * The state itself lives in `table.visible`, which is where `filterAll`
   * reads it and therefore the only place that can make the scene, the dock
   * and an export agree. This is the count, for the read-out; `visibleRev`
   * is what tells a memo the array changed, since mutating a typed array in
   * place cannot.
   */
  hiddenCount: number
  visibleRev: number
  /**
   * Whether clicking a point in the scene hides it.
   *
   * Off by default. The scene is something you spend the session dragging to
   * look around, and a stray click that silently removes a detection -- with
   * nothing on screen saying which -- is a bad default for a control that
   * can only be noticed after it has fired.
   */
  clickToHide: boolean
  /** The frame currently handed to the scene, or null before the first. */
  payload: ScenePayload | null
  /**
   * What a load is doing right now -- "Reading 4 logs", "Indexing 1.2M
   * rows" -- or null when nothing is. The scene shows it over itself, because
   * a large table takes long enough to read and index that a window with the
   * old log still on it looks like it ignored the click.
   */
  loading: string | null
  /**
   * The open logs whose inspector reads have all come back, as a
   * `caseKey`. Until they have, whether the inspector column exists at all
   * is unknown, and showing the case would draw it full width and then
   * shift everything over when the column arrives.
   */
  settledFor: string | null
  /** The open logs now on screen, as a `caseKey`. See `useSettling`. */
  revealedFor: string | null
}

export interface Actions {
  openCase(dir: string, frameCount: number): void
  setSummary(summary: CaseSummary | null): void
  setLoading(loading: string | null): void
  setSettled(key: string | null): void
  setRevealed(key: string | null): void
  openLog(payload: {
    dir: string
    stem: string
    stems: string[]
    ownerSets: string[][]
    table: Table
    keys: CaseState['keys']
    axes: CaseState['axes']
    cloudDisplay: CloudDisplay | null
  }): void
  setCloudOn(on: boolean): void
  setReference(reference: ReferenceFrame | null, error?: string | null): void
  setReferenceBounds(bounds: CaseState['referenceBounds']): void
  setCloud(cloud: CaseState['cloud'], error?: string | null): void
  setAxis(axis: keyof CaseState['axes'], column: string): void
  reopenWithFrameKey(column: string): void
  clearFrameKey(): void
  setNumericFilter(column: string, min: number, max: number): void
  setCategoryFilter(column: string, allowed: string[]): void
  resetFilters(): void
  closeCase(): void
  setFrame(frame: number): void
  stepFrame(delta: number): void
  setDecay(decay: number): void
  setOverlay(on: boolean): void
  togglePlaying(): void
  setColormap(name: string): void
  setSizeVary(on: boolean): void
  toggleHidden(row: number): void
  setClickToHide(on: boolean): void
  applyView(view: CaseView): void
  hideRows(rows: ArrayLike<number>): void
  showRows(rows: ArrayLike<number>): void
  showAllRows(): void
  setVisibility(states: Visibility[]): void
  setPayload(payload: ScenePayload | null): void
}

const initial: CaseState = {
  dir: null,
  summary: null,
  table: null,
  stem: null,
  stems: [],
  ownerSets: [],
  keys: {},
  filters: { numeric: [], categorical: [] },
  cloudDisplay: null,
  cloudOn: false,
  cloud: null,
  cloudError: null,
  referenceError: null,
  reference: null,
  referenceBounds: null,
  axes: { x: 'X', y: 'Y', z: 'Z', colour: 'X' },
  pendingFrameKey: null,
  frame: 0,
  frameCount: 0,
  decay: 0,
  overlay: false,
  playing: false,
  colormap: 'Portland',
  sizeVary: false,
  hiddenCount: 0,
  visibleRev: 0,
  clickToHide: false,
  payload: null,
  loading: null,
  settledFor: null,
  revealedFor: null
}

export const useStore = create<CaseState & Actions>((set) => ({
  ...initial,

  openCase: (dir, frameCount) => set({ ...initial, dir, frameCount }),

  setSummary: (summary) => set({ summary }),

  setLoading: (loading) => set({ loading }),
  setSettled: (settledFor) => set({ settledFor }),
  setRevealed: (revealedFor) => set({ revealedFor }),

  openLog: ({ dir, stem, stems, ownerSets, table, keys, axes, cloudDisplay }) =>
    set((s) => ({
      ...initial,
      // Everything about the log resets; the case does not. Spreading
      // `initial` over the summary would empty the picker on every switch.
      summary: s.summary,
      dir,
      stem,
      stems,
      ownerSets,
      table,
      keys,
      axes,
      cloudDisplay,
      filters: initialFilters(table, keys),
      frameCount: table.frameIds.length
    })),

  setAxis: (axis, column) => set((s) => ({ axes: { ...s.axes, [axis]: column } })),

  reopenWithFrameKey: (column) => set({ pendingFrameKey: column }),
  clearFrameKey: () => set({ pendingFrameKey: null }),

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
  setOverlay: (overlay) => set({ overlay }),
  togglePlaying: () => set((s) => ({ playing: !s.playing })),
  setColormap: (colormap) => set({ colormap }),
  setSizeVary: (sizeVary) => set({ sizeVary }),

  // All four write into `table.visible` -- 0 visible, 1 hidden -- rather than
  // into a Set beside it. A second copy of this state is what let a point
  // hidden by clicking in the scene go on showing in every 2D view.
  toggleHidden: (row) =>
    set((s) => {
      if (!s.table || row < 0 || row >= s.table.rows) {
        return {}
      }
      const was = s.table.visible[row]!
      s.table.visible[row] = was === 1 ? 0 : 1
      return {
        hiddenCount: s.hiddenCount + (was === 1 ? -1 : 1),
        visibleRev: s.visibleRev + 1
      }
    }),

  setClickToHide: (clickToHide) => set({ clickToHide }),

  // Everything here is checked against the open case rather than trusted,
  // because a stored view is a view of whatever that directory held last
  // time: a log can gain and lose columns between sessions, and an axis
  // naming one that is gone reads back as zeros from every row -- a scene
  // that looks drawn and is of nothing.
  applyView: (view) =>
    set((s) => {
      if (!s.table) {
        return {}
      }
      const column = (name: string | undefined, current: string) =>
        name && s.table!.columns.has(name) ? name : current
      return {
        axes: {
          x: column(view.axes?.x, s.axes.x),
          y: column(view.axes?.y, s.axes.y),
          z: column(view.axes?.z, s.axes.z),
          colour: column(view.axes?.colour, s.axes.colour)
        },
        colormap: view.colormap ?? s.colormap,
        // The rail's slider stops at ten, and a decay of four hundred is
        // four hundred frames built per tick.
        decay: Math.min(MAX_DECAY, view.decay ?? s.decay),
        overlay: view.overlay ?? s.overlay,
        // Only where there is a cloud to read. A case that declares none
        // would answer every frame with an error the user never asked for.
        cloudOn: s.cloudDisplay ? (view.cloudOn ?? s.cloudOn) : false,
        sizeVary: view.sizeVary ?? s.sizeVary,
        clickToHide: view.clickToHide ?? s.clickToHide
      }
    }),

  hideRows: (rows) => set((s) => mark(s, rows, 1)),
  showRows: (rows) => set((s) => mark(s, rows, 0)),

  showAllRows: () =>
    set((s) => {
      if (!s.table || s.hiddenCount === 0) {
        return {}
      }
      s.table.visible.fill(0)
      return { hiddenCount: 0, visibleRev: s.visibleRev + 1 }
    }),

  // Which states the views show, as `filterAll` reads it: exactly one filters,
  // none passes nothing, and two or more is the deliberate no-op that means
  // "show hidden points as well".
  setVisibility: (states) =>
    set((s) => ({ filters: { ...s.filters, visible: states } })),

  // Turning the cloud off drops what was read with it: the frame it belongs
  // to will have moved on by the time it is turned back on, and a stale cloud
  // under a live frame is worse than none.
  setCloudOn: (cloudOn) =>
    set(cloudOn ? { cloudOn, cloudError: null } : { cloudOn, cloud: null, cloudError: null }),
  setCloud: (cloud, error = null) => set({ cloud, cloudError: error }),
  setReference: (reference, error = null) => set({ reference, referenceError: error }),
  setReferenceBounds: (referenceBounds) => set({ referenceBounds }),

  setPayload: (payload) => set({ payload })
}))

/** The decay slider's top end, as `FilterRail` draws it. */
const MAX_DECAY = 10

/**
 * Set a run of rows to one visibility, counting the change.
 *
 * Returns an empty patch when nothing moved, so a lasso over rows that are
 * already hidden does not bump `visibleRev` and redraw every view.
 */
function mark(
  state: CaseState,
  rows: ArrayLike<number>,
  to: 0 | 1
): Partial<CaseState> {
  if (!state.table) {
    return {}
  }
  const { visible, rows: total } = state.table
  let moved = 0
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]!
    if (row >= 0 && row < total && visible[row] !== to) {
      visible[row] = to
      moved++
    }
  }
  if (moved === 0) {
    return {}
  }
  return {
    hiddenCount: state.hiddenCount + (to === 1 ? moved : -moved),
    visibleRev: state.visibleRev + 1
  }
}

/** Which logs are open, as one comparable string. */
export function caseKey(dir: string | null, stems: readonly string[]): string {
  return `${dir ?? ''}\n${stems.join('\n')}`
}

/**
 * True while a case is open but not yet shown.
 *
 * Opening a log is followed by the inspector's own reads, and only once
 * those land is it known whether there is an inspector column. The shell
 * stays hidden behind the "Opening ..." plate until then, so the first
 * layout anyone sees is the final one. Derived from the store in the same
 * render the case changes in, so there is no frame in which a new case is
 * marked as shown.
 */
export function useSettling(): boolean {
  return useStore(
    (s) => s.frameCount > 0 && s.revealedFor !== caseKey(s.dir, s.stems)
  )
}
