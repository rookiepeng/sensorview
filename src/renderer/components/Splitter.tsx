// The handle between two regions.
//
// It has looked draggable since the Dash app: a 5px band with a centred grip,
// `cursor: col-resize`, an accent on hover. It was not draggable. The CSS
// said the drag lived in `workbench.js`, a file that did not survive the port
// -- so the rail, the inspector and the dock were fixed at their token widths
// and two handles sat there changing the cursor and doing nothing.
//
// What it writes is the CSS custom property the region already sizes itself
// from, not an inline width. `app.css` keeps owning the geometry; this only
// chooses a number for it.

import { useRef } from 'react'

export type Axis = 'col' | 'row'

export function Splitter({
  id,
  axis,
  label,
  measure,
  onResize,
  onReset,
  min,
  max,
  value,
  /** True when dragging *away* from the pointer grows the region: the
   *  inspector grows leftward and the dock grows upward. */
  invert = false
}: {
  id: string
  axis: Axis
  label: string
  /** The region's current size in pixels, read from the live element. Lets a
   *  never-dragged panel start from whatever the stylesheet gave it. */
  measure: () => number
  onResize: (px: number) => void
  onReset: () => void
  min: number
  /** A function, because the ceiling on the dock is a fraction of a viewport
   *  that changes when the window does. */
  max: () => number
  value: number | null
  invert?: boolean
}) {
  const drag = useRef<{ origin: number; start: number } | null>(null)

  const clamp = (px: number) => Math.round(Math.min(Math.max(px, min), Math.max(max(), min)))

  function begin(event: React.PointerEvent<HTMLDivElement>) {
    // Left button only, and no text selection from the press itself.
    if (event.button !== 0) {
      return
    }
    event.preventDefault()
    const handle = event.currentTarget
    handle.setPointerCapture(event.pointerId)
    drag.current = {
      origin: axis === 'col' ? event.clientX : event.clientY,
      start: measure()
    }
    // `.sv-resizing` has been in the stylesheet all along, suppressing text
    // selection and pinning the drag cursor while the pointer outruns the
    // handle. Nothing ever applied it.
    document.body.classList.add('sv-resizing', axis === 'col' ? 'sv-resizing-col' : 'sv-resizing-row')
  }

  function move(event: React.PointerEvent<HTMLDivElement>) {
    const from = drag.current
    if (!from) {
      return
    }
    const now = axis === 'col' ? event.clientX : event.clientY
    const delta = (now - from.origin) * (invert ? -1 : 1)
    onResize(clamp(from.start + delta))
  }

  function end(event: React.PointerEvent<HTMLDivElement>) {
    if (!drag.current) {
      return
    }
    drag.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
    document.body.classList.remove('sv-resizing', 'sv-resizing-col', 'sv-resizing-row')
  }

  /**
   * Take the key, and keep it.
   *
   * `stopPropagation` is the load-bearing half: arrows reach `useHotkeys` on
   * the window, where they step the frame. A focused splitter owns them, so
   * without this an arrow both resized the panel and scrubbed the transport.
   */
  function claim(event: React.KeyboardEvent<HTMLDivElement>) {
    event.preventDefault()
    event.stopPropagation()
  }

  function key(event: React.KeyboardEvent<HTMLDivElement>) {
    const [less, more] = axis === 'col' ? ['ArrowLeft', 'ArrowRight'] : ['ArrowUp', 'ArrowDown']
    let step: number
    if (event.key === less) {
      step = invert ? 10 : -10
    } else if (event.key === more) {
      step = invert ? -10 : 10
    } else if (event.key === 'Home') {
      // Back to the stylesheet's own size, which is also what a double-click
      // does. There is no other way to find it again once it has been moved.
      claim(event)
      onReset()
      return
    } else {
      return
    }
    claim(event)
    onResize(clamp(measure() + step))
  }

  return (
    <div
      id={id}
      className={`sv-splitter sv-splitter-${axis}`}
      role="separator"
      tabIndex={0}
      // The separator between two columns is itself a vertical line.
      aria-orientation={axis === 'col' ? 'vertical' : 'horizontal'}
      aria-label={label}
      aria-valuenow={value ?? undefined}
      aria-valuemin={min}
      aria-valuemax={Math.max(max(), min)}
      onPointerDown={begin}
      onPointerMove={move}
      onPointerUp={end}
      onPointerCancel={end}
      onDoubleClick={onReset}
      onKeyDown={key}
    />
  )
}
