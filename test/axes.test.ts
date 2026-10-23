// Which columns the 3D view opens on.

import { describe, expect, it } from 'vitest'

import { pickAxes } from '../src/shared/axes'
import type { Column } from '../src/shared/table'

const tableOf = (numeric: string[], strings: string[] = []) => ({
  columns: new Map<string, Column>([
    ...numeric.map((name) => [name, { name, kind: 'number' }] as [string, Column]),
    ...strings.map((name) => [name, { name, kind: 'string' }] as [string, Column])
  ])
})

describe('pickAxes', () => {
  it('follows the manifest', () => {
    const table = tableOf(['Frame', 'SNR', 'Range', 'Longitude', 'Latitude', 'Height'])
    const axes = pickAxes(table, 'Frame', { x: 'Longitude', y: 'Latitude', z: 'Height' })
    expect([axes.x, axes.y, axes.z]).toEqual(['Longitude', 'Latitude', 'Height'])
  })

  it('prefers the manifest over columns called X, Y and Z', () => {
    const table = tableOf(['X', 'Y', 'Z', 'Lon', 'Lat', 'H'])
    const axes = pickAxes(table, 'Frame', { x: 'Lon', y: 'Lat', z: 'H' })
    expect([axes.x, axes.y, axes.z]).toEqual(['Lon', 'Lat', 'H'])
  })

  it('falls back per axis when the manifest names a missing column', () => {
    const table = tableOf(['X', 'Y', 'Z', 'Lon'])
    const axes = pickAxes(table, 'Frame', { x: 'Lon', y: 'None', z: null })
    expect([axes.x, axes.y, axes.z]).toEqual(['Lon', 'Y', 'Z'])
  })

  it('falls back to the first numeric columns without a manifest', () => {
    const table = tableOf(['Frame', 'A', 'B', 'C'], ['Source'])
    const axes = pickAxes(table, 'Frame')
    expect(axes).toEqual({ x: 'A', y: 'B', z: 'C', colour: 'Source' })
  })
})
