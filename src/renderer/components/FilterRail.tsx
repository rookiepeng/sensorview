// The left rail: display options, and the per-column filters.
//
// The filters are generated from the manifest's column metadata, which is why
// this is React and not markup -- a range slider per numeric key and a
// multi-select per categorical one, neither known until a case is open.
//
// Every edit lands in the store and the frame rebuilds from it. There is no
// debounce and no pending state: filtering 19,756 rows is a single pass over
// typed arrays, so a slider drag rebuilds the frame per pointer event and
// still has the budget to spare. Under Dash each of those events was a network
// round trip, which is what the whole caching apparatus was there to hide.

import { PanelHead, Picker, Switch } from './Controls'
import { useLayout } from '../layout'
import { useStore } from '../store'
import { levelsOf, rangeOf, type ColumnMeta } from '@shared/table'

const COLORMAPS = [
  'Blackbody', 'Bluered', 'Blues', 'Earth', 'Electric', 'Greens', 'Greys',
  'Hot', 'Jet', 'Picnic', 'Portland', 'Rainbow', 'RdBu', 'Reds', 'Viridis',
  'YlGnBu', 'YlOrRd'
]

/** Whether the picker's current states are exactly this choice. */
function sameStates(current: readonly string[] | undefined, want: readonly string[]): boolean {
  const have = current ?? ['visible']
  return have.length === want.length && want.every((state) => have.includes(state))
}

function labelOf(name: string, meta: ColumnMeta | undefined): string {
  if (!meta) {
    return name
  }
  const described = meta.description || name
  return meta.unit ? `${described} (${meta.unit})` : described
}

/**
 * A step fine enough to reach either end of a range in a hundred-odd moves.
 *
 * The Python computed this with `round(x, 3)`, which is banker's rounding and
 * would need `roundHalfEven` to reproduce. It does not need reproducing: the
 * step only decides how coarse a drag feels, and the value it produces is used
 * as a number, never written back to the manifest.
 */
function stepFor(min: number, max: number): number {
  const span = max - min
  if (!Number.isFinite(span) || span <= 0) {
    return 1
  }
  const magnitude = Math.pow(10, Math.floor(Math.log10(span)) - 2)
  return magnitude
}

function show(value: number, decimals: number | undefined): string {
  if (!Number.isFinite(value)) {
    return '—'
  }
  return value.toFixed(decimals ?? 2)
}

