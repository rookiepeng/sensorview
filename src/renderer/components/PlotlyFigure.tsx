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
}

const CONFIG = {
  displayModeBar: false,
  responsive: true,
  // Nothing here is a document to be downloaded; the export does that
  // deliberately and with the right size.
  staticPlot: false
}

export function PlotlyFigure({ data, layout, className, revision }: PlotlyFigureProps) {
  const host = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = host.current
    if (!element) {
      return
    }
    void Plotly.react(
      element,
      data,
      { uirevision: revision ?? 'no_change', ...layout },
      CONFIG
    )
  }, [data, layout, revision])

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
      if (element.offsetWidth > 0 && element.offsetHeight > 0) {
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
