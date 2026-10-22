// One slider with two thumbs, and a box for each end.
//
// The rail used to stack two native `<input type="range">`, one per end, and
// the comment on them explained why: overlay a pair and the moment the thumbs
// meet only the one painted on top can be grabbed, so the control dies
// exactly when the range is narrowest and matters most.
//
// That is a real bug in the naive version, and the reason to build the
// control rather than overlap two natives. The press is not handed to a thumb
// here; it is handed to the track, which decides which thumb to move -- the
// nearer one, and when they coincide, whichever still has somewhere to go.
// Two thumbs on one value stay separable because neither of them is what the
// pointer is hitting.
//
// The boxes exist because a slider cannot be typed into. Reading a filter off
// a 288px rail is fine; setting one to -12.5 by dragging is not.

import { useRef, useState } from 'react'

export interface RangeSliderProps {
  /** The column's own extent -- the ends the thumbs travel between. */
  low: number
  high: number
  step: number
  value: readonly [number, number]
  /** Decimal places for the boxes, from the manifest. */
  decimals: number
  /** Names the thumbs and the boxes: "Range (m) minimum". */
  label: string
  onChange: (min: number, max: number) => void
}

/** A PageUp or PageDown is worth ten of an arrow. */
const PAGE = 10

/**
 * Put a value on the step grid, anchored at `low`.
 *
 * Anchored rather than absolute so both ends stay reachable: a grid anchored
 * at zero leaves `low` itself off it whenever `low % step` is not zero, and
 * the thumb then cannot be dragged the last fraction back to it.
 */
function snap(value: number, low: number, high: number, step: number): number {
  const steps = Math.round((value - low) / step)
  // Multiplying a 1e-9 step back out reintroduces the float noise the round
  // just took away, so trim to the step's own precision.
  const places = Math.max(0, Math.min(20, -Math.floor(Math.log10(step))))
  const on = Number((low + steps * step).toFixed(places))
  return Math.min(Math.max(on, low), high)
}

/**
 * A typed value, honoured as typed.
 *
 * Deliberately *not* put on the step grid. The step is a drag affordance --
 * about a hundred of them across the column -- and snapping a typed number
 * to it would leave the boxes no more precise than the thumb they exist to
 * work around: on a 440m column the step is 1, so "-12.5" would land on -12.
 *
 * Rounded instead to the manifest's declared precision, so the box shows
 * exactly the number the filter is using rather than a rounded picture of a
 * different one, and clamped to the column's own extent.
 */
function typed(value: number, low: number, high: number, decimals: number): number {
  const at = Number(value.toFixed(Math.max(0, Math.min(20, decimals))))
  return Math.min(Math.max(at, low), high)
}

function text(value: number, decimals: number): string {
  if (!Number.isFinite(value)) {
    return ''
  }
  // A manifest is a file someone can edit, and `toFixed` throws past 100.
  return value.toFixed(Math.max(0, Math.min(20, decimals)))
}

