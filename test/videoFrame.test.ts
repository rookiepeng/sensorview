// Mapping a data frame onto a frame of its recording.
//
// Transliterated from tests/test_video_frame_mapping.py. That file existed
// because the formula lived twice -- Python for the export, a JavaScript
// string inside a Dash callback for the panel -- with nothing keeping the pair
// in step. There is one language now, so the two-language hazard is gone.
//
// The tests came across anyway. The half-up rounding rule is still what
// decides whether an exported still is the picture the panel was showing or
// its neighbour, and it is still exactly what a tidy-up to some other rounding
// call would quietly change.

import { describe, expect, it } from 'vitest'

import { seekSeconds, videoFrameFor } from '../src/shared/videoFrame'

describe('videoFrameFor', () => {
  describe('rounding', () => {
    // Both cases land exactly on .5. Python's round() breaks halves toward
    // even and would give the second number; the mapping must give the first.
    it.each([
      // ratio 0.5 * (2 - 1) = 0.5 -> half-up 1, round-half-even 0
      [1, 3, 2, 1, 0],
      // ratio 0.5 * (6 - 1) = 2.5 -> half-up 3, round-half-even 2
      [1, 3, 6, 3, 2]
    ])(
      'breaks a half upward: (%i of %i, %i video frames) -> %i',
      (local, total, frames, expected, halfEvenWouldGive) => {
        expect(videoFrameFor(local, total, frames)).toBe(expected)
        // Guards the premise: if these stop differing, the assertion above has
        // quietly stopped testing anything.
        expect(expected).not.toBe(halfEvenWouldGive)
      }
    )
  })

  describe('endpoints', () => {
    it('maps the first data frame to the first video frame', () => {
      expect(videoFrameFor(0, 10, 30)).toBe(0)
    })

    it('maps the last data frame to the last video frame', () => {
      expect(videoFrameFor(9, 10, 30)).toBe(29)
    })

    it('maps a single-frame log to the first video frame', () => {
      // A total of 1 would make the span zero; the guard substitutes 1 so this
      // divides rather than producing NaN.
      expect(videoFrameFor(0, 1, 30)).toBe(0)
    })

    it('handles a single-frame video', () => {
      expect(videoFrameFor(5, 10, 1)).toBe(0)
    })
  })

  describe('bounds', () => {
    it('clamps a position past the end', () => {
      // A stale slider position against a freshly loaded, shorter log. It
      // should show the last frame, not read past the clip.
      expect(videoFrameFor(50, 10, 30)).toBe(29)
    })

    it('clamps a negative position', () => {
      expect(videoFrameFor(-5, 10, 30)).toBe(0)
    })

    it('is monotonic across a log', () => {
      // Scrubbing forward must never step the video backward.
      let previous = -1
      for (let i = 0; i < 40; i++) {
        const frame = videoFrameFor(i, 40, 97)
        expect(frame).toBeGreaterThanOrEqual(previous)
        previous = frame
      }
    })

    it('never exceeds the clip', () => {
      for (let i = 0; i < 40; i++) {
        expect(videoFrameFor(i, 40, 97)).toBeLessThanOrEqual(96)
      }
    })
  })
})

describe('seekSeconds', () => {
  it('lands in the middle of the frame, not on its boundary', () => {
    // Half a frame of slack: seeking exactly to a boundary is ambiguous
    // between a frame and its predecessor once container timestamps carry any
    // rounding.
    expect(seekSeconds(0, 10, 100)).toBeCloseTo(0.05, 10)
    expect(seekSeconds(99, 10, 100)).toBeCloseTo(9.95, 10)
  })

  it('applies the manifest offset', () => {
    expect(seekSeconds(0, 10, 100, 2)).toBeCloseTo(2.05, 10)
  })

  it('never seeks before the start', () => {
    expect(seekSeconds(0, 10, 100, -5)).toBe(0)
  })

  it('degrades to the offset when the clip is unmeasured', () => {
    // Duration is probed, and a probe can fail. Seeking to the offset is a
    // better answer than NaN, which a media element ignores silently.
    expect(seekSeconds(3, Number.NaN, 100)).toBe(0)
    expect(seekSeconds(3, 10, 0)).toBe(0)
  })
})
