// The analysis dock: two slots, each showing one of the analysis views.
//
// Two rather than a grid of six, carried over from the Dash dock: the views
// are for comparing, and two side by side at a readable size beats six at a
// size where none of them can be read. How many are showing is said once, in
// the head, rather than inferred from a slot set to "Empty" -- choosing a
// chart type of "nothing" to change the shape of the dock is a question
// answered in the wrong place.
//
// It sits at the foot of the centre column rather than across the whole
// window. Full width it was taking a third of the rail's and the inspector's
// height and spending it on two 780x280 letterboxes; in the centre the panes
// are about 450 wide, which is the shape a chart wants.
//
// Every view draws the **whole filtered table**, not the frame on the slider.
// A histogram of one frame's five hundred detections says nothing. That makes
// the dock the one place where the filters are the whole input, which is why
// the rows are gathered here and handed down rather than each view filtering
// for itself.

import { useEffect, useMemo, useRef, useState } from 'react'

import { filterAll, frameRows, type Table } from '@shared/table'
import type { DockSlot } from '@shared/types'

import { maskedRows } from '../figures/common'
import { buildView, VIEW_LABELS, type ViewId, type ViewOptions } from '../figures/views'
import { ToggleGroup } from 'radix-ui'

import { CollapseButton, IconButton, Picker, Switch } from './Controls'
import { useLayout } from '../layout'
import { PlotlyFigure } from './PlotlyFigure'
import { useStore } from '../store'

interface SlotState {
  view: ViewId
  x: string
  y: string
  colour: string
  dimensions: string[]
  logScale: boolean
  histnorm: 'probability' | 'density'
  /**
   * Whether a scatter draws this frame or every frame.
   *
   * Only the scatters had this in the Dash app, and it defaulted to the
   * current frame. The other four views have no such switch and always drew
   * the whole filtered table, which is what a distribution is of.
   */
  scope: 'current' | 'all'
  /**
   * Fixed axis limits, as typed.
   *
   * Kept as strings so a half-typed "-" or an empty box is a state rather
   * than a NaN. An end left empty means autorange for that axis, which is
   * what the pane does by default.
   */
  limits: { xMin: string; xMax: string; yMin: string; yMax: string }
}

/**
 * The dock width below which a second pane is not worth having.
 *
 * A pane's control strip is a view picker and up to four others plus the
 * limits button, which needs about 360px to stay on one row, and a chart
 * under it wants at least as much again. Two of those in less than this and
 * both are unreadable, so the dock shows one until there is room -- without
 * forgetting that two were asked for.
 */
const TWO_PANES_MIN = 680

/** As the layout's: long enough that a drag or a typed limit is one write. */
const WRITE_AFTER_MS = 400

const EMPTY: SlotState = {
  view: 'histogram',
  x: '',
  y: '',
  colour: 'None',
  dimensions: [],
  logScale: false,
  histnorm: 'probability',
  scope: 'current',
  limits: { xMin: '', xMax: '', yMin: '', yMax: '' }
}

