// One slider with two thumbs, and a box for each end.
//
// The rail used to stack two native `<input type="range">`, one per end, and
// the comment on them explained why: overlay a pair and the moment the thumbs
// meet only the one painted on top can be grabbed, so the control dies
// exactly when the range is narrowest and matters most.
//
// The control that replaced them solved it by handing the press to the track
// rather than to a thumb, and by breaking the tie in favour of whichever
// thumb still had somewhere to go. Radix answers the same question a
// different way: it hands the press to the nearest thumb, writes the new
// value at that index and then *sorts*, so a tie going to the lower thumb
// is harmless -- drag right from a pair sitting on one value and the sort
// swaps them, leaving the one that moved as the thumb under the pointer.
// Thumbs that cross simply exchange places, so there is no state in which
// one of them is stuck.
//
// The boxes stay. A slider cannot be typed into, and reading a filter off a
// 288px rail is fine while setting one to -12.5 by dragging is not. They are
// deliberately not on the step grid -- see `typed`.

import { useState } from 'react'
import { Slider } from 'radix-ui'

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
  // Null means "show the committed value". Set only while a box is being
  // typed into, so an external change -- Reset, or a new case -- is picked up
  // without overwriting whatever is half-typed.
  const [draft, setDraft] = useState<{ end: 'min' | 'max'; text: string } | null>(null)

  const [min, max] = value
  // A column whose rows all hold one value has no range to pick within.
  const dead = !(high > low)

  function commit(which: 'min' | 'max', raw: string) {
    setDraft(null)
    const parsed = Number(raw)
    // An empty or unparseable box reverts rather than filtering to nothing.
    if (raw.trim() === '' || !Number.isFinite(parsed)) {
      return
    }
    const at = typed(parsed, low, high, decimals)
    if (which === 'min') {
      onChange(Math.min(at, max), max)
    } else {
      onChange(min, Math.max(at, min))
    }
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

  return (
    <div className={`sv-range${dead ? ' sv-range-dead' : ''}`}>
      {/* A dead column gets no slider at all: Radix divides by `max - min`
          to place its thumbs, and that span is zero here. */}
      {dead ? (
        <div className="sv-range-track" aria-hidden="true">
          <div className="sv-range-rail" />
        </div>
      ) : (
        <Slider.Root
          className="sv-range-track"
          value={[min, max]}
          min={low}
          max={high}
          step={step}
          // The filter is allowed to close to a single value, so the thumbs
          // may meet. They come apart again because Radix sorts after every
          // move -- which is the whole reason this is a library now.
          minStepsBetweenThumbs={0}
          onValueChange={([nextMin, nextMax]) => onChange(nextMin!, nextMax!)}
        >
          <Slider.Track className="sv-range-rail">
            <Slider.Range className="sv-range-fill" />
          </Slider.Track>
          {/* `aria-valuetext` because `aria-valuenow`, which Radix sets, is
              the raw number: a column whose extent is 203.7790069580078 is
              read out to the last digit without this. The manifest's own
              precision is what the boxes show, so it is what the thumbs
              should say too. */}
          <Slider.Thumb
            className="sv-range-thumb"
            aria-label={`${label} minimum`}
            aria-valuetext={text(min, decimals)}
          />
          <Slider.Thumb
            className="sv-range-thumb"
            aria-label={`${label} maximum`}
            aria-valuetext={text(max, decimals)}
          />
        </Slider.Root>
      )}

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
