// The 3D view's starting axes for a freshly opened log.

import type { Table } from './table'

/**
 * Choose the starting axes.
 *
 * The manifest's `table.x_3d` and friends come first. A log whose manifest
 * says nothing, or names a column this log does not have, should still open
 * -- so each axis falls back to a column called `X`/`Y`/`Z`, then to the first
 * numeric columns that are not the frame key, which for a radar table is
 * almost always the position.
 */
export function pickAxes(
  table: Pick<Table, 'columns'>,
  frameKey: string,
  declared: { x: string | null; y: string | null; z: string | null } = {
    x: null,
    y: null,
    z: null
  }
): { x: string; y: string; z: string; colour: string } {
  const numeric = [...table.columns.values()]
    .filter((column) => column.kind === 'number' && column.name !== frameKey)
    .map((column) => column.name)
  const categorical = [...table.columns.values()]
    .filter((column) => column.kind === 'string')
    .map((column) => column.name)

  const pick = (named: string | null, want: string, fallback: string | undefined) => {
    if (named && numeric.includes(named)) {
      return named
    }
    return numeric.includes(want) ? want : (fallback ?? numeric[0] ?? frameKey)
  }

  return {
    x: pick(declared.x, 'X', numeric[0]),
    y: pick(declared.y, 'Y', numeric[1]),
    z: pick(declared.z, 'Z', numeric[2]),
    // Colour by a category when there is one: it is more legible than a
    // gradient on first open, and it shows the legend doing something.
    colour: categorical[0] ?? numeric[0] ?? frameKey
  }
}
