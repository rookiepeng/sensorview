// The grid's spacing, which follows the camera.
//
// `Axes.retick` turns a distance into a step: one pixel is
// `2 * d * tan(fov / 2) / height` world units at the data's distance, the
// root's scale turns those into the data's own, and the result is snapped so
// the spacing steps between readable values instead of sliding. The snapping
// and the tick run are pure and tested here; the measuring is not, because it
// needs a camera.
//
// Driven by a bug this would have caught: the first attempt was verified by
// zooming in, where the step went 20 -> 10 -> 5, and the other direction was
// taken on trust.

import { describe, expect, it } from 'vitest'

// @ts-expect-error -- plain ESM, no types, as the rest of `gl/` is.
import { niceStep, ticksAtStep } from '../src/renderer/gl/sv_axes.esm.js'

/** What `retick` computes, with the measuring stripped out. */
function stepFor(distance: number, { fov = 50, height = 900, scale = 1, targetPx = 96 } = {}) {
  const worldPerPx = (2 * distance * Math.tan((fov / 2) * (Math.PI / 180))) / height
  return niceStep((targetPx * worldPerPx) / scale) as number
}

describe('niceStep', () => {
  it('snaps to one, two or five times a power of ten', () => {
    for (const raw of [0.011, 0.04, 0.4, 1.1, 2.9, 6, 13, 44, 180, 900, 4200]) {
      const step = niceStep(raw) as number
      const mantissa = step / Math.pow(10, Math.floor(Math.log10(step)))
      expect([1, 2, 5]).toContain(Math.round(mantissa))
    }
  })

  it('never returns a step a range cannot be divided by', () => {
    for (const raw of [0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(niceStep(raw)).toBe(1)
    }
  })

  it('coarsens as the camera pulls back and refines as it closes in', () => {
    const steps = [5, 10, 20, 40, 80, 160, 320].map((d) => stepFor(d))
    // Monotonic going out, which is the direction the browser check could
    // not drive -- a step that only ever refined would bury the floor in
    // lines as soon as the view was pulled back.
    for (let i = 1; i < steps.length; i++) {
      expect(steps[i]).toBeGreaterThanOrEqual(steps[i - 1]!)
    }
    expect(steps.at(-1)!).toBeGreaterThan(steps[0]!)
  })

  it('keeps the cells near the pixel size they are aimed at', () => {
    // Snapping can only put the step within a factor of two of the target.
    for (const distance of [8, 17, 35, 64, 129, 260]) {
      const step = stepFor(distance)
      const wanted = (96 * (2 * distance * Math.tan((50 / 2) * (Math.PI / 180)))) / 900
      expect(step / wanted).toBeGreaterThan(0.5)
      expect(step / wanted).toBeLessThan(2.1)
    }
  })
})

describe('ticksAtStep', () => {
  it('covers the range on multiples of the step', () => {
    const ticks = ticksAtStep(-60, 60, 20) as number[]
    expect(ticks).toEqual([-60, -40, -20, 0, 20, 40, 60])
  })

  it('starts on a multiple inside the range, not on its edge', () => {
    expect(ticksAtStep(-18, 141, 20)).toEqual([0, 20, 40, 60, 80, 100, 120, 140])
  })

  it('pins a tick that lands on zero to exactly zero', () => {
    const ticks = ticksAtStep(-0.3, 0.3, 0.1) as number[]
    expect(ticks.filter((v) => v === 0)).toHaveLength(1)
    expect(ticks.some((v) => Object.is(v, -0))).toBe(false)
  })

  it('gives a drawable answer for a step that cannot divide anything', () => {
    expect(ticksAtStep(0, 10, 0)).toEqual([0])
    expect(ticksAtStep(0, Number.NaN, 1)).toEqual([0])
  })
})