export function RangeSlider({
  low,
  high,
  step,
  value,
  decimals,
  label,
  onChange
}: RangeSliderProps) {
  const track = useRef<HTMLDivElement>(null)
  const held = useRef<'min' | 'max' | null>(null)
  // Null means "show the committed value". Set only while a box is being
  // typed into, so an external change -- Reset, or a new case -- is picked up
  // without overwriting whatever is half-typed.
  const [draft, setDraft] = useState<{ end: 'min' | 'max'; text: string } | null>(null)

  const [min, max] = value
  // A column whose rows all hold one value has no range to pick within.
  const dead = !(high > low)
  const pct = (at: number) => (dead ? 0 : ((at - low) / (high - low)) * 100)

  /** Where along the column's extent a pointer is. */
  function valueAt(clientX: number): number {
    const box = track.current?.getBoundingClientRect()
    if (!box || box.width === 0) {
      return low
    }
    const across = Math.min(Math.max((clientX - box.left) / box.width, 0), 1)
    return snap(low + across * (high - low), low, high, step)
  }

  /**
   * Which thumb a press belongs to.
   *
   * The last clause is the point of this control: with both thumbs on one
   * value "nearest" is a tie, so the tie goes to the thumb that still has
   * room to travel. Pinned at the top that is the minimum; anywhere else,
   * the maximum.
   */
  function pick(at: number): 'min' | 'max' {
    if (at < min) {
      return 'min'
    }
    if (at > max) {
      return 'max'
    }
    const toMin = at - min
    const toMax = max - at
    if (toMin !== toMax) {
      return toMin < toMax ? 'min' : 'max'
    }
    return max >= high ? 'min' : 'max'
  }

  /** Move one end, never past the other. */
  function move(end: 'min' | 'max', to: number) {
    if (end === 'min') {
      onChange(Math.min(to, max), max)
    } else {
      onChange(min, Math.max(to, min))
    }
  }

  function begin(event: React.PointerEvent<HTMLDivElement>) {
    if (dead || event.button !== 0) {
      return
    }
    event.preventDefault()
    const at = valueAt(event.clientX)
    held.current = pick(at)
    event.currentTarget.setPointerCapture(event.pointerId)
    move(held.current, at)
  }

  function drag(event: React.PointerEvent<HTMLDivElement>) {
    if (held.current) {
      move(held.current, valueAt(event.clientX))
    }
  }

  function release(event: React.PointerEvent<HTMLDivElement>) {
    if (!held.current) {
      return
    }
    held.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  function keys(which: 'min' | 'max', event: React.KeyboardEvent<HTMLDivElement>) {
    const here = which === 'min' ? min : max
    let to: number
    switch (event.key) {
      case 'ArrowLeft':
      case 'ArrowDown':
        to = here - step
        break
      case 'ArrowRight':
      case 'ArrowUp':
        to = here + step
        break
      case 'PageDown':
        to = here - step * PAGE
        break
      case 'PageUp':
        to = here + step * PAGE
        break
      case 'Home':
        to = low
        break
      case 'End':
        to = high
        break
      default:
        return
    }
    event.preventDefault()
    // Arrows reach `useHotkeys` on the window, where they step the frame. A
    // focused thumb owns them, so without this one press would do both.
    event.stopPropagation()
    move(which, snap(to, low, high, step))
  }

  function commit(which: 'min' | 'max', raw: string) {
    setDraft(null)
    const parsed = Number(raw)
    // An empty or unparseable box reverts rather than filtering to nothing.
    if (raw.trim() === '' || !Number.isFinite(parsed)) {
      return
    }
    move(which, typed(parsed, low, high, decimals))
  }

  function box(which: 'min' | 'max') {
    const here = which === 'min' ? min : max
    const shown = draft?.end === which ? draft.text : text(here, decimals)
    return (
      <input
        type="number"
        className="sv-range-box"
        value={shown}
        // Not `step`: the grid belongs to the thumb, and against it the
        // browser would mark a perfectly good typed value invalid.
        step="any"
        min={which === 'min' ? low : min}
        max={which === 'min' ? max : high}
        disabled={dead}
        aria-label={`${label} ${which === 'min' ? 'minimum' : 'maximum'}`}
        onChange={(event) => setDraft({ end: which, text: event.target.value })}
        onBlur={(event) => commit(which, event.target.value)}
        onKeyDown={(event) => {
          // `useHotkeys` already stands aside for an input, but Enter and
          // Escape are this box's own and should go no further either.
          event.stopPropagation()
          if (event.key === 'Enter') {
            commit(which, event.currentTarget.value)
          } else if (event.key === 'Escape') {
            setDraft(null)
          }
        }}
      />
    )
  }

  function thumb(which: 'min' | 'max') {
    const here = which === 'min' ? min : max
    return (
      <div
        className="sv-range-thumb"
        style={{ left: `${pct(here)}%` }}
        role="slider"
        tabIndex={dead ? -1 : 0}
        aria-label={`${label} ${which === 'min' ? 'minimum' : 'maximum'}`}
        aria-valuenow={here}
        aria-valuemin={which === 'min' ? low : min}
        aria-valuemax={which === 'min' ? max : high}
        aria-valuetext={text(here, decimals)}
        aria-disabled={dead || undefined}
        onKeyDown={(event) => keys(which, event)}
      />
    )
  }

  return (
    <div className={`sv-range${dead ? ' sv-range-dead' : ''}`}>
      {/* The press lands here, not on a thumb. */}
      <div
        className="sv-range-track"
        ref={track}
        onPointerDown={begin}
        onPointerMove={drag}
        onPointerUp={release}
        onPointerCancel={release}
      >
        <div className="sv-range-rail" />
        <div
          className="sv-range-fill"
          style={{ left: `${pct(min)}%`, right: `${100 - pct(max)}%` }}
        />
        {thumb('min')}
        {thumb('max')}
      </div>

      <div className="sv-range-boxes">
        {box('min')}
        <span className="sv-range-dash" aria-hidden="true">
          to
        </span>
        {box('max')}
      </div>
    </div>
  )
}
