// The left rail: display options, and the per-column filters.
//
// The filters are generated from the manifest's column metadata, which is why
// this is React and not markup -- a range slider per numeric key and a
// multi-select per categorical one, neither known until a case is open. Until
// the readers land there are no columns to generate from, so the rail carries
// the display options that already have something to act on.

import { useStore } from '../store'

const COLORMAPS = [
  'Blackbody', 'Bluered', 'Blues', 'Earth', 'Electric', 'Greens', 'Greys',
  'Hot', 'Jet', 'Picnic', 'Portland', 'Rainbow', 'RdBu', 'Reds', 'Viridis',
  'YlGnBu', 'YlOrRd'
]

export function FilterRail() {
  const decay = useStore((s) => s.decay)
  const setDecay = useStore((s) => s.setDecay)
  const colormap = useStore((s) => s.colormap)
  const setColormap = useStore((s) => s.setColormap)
  const sizeVary = useStore((s) => s.sizeVary)
  const setSizeVary = useStore((s) => s.setSizeVary)
  const hidden = useStore((s) => s.hidden)
  const dir = useStore((s) => s.dir)

  return (
    <aside id="filter-sidebar-col" className="sv-rail">
      <div className="sv-panel-head">
        <span className="sv-panel-title">
          <i className="bi bi-funnel" /> Filters
        </span>
      </div>

      <div className="sv-rail-body">
        <span className="sv-section-label">Display</span>

        <label className="sv-switch-row">
          <input
            type="checkbox"
            checked={sizeVary}
            onChange={(event) => setSizeVary(event.target.checked)}
          />
          <span>Size varies with category</span>
        </label>

        <div className="sv-field">
          <span className="sv-section-label">Colormap</span>
          <select value={colormap} onChange={(event) => setColormap(event.target.value)}>
            {COLORMAPS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        <div className="sv-field">
          <span className="sv-section-label">Decay</span>
          <input
            type="range"
            min={0}
            max={10}
            step={1}
            value={decay}
            aria-label="Decay"
            onChange={(event) => setDecay(Number(event.target.value))}
          />
          <span className="sv-field-value">{decay}</span>
        </div>

        <div className="sv-divider" />

        <span className="sv-section-label">Data filters</span>
        <p className="sv-rail-note">
          {dir
            ? 'Per-column filters arrive with the readers.'
            : 'Open a case to filter its columns.'}
        </p>

        {hidden.size > 0 && (
          <p className="sv-rail-note">
            {hidden.size} point{hidden.size === 1 ? '' : 's'} hidden by clicking.
          </p>
        )}
      </div>
    </aside>
  )
}
