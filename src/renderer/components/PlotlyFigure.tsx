// A Plotly figure, wrapped thinly.
//
// `Plotly.react` directly rather than `react-plotly.js`: the wrapper exists to
// make a figure look like a React component, and the cost of that is a
// re-render per update of a thing that updates on every slider tick. This
// keeps the figure out of the React tree -- the div is React's, everything
// inside it is Plotly's.
//
// `uirevision` is load-bearing. Without it `Plotly.react` resets the axes on
// every call, so a zoomed curve snaps back to default the moment the slider
// moves. It is a value rather than a constant so that it can change when the
// figure's subject does -- see `revision`.

import { useEffect, useRef } from 'react'

import Plotly from '../lib/plotly'

export interface PlotlyFigureProps {
  data: Partial<Plotly.Data>[]
  layout: Partial<Plotly.Layout>
  className?: string
  /**
   * What the figure is of.
   *
   * Plotly keeps the axes across a `react` call while this is unchanged,
   * which is the point -- a zoomed plot must not snap back every slider
   * tick. But it keeps them when the data changes scope too, so combining a
   * second log left the axes on the first one's range. Changing this with
   * the subject is what lets the new data pick its own.
   */
  revision?: string
  /**
   * Called with the table rows a lasso or box enclosed.
   *
   * Plotly fires `plotly_selected` with `undefined` when a selection is
   * cleared by double-click; that arrives here as an empty array, which is
   * the deselect and not an error.
   */
  onSelected?: (rows: number[]) => void
  /**
   * Called as a box or lasso drag starts selecting, and again as it moves.
   *
   * Plotly works out the enclosed points during the drag and again on
   * release, synchronously -- on a scatter of every frame that is seconds
   * with nothing painted. This is the moment to put a message up, while
   * there is still a frame to paint it in.
   */
  onSelecting?: () => void
  /**
   * Show Plotly's toolbar.
   *
   * On for anything a selection can be made in; off for the inspector's
   * curve plots, which are small, read-only and would lose a third of their
   * height to it.
   */
  tools?: boolean
}

const BASE = {
  responsive: true,
  // Nothing here is a document to be downloaded: the export menu does that
  // deliberately, at the right size, and with the data rebuilt rather than
  // scraped off the page.
  staticPlot: false,
  displaylogo: false,
  // Plotly 4 turned this on by default: a "Share chart" button that sends
  // the chart's data to an external server. Nothing here is shared that way,
  // and a click on it would put sensor data on someone else's machine.
  showSendToCloud: false
}

/**
 * The toolbar, for the figures that need one.
 *
 * Box and lasso select are the point: they are how a selection is made at
 * all, and without the toolbar there is no way to reach either -- which is
 * what a modeBar-less dock meant for everything built on top of them.
 *
 * `toImage` is dropped because the export menu owns that and does it better;
 * the autoscale and reset pair is kept because fixed limits make it possible
 * to lose the data off-screen. The share button goes too, by its Plotly 4
 * name -- `sendDataToCloud` was the old one, and no longer removed anything.
 *
 * Shown on hover only: a row of icons over the top of every chart covers
 * the data it sits on, and it is needed for the moment of making a selection.
 */
const WITH_TOOLS = {
  ...BASE,
  displayModeBar: 'hover' as const,
  modeBarButtonsToRemove: ['toImage', 'sendChartToCloud'],
  modeBarButtonsToAdd: [] as string[]
  // Through `unknown`: the type definitions predate Plotly 4's button names.
} as unknown as Partial<Plotly.Config>

const WITHOUT_TOOLS = { ...BASE, displayModeBar: false }