export function AnalysisDock({ theme }: { theme: 'dark' | 'light' }) {
  const table = useStore((s) => s.table)
  const filters = useStore((s) => s.filters)
  const keys = useStore((s) => s.keys)
  const colormap = useStore((s) => s.colormap)
  const stems = useStore((s) => s.stems)
  // Visibility lives in a typed array on the table, which a memo cannot see
  // change; this is what tells it to re-filter.
  const visibleRev = useStore((s) => s.visibleRev)
  const frame = useStore((s) => s.frame)
  const hideRows = useStore((s) => s.hideRows)
  const showRows = useStore((s) => s.showRows)

  const collapsed = useLayout((s) => s.dockCollapsed)
  const toggleCollapsed = useLayout((s) => s.toggle)
  const wanted = useLayout((s) => s.dockPanes)
  const setPanes = useLayout((s) => s.setPanes)
  const dock = useRef<HTMLDivElement>(null)
  // Measured rather than derived from the window: the dock is as wide as
  // the gap the overlays leave, so hiding one changes this without the
  // window moving at all.
  const [cramped, setCramped] = useState(false)
  const [selection, setSelection] = useState<number[]>([])
  // The second slot keeps its settings while it is hidden, so going back to
  // two panes returns the one that was there rather than a fresh default.
  const [slots, setSlots] = useState<[SlotState, SlotState]>([
    { ...EMPTY, view: 'histogram' },
    { ...EMPTY, view: 'scatter' }
  ])
  const dir = useStore((s) => s.dir)
  // The panes this case was left with, once the read for them has landed.
  // State rather than applied on the spot, because they cannot be settled
  // until a table says which columns exist -- which is the effect below.
  const [saved, setSaved] = useState<[DockSlot, DockSlot] | null>(null)
  // The case whose panes have been read back. Until this matches, a write
  // would save the defaults over the settings being read.
  const read = useRef<string | null>(null)

  // One pass over the table per filter change, shared by both slots.
  const rows = useMemo(
    () => {
    // `visibleRev` is a real dependency: the visibility it stands for lives
    // in a typed array that is mutated in place, which a memo cannot see.
    // Referenced rather than only listed, so the rule agrees.
    void visibleRev
      return table ? maskedRows(filterAll(table, filters)) : new Int32Array(0)
    },
    [table, filters, visibleRev]
  )

  const numeric = useMemo(
    () =>
      table
        ? [...table.columns.values()].filter((c) => c.kind === 'number').map((c) => c.name)
        : [],
    [table]
  )
  // The frame column is selectable but never chosen for you: a scatter of
  // frame against time is a straight line, which is a dull thing to greet
  // someone with when the position columns are right there.
  const preferred = useMemo(
    () => numeric.filter((name) => name !== table?.frameKey),
    [numeric, table]
  )
  const categorical = useMemo(
    () =>
      table
        ? [...table.columns.values()].filter((c) => c.kind === 'string').map((c) => c.name)
        : [],
    [table]
  )

  // `table` is the dependency, not nothing: this component returns null
  // until one arrives, so on the first run there is no dock to observe --
  // and with an empty dependency list the effect would never look again.
  useEffect(() => {
    const element = dock.current
    if (!element) {
      return
    }
    const observer = new ResizeObserver(([entry]) => {
      setCramped((entry?.contentRect.width ?? 0) < TWO_PANES_MIN)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [table])

  // The panes this case was last set up with. Read per case rather than per
  // log: switching logs inside a case is not a reason to lose a chart, and
  // the reconciliation below handles a log that lacks a column the saved
  // pane names.
  useEffect(() => {
    if (!dir) {
      return
    }
    let live = true
    read.current = null
    setSaved(null)
    void window.sensorview.settings.get().then((stored) => {
      if (!live) {
        return
      }
      const panes = stored.ok ? stored.data?.views[dir]?.slots : undefined
      // Not over a pane the user has already picked: the read is a round
      // trip through the main process and a click can land first.
      if (panes && read.current === null) {
        setSaved(panes)
      }
      read.current = dir
    })
    return () => {
      live = false
    }
  }, [dir])

  // A slot's columns cannot be chosen until a table says which exist, and
  // they have to be re-chosen when the log changes: a column name that is not
  // in the new table reads back as zeros from every row, which draws a
  // plausible-looking chart of nothing. That was this component's first bug.
  //
  // Restored panes come through here too, which is why `saved` is a
  // dependency rather than something applied where it is read: a saved pane
  // is as much in need of reconciling as a default one.
  useEffect(() => {
    if (numeric.length === 0 && categorical.length === 0) {
      return
    }
    setSlots((current) => {
      const base = saved
        ? ([restore(saved[0], 'histogram'), restore(saved[1], 'scatter')] as const)
        : current
      return [
        defaults(base[0], numeric, categorical, preferred),
        defaults(base[1], numeric, categorical, preferred)
      ]
    })
    // Consumed, so that a later log switch reconciles what is on screen
    // rather than putting the stored panes back over it.
    if (saved) {
      setSaved(null)
    }
  }, [numeric, categorical, preferred, saved])

  // Write the panes back, debounced: a column picker is one change, but an
  // axis limit is one per keystroke.
  useEffect(() => {
    if (!dir || read.current !== dir) {
      return
    }
    const timer = setTimeout(() => {
      void window.sensorview.settings.rememberView(dir, { slots })
    }, WRITE_AFTER_MS)
    return () => clearTimeout(timer)
  }, [dir, slots])

  if (!table) {
    return null
  }

  // A selection is remembered rather than acted on: hiding on the lasso
  // itself would make an accidental drag destructive, and there is no undo
  // for something that leaves no trace of what it removed.
  const selectRows = (rows: number[]) => setSelection(rows)

  // What is actually on screen, which is two only if two will fit.
  const panes = cramped ? 1 : wanted

  const set = (index: 0 | 1, patch: Partial<SlotState>) => {
    // The user has picked a pane, so a read still in flight leaves it alone
    // and changes from here on are written back.
    read.current = dir
    setSlots((current) => {
      const next: [SlotState, SlotState] = [current[0], current[1]]
      next[index] = defaults({ ...next[index], ...patch }, numeric, categorical, preferred)
      return next
    })
  }

  return (
    // The handle above this, and the height it sets, belong to the panel
    // group in `App.tsx` now. What is left here is the dock itself.
    <div className={`sv-dock${collapsed ? ' sv-collapsed' : ''}`} ref={dock}>
        <div className="sv-dock-head">
          {/* How many panes, said as a shape. Each pane's own view is picked
              on the pane, where the chart it names is. */}
          {/* One of two, so a single-select group rather than two toggle
              buttons that happened to agree. The items are written out here
              rather than through `IconButton`: they need Radix's own props
              and its ref, and `IconButton` passes on neither. */}
          <ToggleGroup.Root
            type="single"
            className="sv-dock-layout"
            aria-label="Analysis panes"
            value={String(panes)}
            // Empty means the active one was pressed again. There is no
            // "no panes", so that answer is ignored.
            onValueChange={(next) => {
              if (next) {
                setPanes(Number(next))
              }
            }}
          >
            <ToggleGroup.Item
              value="1"
              className="sv-icon-btn"
              title="One pane"
              aria-label="One pane"
            >
              <i className="bi bi-square" aria-hidden="true" />
            </ToggleGroup.Item>
            <ToggleGroup.Item
              value="2"
              className="sv-icon-btn"
              disabled={cramped}
              title={
                cramped
                  ? 'Not enough width for two panes -- widen the window, or hide a panel'
                  : 'Two panes, side by side'
              }
              aria-label="Two panes, side by side"
            >
              <i className="bi bi-layout-split" aria-hidden="true" />
            </ToggleGroup.Item>
          </ToggleGroup.Root>

          {/* Swapping beats re-picking both views when the comparison is the
              right way round but on the wrong sides. Nothing to swap with
              one pane. */}
          {panes === 2 && (
            <IconButton
              icon="arrow-left-right"
              title="Swap the two panes"
              onClick={() => setSlots((current) => [current[1], current[0]])}
            />
          )}

          {/* What to do with a selection, beside the dock's own controls.
              Present only while something is selected -- two buttons that do
              nothing are worse than none. */}
          {selection.length > 0 && (
            <div className="sv-dock-selection">
              <span className="sv-export-note">{selection.length} selected</span>
              <button
                type="button"
                className="sv-text-btn"
                onClick={() => {
                  hideRows(selection)
                  setSelection([])
                }}
              >
                Hide
              </button>
              <button
                type="button"
                className="sv-text-btn"
                onClick={() => {
                  showRows(selection)
                  setSelection([])
                }}
              >
                Show
              </button>
            </div>
          )}

          <div className="sv-dock-actions">
            <CollapseButton
              collapsed={collapsed}
              onToggle={() => toggleCollapsed('dockCollapsed')}
              subject="dock"
              edge="bottom"
            />
          </div>
        </div>

        <div className="sv-dock-grid">
          {([0, 1] as const).slice(0, panes).map((index) => {
            const slot = slots[index]
            // A view is chosen but the table has no column of the kind it
            // needs -- a violin with nothing categorical, a histogram with
            // nothing numeric. This used to draw a blank pane under a
            // picker that said "Histogram", which reads as a broken figure.
            if (!slot.x) {
              return (
                <div key={index} className={`sv-dock-pane sv-slot-${index === 0 ? 'a' : 'b'}`}>
                  <p className="sv-rail-note">
                    {slot.view === 'violin'
                      ? 'This table has no categorical column for a violin plot.'
                      : 'This table has no numeric column for this view.'}
                  </p>
                </div>
              )
            }
            return (
              <div
                key={index}
                className={`sv-dock-pane sv-slot-${index === 0 ? 'a' : 'b'}${
                  panes === 2 && index === 1 ? ' sv-slot-paired' : ''
                }`}
              >
                <Pane
                  slot={slot}
                  table={table}
                  rows={rows}
                  keys={keys}
                  colormap={colormap}
                  theme={theme}
                  numeric={numeric}
                  categorical={categorical}
                  stems={stems}
                  frame={frame}
                  onSelectRows={selectRows}
                  onChange={(patch) => set(index, patch)}
                />
              </div>
            )
          })}
        </div>
      </div>
  )
}

/**
 * A stored pane, narrowed back to one this component can draw.
 *
 * The settings file carries panes loosely -- `view` is any string there --
 * because this is the only place that knows which chart types exist. Columns
 * are taken as given and settled by `defaults`, which does that for the panes
 * built here as well.
 *
 * @param fallback The chart type for a pane whose stored one is unknown,
 *     which is the one this slot would have opened with.
 */
function restore(raw: DockSlot | undefined, fallback: ViewId): SlotState {
  const it = raw ?? {}
  const text = (value: unknown, instead: string) =>
    typeof value === 'string' ? value : instead
  return {
    view: it.view && it.view in VIEW_LABELS ? (it.view as ViewId) : fallback,
    x: text(it.x, ''),
    y: text(it.y, ''),
    colour: text(it.colour, 'None'),
    dimensions: Array.isArray(it.dimensions)
      ? it.dimensions.filter((name): name is string => typeof name === 'string')
      : [],
    logScale: it.logScale === true,
    histnorm: it.histnorm === 'density' ? 'density' : 'probability',
    scope: it.scope === 'all' ? 'all' : 'current',
    limits: {
      xMin: text(it.limits?.xMin, ''),
      xMax: text(it.limits?.xMax, ''),
      yMin: text(it.limits?.yMin, ''),
      yMax: text(it.limits?.yMax, '')
    }
  }
}

/**
 * Fill in the columns a view needs but has not been given one for.
 *
 * Run on every change rather than only on the first, because switching view
 * changes which fields are read: a histogram needs only x, and switching it to
 * a scatter with no y would draw nothing and look broken.
 */
function defaults(
  slot: SlotState,
  numeric: string[],
  categorical: string[],
  preferred: string[]
): SlotState {
  const next = { ...slot }
  if (!numeric.includes(next.x)) {
    next.x = preferred[0] ?? numeric[0] ?? ''
  }
  if (!numeric.includes(next.y)) {
    next.y = preferred[1] ?? preferred[0] ?? numeric[0] ?? ''
  }
  if (next.colour !== 'None' && ![...numeric, ...categorical].includes(next.colour)) {
    next.colour = categorical[0] ?? 'None'
  }
  if (next.view === 'violin' && !categorical.includes(next.x)) {
    // A violin's x is what it groups by, so it is a category, not a number.
    next.x = categorical[0] ?? ''
  }
  if (next.view === 'parcats' && next.dimensions.length === 0) {
    next.dimensions = categorical.slice(0, 2)
  }
  return next
}

function Pane({
  slot,
  table,
  rows,
  keys,
  colormap,
  theme,
  numeric,
  categorical,
  stems,
  frame,
  onSelectRows,
  onChange
}: {
  slot: SlotState
  table: Table
  rows: Int32Array
  keys: ViewOptions['keys']
  colormap: string
  theme: 'dark' | 'light'
  numeric: string[]
  categorical: string[]
  stems: string[]
  frame: number
  onSelectRows: (rows: number[]) => void
  onChange: (patch: Partial<SlotState>) => void
}) {
  // The scatter's scope narrows the shared rows to the frame on the slider.
  // `frameRows` is what `buildFrame` uses, so a current-frame scatter and the
  // scene resolve a slider position identically.
  const scoped = useMemo(() => {
    if (slot.view !== 'scatter' || slot.scope === 'all') {
      return rows
    }
    const wanted = new Set(frameRows(table, frame))
    return rows.filter((row) => wanted.has(row))
  }, [slot.view, slot.scope, rows, table, frame])

  const [showLimits, setShowLimits] = useState(false)

  const figure = useMemo(
    () =>
      buildView(slot.view, table, scoped, {
        x: slot.x,
        y: slot.y,
        colour: slot.colour,
        dimensions: slot.dimensions,
        colormap,
        keys,
        theme,
        histnorm: slot.histnorm,
        logScale: slot.logScale
      }),
    [slot, table, scoped, colormap, keys, theme]
  )

  // Applied over the built figure rather than inside the builders: a limit is
  // a view setting, not a property of the data, and the builders stay pure
  // functions of the table.
  const limited = useMemo(() => {
    const span = (low: string, high: string) => {
      const a = Number.parseFloat(low)
      const b = Number.parseFloat(high)
      return Number.isFinite(a) && Number.isFinite(b) ? ([a, b] as [number, number]) : null
    }
    const x = span(slot.limits.xMin, slot.limits.xMax)
    const y = span(slot.limits.yMin, slot.limits.yMax)
    if (!x && !y) {
      return figure
    }
    return {
      data: figure.data,
      layout: {
        ...figure.layout,
        xaxis: { ...figure.layout.xaxis, ...(x ? { range: x, autorange: false } : {}) },
        yaxis: { ...figure.layout.yaxis, ...(y ? { range: y, autorange: false } : {}) }
      }
    }
  }, [figure, slot.limits])

  const view = slot.view
  const revision = [stems.join('+'), view, slot.x, slot.y, slot.colour].join('|')
  const wantsY = view === 'scatter' || view === 'heatmap' || view === 'violin'
  const xChoices = view === 'violin' ? categorical : numeric

  return (
    <div className="sv-pane">
      <div className="sv-pane-controls">
        {/* The pane's own title: what it is a chart of. In the head it was
            one of two anonymous selects labelled only by position. */}
        <Picker
          label="View"
          value={slot.view}
          choices={(Object.keys(VIEW_LABELS) as ViewId[]).map((id) => ({
            value: id,
            label: VIEW_LABELS[id]
          }))}
          onChange={(view) => onChange({ view: view as ViewId })}
          className="sv-pane-field sv-slot-picker"
        />
        {/* Only the scatter: the other four draw a distribution, which one
            frame's few hundred points does not describe. */}
        {view === 'scatter' && (
          <Picker
            label="Frames"
            value={slot.scope}
            choices={['current', 'all']}
            onChange={(scope) => onChange({ scope: scope as SlotState['scope'] })}
          />
        )}
        {view !== 'parcats' && (
          <Picker
            label="X"
            value={slot.x}
            choices={xChoices}
            onChange={(x) => onChange({ x })}
          />
        )}
        {wantsY && (
          <Picker label="Y" value={slot.y} choices={numeric} onChange={(y) => onChange({ y })} />
        )}
        {view !== 'heatmap' && (
          <Picker
            label="Colour"
            value={slot.colour}
            choices={['None', ...categorical, ...numeric]}
            onChange={(colour) => onChange({ colour })}
          />
        )}
        {view === 'histogram' && (
          <Picker
            label="Norm"
            value={slot.histnorm}
            choices={['probability', 'density']}
            onChange={(histnorm) =>
              onChange({ histnorm: histnorm as SlotState['histnorm'] })
            }
          />
        )}
        {view === 'heatmap' && (
          <Switch checked={slot.logScale} onChange={(logScale) => onChange({ logScale })}>
            Log counts
          </Switch>
        )}
        {/* Limits last in the strip, since they are set once and then left
            alone -- unlike the pickers beside them. */}
        {view !== 'parcats' && (
          <button
            type="button"
            className={`sv-icon-btn sv-limits-btn${showLimits ? ' sv-limits-on' : ''}`}
            onClick={() => setShowLimits((on) => !on)}
            aria-expanded={showLimits}
            aria-label="Set fixed axis limits"
            title="Set fixed axis limits"
          >
            <i className="bi bi-arrows-angle-expand" />
          </button>
        )}
        {view === 'parcats' &&
          [0, 1, 2].map((at) => (
            <Picker
              key={at}
              label={`Dim ${at + 1}`}
              value={slot.dimensions[at] ?? 'None'}
              choices={['None', ...categorical]}
              onChange={(name) => {
                const dimensions = [...slot.dimensions]
                if (name === 'None') {
                  dimensions.splice(at, 1)
                } else {
                  dimensions[at] = name
                }
                onChange({ dimensions: dimensions.filter(Boolean) })
              }}
            />
          ))}
      </div>

      {showLimits && view !== 'parcats' && (
        <div className="sv-pane-controls sv-pane-limits">
          {(
            [
              ['xMin', 'x min'],
              ['xMax', 'x max'],
              ['yMin', 'y min'],
              ['yMax', 'y max']
            ] as const
          ).map(([field, label]) => (
            <label className="sv-pane-field" key={field}>
              <span className="sv-section-label">{label}</span>
              <input
                type="number"
                value={slot.limits[field]}
                placeholder="auto"
                onChange={(event) =>
                  onChange({ limits: { ...slot.limits, [field]: event.target.value } })
                }
              />
            </label>
          ))}
          <button
            type="button"
            className="sv-text-btn"
            onClick={() => onChange({ limits: { xMin: '', xMax: '', yMin: '', yMax: '' } })}
          >
            Auto
          </button>
        </div>
      )}

      <PlotlyFigure
        data={limited.data}
        layout={limited.layout}
        className="sv-pane-graph"
        // The axes follow what the figure is of. A zoom has to survive a
        // slider tick -- that is the whole reason uirevision exists -- and
        // must not survive a change of view, of column, or of which logs are
        // loaded, each of which is a different extent entirely.
        revision={revision}
        // Only the scatter carries row ids, so only it can turn a selection
        // into a visibility change. A lasso on a histogram encloses bars,
        // not rows.
        onSelected={view === 'scatter' ? onSelectRows : undefined}
        // The toolbar is how box and lasso select are reached. Without it
        // the selection path exists and nothing can start one.
        tools
        
      />
    </div>
  )
}
