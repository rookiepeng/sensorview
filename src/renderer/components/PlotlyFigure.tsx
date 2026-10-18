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
// moves.

import { useEffect, useRef } from 'react'

import Plotly from '../lib/plotly'

export interface PlotlyFigureProps {
  data: Partial<Plotly.Data>[]
  layout: Partial<Plotly.Layout>
  className?: string
}

const CONFIG = {
  displayModeBar: false,
  responsive: true,
  // Nothing here is a document to be downloaded; the export does that
  // deliberately and with the right size.
  staticPlot: false
}

export function PlotlyFigure({ data, layout, className }: PlotlyFigureProps) {
  const host = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = host.current
    if (!element) {
      return
    }
    void Plotly.react(element, data, { uirevision: 'no_change', ...layout }, CONFIG)
  }, [data, layout])

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
