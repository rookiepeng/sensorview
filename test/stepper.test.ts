import { describe, expect, it } from 'vitest'

import { stepped } from '../src/renderer/components/Controls'

describe('number stepper', () => {
  it('steps by one at 1 and above', () => {
    expect(stepped(5, 1)).toBe(6)
    expect(stepped(12, -1)).toBe(11)
  })

  it('steps by a decade below 1, without float noise', () => {
    expect(stepped(0.5, 1)).toBe(0.6)
    expect(stepped(0.05, -1)).toBe(0.04)
    expect(stepped(0.9, 1)).toBe(1)
  })

  it('drops a decade when stepping toward zero from a power of ten', () => {
    expect(stepped(1, -1)).toBe(0.9)
    expect(stepped(0.1, -1)).toBe(0.09)
    expect(stepped(-1, 1)).toBe(-0.9)
  })

  it('crosses zero by whole units', () => {
    expect(stepped(0, -1)).toBe(-1)
    expect(stepped(-3, -1)).toBe(-4)
  })
})
