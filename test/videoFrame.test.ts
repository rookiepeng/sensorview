// Mapping a data frame onto a frame of its recording.
//
// The half-up rounding rule decides whether an exported still is the picture
// the panel was showing or its neighbour, and is exactly what a tidy-up to
// some other rounding call would quietly change.

import { describe, expect, it } from 'vitest'

import { seekSeconds, videoFrameFor } from '../src/shared/videoFrame'

describe('videoFrameFor', () => {
  it.each([
    // Both land exactly on .5, where round-half-even would give one less.
    ['breaks 0.5 upward', 1, 3, 2, 1],
    ['breaks 2.5 upward', 1, 3, 6, 3],
    ['maps the first frame to the first', 0, 10, 30, 0],
    ['maps the last frame to the last', 9, 10, 30, 29],
    ['handles a single-frame log', 0, 1, 30, 0],
    ['handles a single-frame video', 5, 10, 1, 0],
    ['clamps a position past the end', 50, 10, 30, 29],
    ['clamps a negative position', -5, 10, 30, 0]
  ])('%s', (_, local, total, frames, expected) => {
    expect(videoFrameFor(local, total, frames)).toBe(expected)
  })

  it('never steps backward while scrubbing forward', () => {
    const mapped = Array.from({ length: 40 }, (_, i) => videoFrameFor(i, 40, 97))
    expect(mapped).toEqual([...mapped].sort((a, b) => a - b))
  })
})

describe('seekSeconds', () => {
  it('lands mid-frame, after the offset', () => {
    // A boundary is ambiguous once container timestamps carry any rounding.
    expect(seekSeconds(0, 10, 100)).toBeCloseTo(0.05, 10)
    expect(seekSeconds(99, 10, 100)).toBeCloseTo(9.95, 10)
    expect(seekSeconds(0, 10, 100, 2)).toBeCloseTo(2.05, 10)
  })

  it('never seeks before the start, or to NaN for an unmeasured clip', () => {
    expect(seekSeconds(0, 10, 100, -5)).toBe(0)
    expect(seekSeconds(3, Number.NaN, 100)).toBe(0)
    expect(seekSeconds(3, 10, 0)).toBe(0)
  })
})
