// The curve panel: one plot per definition in the manifest, for one frame.
//
// A curve file holds many named series per frame -- a detection threshold, the
// signal it is applied to, a noise floor -- and which are drawn together is
// declared in `info.json` rather than inferred, so this draws what it is given
// and decides nothing about grouping.
//
// The y range is the part worth care. Letting Plotly autorange each frame
// makes the trace appear to stay still while the axis moves underneath it,
// which is the opposite of what a scrub is for: the shape of the change is
// the thing being looked at. So the range is fixed per (log, source, plot) and
// only widens.

import { useMemo } from 'react'

import type { CurvePlot } from '@shared/types'

import { PlotlyFigure } from './PlotlyFigure'

export interface CurvePanelProps {
  plots: CurvePlot[]
  /**
   * Fixed y ranges, keyed by `rangeKey` rather than by `id`.
   *
   * Combined logs each draw their own band of a plot, and the bands share
   * one range: a band scaled to its own log would put two signals side by
   * side at different scales, which is the comparison this view exists to
   * make possible.
   */
  yRanges: Record<string, [number, number]>
  theme: 'dark' | 'light'
}

export function CurvePanel({ plots, yRanges, theme }: CurvePanelProps) {
  return (
    <>
      {plots.map((plot) => (
        <Plot key={plot.id} plot={plot} range={yRanges[plot.rangeKey]} theme={theme} />
      ))}
    </>
  )
}

function Plot({
  plot,
  range,
  theme
}: {
  plot: CurvePlot
  range: [number, number] | undefined
  theme: 'dark' | 'light'
}) {
  const data = useMemo(
    () =>
      plot.traces.map((trace) => ({
        type: 'scatter' as const,
        mode: (trace.mode ?? 'lines') as 'lines' | 'markers' | 'lines+markers',
        name: trace.label,
        // Plotly reads a typed array directly; converting to a plain array
        // here would copy every sample for no gain.
        x: trace.x ?? trace.y.map((_, i) => i),
        y: trace.y,
        line: {
          color: trace.color,
          width: trace.width ?? 2,
          dash: (trace.dash ?? 'solid') as Plotly.Dash
        },
        marker: {
          color: trace.color,
          size: trace.size ?? 6,
          // Plotly's symbol union is closed; the manifest names any symbol it knows.
          symbol: (trace.symbol ?? 'circle') as 'circle'
        },
        // A gap is a gap. Joining across one would draw a line through a bin
        // that had no return, which reads as data.
        connectgaps: false
      })),
    [plot]
  )

  const layout = useMemo(() => {
    const ink = theme === 'dark' ? '#8a929e' : '#5e6773'
    const grid = theme === 'dark' ? '#242a33' : '#dfe3e8'
    return {
      autosize: true,
      // The panel is small, so the margins are the plot: Plotly's defaults
      // would leave less than half the box for the trace.
      // The top margin leaves one row for the legend above the plot.
      margin: { l: 52, r: 8, t: 22, b: 34 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: ink, size: 10 },
      // A legend row above the plot, so it never covers the traces.
      showlegend: true,
      legend: {
        orientation: 'h' as const,
        x: 0,
        xanchor: 'left' as const,
        y: 1,
        yanchor: 'bottom' as const,
        bgcolor: 'rgba(0,0,0,0)',
        font: { size: 9 }
      },
      xaxis: {
        title: { text: plot.xLabel, font: { size: 10 } },
        gridcolor: grid,
        zeroline: false
      },
      yaxis: {
        title: { text: plot.yLabel, font: { size: 10 } },
        gridcolor: grid,
        zeroline: false,
        ...(range ? { range, autorange: false as const } : {})
      }
    }
  }, [plot.xLabel, plot.yLabel, range, theme])

  return (
    <div className="sv-curve">
      <span className="sv-section-label">{plot.label}</span>
      <PlotlyFigure
        data={data}
        layout={layout}
        className="sv-curve-graph"
        revision={plot.id}
      />
    </div>
  )
}

/**
 * Widen a set of y ranges to cover what just arrived.
 *
 * Only ever widens, within one log and source. A range that re-fitted each
 * frame would make the axis move while the trace stood still, and a range
 * that never grew would clip a later frame's peak off the top.
 */
export function growYRanges(
  current: Record<string, [number, number]>,
  plots: CurvePlot[]
): Record<string, [number, number]> {
  let changed = false
  const next = { ...current }

  for (const plot of plots) {
    let min = Infinity
    let max = -Infinity
    for (const trace of plot.traces) {
      for (const value of trace.y) {
        // NaN is a real value here -- a bin with no return -- and must not
        // drag the range to nothing.
        if (!Number.isFinite(value)) {
          continue
        }
        if (value < min) min = value
        if (value > max) max = value
      }
    }
    if (min > max) {
      continue
    }

    // A little headroom, so a peak does not sit exactly on the frame.
    const pad = (max - min) * 0.05 || 0.5
    const found: [number, number] = [min - pad, max + pad]
    const have = next[plot.rangeKey]
    if (!have) {
      next[plot.rangeKey] = found
      changed = true
    } else if (found[0] < have[0] || found[1] > have[1]) {
      next[plot.rangeKey] = [Math.min(have[0], found[0]), Math.max(have[1], found[1])]
      changed = true
    }
  }

  // The same object when nothing moved, so a subscriber comparing by
  // reference does not redraw every plot on every frame.
  return changed ? next : current
}
