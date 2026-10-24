// A dock view or a curve plot, as a file.
//
// The figure is rebuilt in the light theme by whoever owns it and handed
// here; this puts it on white paper and renders it. PNG and SVG go through
// `Plotly.toImage`, which draws into a detached element of its own, so the
// figure on screen is never touched and keeps the theme it was drawn in.

import Plotly from '../lib/plotly'
import { onPaper, standaloneHtml } from './exporters'

export type FigureFormat = 'png' | 'svg' | 'html'

/** A figure ready to be written, in the light theme. */
export interface ExportFigure {
  data: unknown[]
  layout: Record<string, unknown>
  /** Pixel size of the image. A PNG is drawn at twice this. */
  width: number
  height: number
  /** The HTML page's title: what the figure is, and of which log. */
  name: string
  /** Drawn at the top of the figure, when the figure has no title of its own. */
  title?: string
}

export const FORMATS: Record<
  FigureFormat,
  { label: string; hint: string; filter: { name: string; extensions: string[] } }
> = {
  png: { label: 'PNG', hint: 'image', filter: { name: 'PNG image', extensions: ['png'] } },
  svg: { label: 'SVG', hint: 'vector image', filter: { name: 'SVG image', extensions: ['svg'] } },
  html: {
    label: 'HTML',
    hint: 'interactive page',
    filter: { name: 'HTML page', extensions: ['html'] }
  }
}

/**
 * The file's contents, as the save dialog takes them.
 *
 * @returns Text for SVG and HTML, base64 for PNG.
 */
export async function figureFile(
  figure: ExportFigure,
  format: FigureFormat
): Promise<{ data: string; encoding: 'utf8' | 'base64' }> {
  const layout = onPaper(figure.layout, figure.title)

  if (format === 'html') {
    // The library is fetched rather than imported: it is 4.7 MB, and
    // bundling it into the app to serve an export taken once a session
    // would put it in memory for every session that never exports.
    const { default: url } = await import('plotly.js/dist/plotly.min.js?url')
    const source = await (await fetch(url)).text()
    return {
      data: standaloneHtml(
        { data: figure.data, layout },
        figure.name,
        source
      ),
      encoding: 'utf8'
    }
  }

  const url = await Plotly.toImage(
    // A figure object rather than an element: Plotly draws it off screen.
    { data: figure.data, layout, config: { staticPlot: true } } as never,
    {
      format,
      width: Math.round(figure.width),
      height: Math.round(figure.height),
      // Twice the size on screen, so a PNG is sharp on a slide. An SVG is
      // vector, and scaling it would only change the numbers in it.
      scale: format === 'png' ? 2 : 1
    } as never
  )
  const comma = url.indexOf(',')
  const head = url.slice(0, comma)
  const body = url.slice(comma + 1)
  if (format === 'png') {
    return { data: body, encoding: 'base64' }
  }
  // Plotly hands an SVG back URI-encoded; base64 is handled in case that
  // ever changes, since either decodes to the same file.
  return {
    data: head.endsWith(';base64') ? atob(body) : decodeURIComponent(body),
    encoding: 'utf8'
  }
}

/**
 * The size an exported figure is drawn at: the size it has on screen, so the
 * text keeps its proportion to the plot, but never smaller than a figure is
 * worth reading at.
 */
export function exportSize(element: Element | null | undefined): {
  width: number
  height: number
} {
  const box = element?.getBoundingClientRect()
  return {
    width: Math.max(box?.width ?? 0, 560),
    height: Math.max(box?.height ?? 0, 340)
  }
}
