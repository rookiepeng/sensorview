// Only what the React side uses. The GL modules call each other directly and
// need no declarations between themselves; this exists because `App.tsx` turns
// the manifest's cloud colour into the triple the scene wants, and the one
// parser for that already lives here.

/**
 * Parse a CSS colour into `[r, g, b]`, each 0-255.
 *
 * Accepts the forms a manifest or a Plotly palette can hold: `#rgb`,
 * `#rrggbb`, and `rgb(r, g, b)`.
 */
export function parseColor(value: string): number[]