export function PlotlyFigure({
  data,
  layout,
  className,
  revision,
  onSelected,
  onSelecting,
  tools = false
}: PlotlyFigureProps) {
  const host = useRef<HTMLDivElement>(null)

  // Through a ref so the handler can change without re-attaching: Plotly
  // listeners are added per element, and `removeAllListeners` would take the
  // resize wiring with them.
  const selected = useRef(onSelected)
  selected.current = onSelected
  const selecting = useRef(onSelecting)
  selecting.current = onSelecting

  // A draw waiting for the element to have a size, and whether it has been
  // drawn into at all. Plotly cannot lay a figure out in a box with no width
  // or no height: it draws what it can and leaves itself a redraw for when
  // the margins can be worked out -- and if the figure is purged first, that
  // redraw runs against a figure that no longer exists and throws. A panel
  // the library sizes can be zero wide for a commit before it widens, which
  // is exactly when a figure mounting inside it gets its first data. So the
  // first draw waits for a box, and the resize observer below is what
  // notices one arriving.
  const pending = useRef<(() => void) | null>(null)
  const drawn = useRef(false)

  useEffect(() => {
    const element = host.current as (HTMLDivElement & Plotly.PlotlyHTMLElement) | null
    if (!element) {
      return
    }
    const draw = () => {
      void Plotly.react(
        element,
        data,
        { uirevision: revision ?? 'no_change', ...layout },
        tools ? WITH_TOOLS : WITHOUT_TOOLS
      ).then(() => {
        // Selection is listened for once the figure exists: `on` is
        // something Plotly puts on the element when it first draws, so a
        // figure whose first draw waited for a box would otherwise never
        // hear a lasso.
        if (!drawn.current) {
          drawn.current = true
          element.on?.('plotly_selected', (event) => {
            const points = (event as Plotly.PlotSelectionEvent | undefined)?.points ?? []
            const rows: number[] = []
            for (const point of points) {
              const row = (point as { customdata?: unknown }).customdata
              if (typeof row === 'number') {
                rows.push(row)
              }
            }
            selected.current?.(rows)
          })
          element.on?.('plotly_selecting', () => selecting.current?.())
          // A click that clears the selection, or a drag abandoned: no
          // `plotly_selected` with points follows, and the caller still has
          // to hear that the selecting is over.
          element.on?.('plotly_deselect', () => selected.current?.([]))
        }
      })
    }
    if (element.offsetWidth > 0 && element.offsetHeight > 0) {
      pending.current = null
      draw()
    } else {
      pending.current = draw
    }
  }, [data, layout, revision, tools])

  useEffect(() => {
    const element = host.current as (HTMLDivElement & Plotly.PlotlyHTMLElement) | null
    return () => {
      // `removeAllListeners` with a name, not the bare form: the bare one
      // would also drop whatever else is attached to this element.
      element?.removeAllListeners?.('plotly_selected')
      element?.removeAllListeners?.('plotly_selecting')
      element?.removeAllListeners?.('plotly_deselect')
    }
  }, [])

  // Plotly's own `responsive` listens to the window, not to the element, so a
  // figure laid out at one width keeps that width when its container changes
  // for any other reason -- a second dock slot appearing beside it, the
  // inspector collapsing, the rail being dragged. The figure is not wrong
  // when that happens, it is simply drawn for a box it no longer has, and the
  // part that does not fit is clipped. This watches the box instead.
  useEffect(() => {
    const element = host.current
    if (!element) {
      return
    }
    const observer = new ResizeObserver(() => {
      if (element.offsetWidth === 0 || element.offsetHeight === 0) {
        return
      }
      // The first box this element has had: draw what was waiting for one.
      // Resizing a figure that was never drawn is not a thing Plotly does.
      const waiting = pending.current
      if (waiting) {
        pending.current = null
        waiting()
      } else if (drawn.current) {
        Plotly.Plots.resize(element)
      }
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // Purge on unmount, not just React's own cleanup: Plotly hangs listeners and
  // a resize observer off the element, and dropping the div alone leaks both.
  useEffect(() => {
    const element = host.current
    return () => {
      if (element) {
        Plotly.purge(element)
      }
    }
  }, [])

  return <div ref={host} className={className} />
}