export function FilterRail() {
  const collapsed = useLayout((s) => s.railCollapsed)
  const toggle = useLayout((s) => s.toggle)
  const decay = useStore((s) => s.decay)
  const setDecay = useStore((s) => s.setDecay)
  const overlay = useStore((s) => s.overlay)
  const setOverlay = useStore((s) => s.setOverlay)
  const colormap = useStore((s) => s.colormap)
  const setColormap = useStore((s) => s.setColormap)
  const sizeVary = useStore((s) => s.sizeVary)
  const setSizeVary = useStore((s) => s.setSizeVary)
  const hiddenCount = useStore((s) => s.hiddenCount)
  const showAllRows = useStore((s) => s.showAllRows)
  const setVisibility = useStore((s) => s.setVisibility)
  const dir = useStore((s) => s.dir)
  const cloudDisplay = useStore((s) => s.cloudDisplay)
  const cloudOn = useStore((s) => s.cloudOn)
  const setCloudOn = useStore((s) => s.setCloudOn)
  const cloudError = useStore((s) => s.cloudError)
  const referenceError = useStore((s) => s.referenceError)

  const table = useStore((s) => s.table)
  const keys = useStore((s) => s.keys)
  const filters = useStore((s) => s.filters)
  const setNumericFilter = useStore((s) => s.setNumericFilter)
  const setCategoryFilter = useStore((s) => s.setCategoryFilter)
  const resetFilters = useStore((s) => s.resetFilters)

  const touched =
    table != null &&
    (filters.numeric.some((entry) => {
      const [min, max] = rangeOf(table, entry.column)
      return entry.min !== min || entry.max !== max
    }) ||
      filters.categorical.some(
        (entry) => entry.allowed.length !== levelsOf(table, entry.column).length
      ))

  return (
    <aside id="filter-sidebar-col" className={`sv-rail${collapsed ? ' sv-collapsed' : ''}`}>
      {/* The inspector and the dock could both fold away; the rail could
          not, though every rule for a collapsed one was already here. */}
      <PanelHead
        icon="funnel"
        title="Filters"
        collapse={{
          collapsed,
          onToggle: () => toggle('railCollapsed'),
          subject: 'filter rail',
          edge: 'left'
        }}
      >
        {touched && !collapsed && (
          <button type="button" className="sv-text-btn" onClick={resetFilters}>
            Reset
          </button>
        )}
      </PanelHead>

      <div className="sv-rail-body">
        <span className="sv-section-label">Display</span>

        <Switch checked={sizeVary} onChange={setSizeVary}>
          Size varies with category
        </Switch>

        {/* Only when the case has one. A dead switch is worse than no switch:
            it says the cloud is off rather than absent. */}
        {cloudDisplay && (
          <Switch checked={cloudOn} onChange={setCloudOn}>
            {/* The manifest names the cloud, and that name is the whole
                label. A verb in front of it would be the same word twice
                for every case that calls its cloud "Lidar". */}
            {cloudDisplay.name || 'Point cloud'}
          </Switch>
        )}

        {cloudError && <p className="sv-rail-note sv-rail-note-bad">{cloudError}</p>}
        {referenceError && <p className="sv-rail-note sv-rail-note-bad">{referenceError}</p>}

        <Picker
          label="Colormap"
          value={colormap}
          choices={COLORMAPS}
          onChange={setColormap}
          className="sv-field"
        />

        {/* Decay trails a fixed number of frames behind the current one;
            overlay draws every frame at once. Two answers to one question,
            so the slider goes dead rather than competing while overlay is
            on. */}
        <label className={`sv-field${overlay ? ' sv-field-off' : ''}`}>
          <span className="sv-section-label">Decay</span>
          <input
            type="range"
            min={0}
            max={10}
            step={1}
            value={decay}
            disabled={overlay}
            onChange={(event) => setDecay(Number(event.target.value))}
          />
          <span className="sv-field-value">{overlay ? 'all frames' : decay}</span>
        </label>

        <label className="sv-switch-row">
          <input
            type="checkbox"
            checked={overlay}
            onChange={(event) => setOverlay(event.target.checked)}
          />
          <span>Overlay every frame</span>
        </label>

        <div className="sv-divider" />

        <span className="sv-section-label">Data filters</span>

        {/* Always here, whether or not anything is hidden yet. It is a filter
            like the ones below it -- the state it reads is set by clicking a
            point or selecting a region -- and a control that appears only
            once it has something to say is one nobody finds. */}
        {table && (
          <div className="sv-field">
            <span className="sv-section-label">Visibility</span>
            <div className="sv-chips">
              {(
                [
                  { label: 'Visible', states: ['visible'] },
                  { label: 'Hidden', states: ['hidden'] },
                  { label: 'Both', states: ['visible', 'hidden'] }
                ] as const
              ).map((choice) => {
                const on = sameStates(filters.visible, choice.states)
                return (
                  <button
                    type="button"
                    key={choice.label}
                    className={`sv-chip${on ? ' sv-chip-on' : ''}`}
                    aria-pressed={on}
                    title={
                      choice.label === 'Both'
                        ? 'Show hidden points as well'
                        : `Show only ${choice.label.toLowerCase()} points`
                    }
                    onClick={() => setVisibility([...choice.states])}
                  >
                    {choice.label}
                  </button>
                )
              })}
            </div>
            <span className="sv-field-value">
              {hiddenCount > 0
                ? `${hiddenCount} hidden by clicking or selecting`
                : 'Everything starts out visible'}
            </span>
            {hiddenCount > 0 && (
              <button type="button" className="sv-text-btn sv-rail-action" onClick={showAllRows}>
                Show all again
              </button>
            )}
          </div>
        )}

        {!table && (
          <p className="sv-rail-note">
            {dir ? 'This case has no table to filter.' : 'Open a case to filter its columns.'}
          </p>
        )}

        {table &&
          filters.numeric.map((entry) => {
            const [low, high] = rangeOf(table, entry.column)
            const meta = keys[entry.column]
            const step = stepFor(low, high)
            return (
              <div className="sv-filter" key={entry.column}>
                <span className="sv-section-label">{labelOf(entry.column, meta)}</span>
                <div className="sv-range">
                  {/* Two inputs rather than one two-thumb control: the platform
                      has no dual range, and a pair that clamps against each
                      other behaves the same without a drag implementation. */}
                  <input
                    type="range"
                    min={low}
                    max={high}
                    step={step}
                    value={entry.min}
                    aria-label={`${entry.column} minimum`}
                    onChange={(event) =>
                      setNumericFilter(
                        entry.column,
                        Math.min(Number(event.target.value), entry.max),
                        entry.max
                      )
                    }
                  />
                  <input
                    type="range"
                    min={low}
                    max={high}
                    step={step}
                    value={entry.max}
                    aria-label={`${entry.column} maximum`}
                    onChange={(event) =>
                      setNumericFilter(
                        entry.column,
                        entry.min,
                        Math.max(Number(event.target.value), entry.min)
                      )
                    }
                  />
                </div>
                <span className="sv-field-value">
                  {show(entry.min, meta?.decimal)} … {show(entry.max, meta?.decimal)}
                </span>
              </div>
            )
          })}

        {table &&
          filters.categorical.map((entry) => {
            const levels = levelsOf(table, entry.column)
            const allowed = new Set(entry.allowed)
            return (
              <div className="sv-filter" key={entry.column}>
                <span className="sv-section-label" id={`chips-${entry.column}`}>
                  {labelOf(entry.column, keys[entry.column])}
                </span>
                <div className="sv-chips" role="group" aria-labelledby={`chips-${entry.column}`}>
                  {levels.map((level) => (
                    <button
                      type="button"
                      key={level}
                      className={`sv-chip${allowed.has(level) ? ' sv-chip-on' : ''}`}
                      aria-pressed={allowed.has(level)}
                      onClick={() =>
                        setCategoryFilter(
                          entry.column,
                          allowed.has(level)
                            ? entry.allowed.filter((name) => name !== level)
                            : [...entry.allowed, level]
                        )
                      }
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>
            )
          })}

      </div>
    </aside>
  )
}
