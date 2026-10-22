// Which column means what.
//
// The axes, the colour, the frame slider and the reference sidecar's pose
// fields. All of it is the dataset author's choice rather than this app's, so
// all of it is written back to `info.json` -- which is the one thing
// SensorView writes, and the reason §8 R1 of the plan is about manifest
// formatting at all.
//
// The manifest mutates only the paths given and writes the parsed object back
// as-is, so a save here does not reformat the rest of someone's file. A v1
// file is upgraded on the first save, with the original kept once as
// `info.json.bak`; that is said out loud rather than done quietly.

import { useEffect, useRef, useState } from 'react'

import { useStore } from '../store'

/** Pose fields, in the order the sidecar reader wants them. */
const POSE_FIELDS = ['x', 'y', 'z', 'yaw', 'pitch', 'roll', 'frame'] as const

export function ColumnConfig() {
  const table = useStore((s) => s.table)
  const dir = useStore((s) => s.dir)
  const stem = useStore((s) => s.stem)
  const axes = useStore((s) => s.axes)
  const setAxis = useStore((s) => s.setAxis)
  const reopen = useStore((s) => s.reopenWithFrameKey)

  const [open, setOpen] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [reference, setReference] = useState<{
    available: string[]
    resolved: Record<string, string | null>
  } | null>(null)
  const menu = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) {
      return
    }
    const close = (event: MouseEvent) => {
      if (!menu.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', close, true)
    return () => document.removeEventListener('mousedown', close, true)
  }, [open])

  // Read when the popover opens rather than on every log change: it is one
  // more file read, and nothing needs it until someone looks.
  useEffect(() => {
    if (!open || !dir || !stem) {
      return
    }
    let current = true
    void window.sensorview
      .data('logReferenceColumns', { dir, stem })
      .then((result) => {
        if (current && result.ok) {
          setReference(result.data ?? null)
        }
      })
    return () => {
      current = false
    }
  }, [open, dir, stem])

  if (!table || !dir) {
    return null
  }

  const numeric = [...table.columns.values()]
    .filter((column) => column.kind === 'number')
    .map((column) => column.name)
  const every = [...table.columns.keys()]

  async function save(
    patch: { table?: Record<string, string>; reference?: Record<string, string> }
  ) {
    const result = await window.sensorview.data('saveManifest', { dir: dir!, ...patch })
    if (!result.ok) {
      setNote(result.error ?? 'could not write info.json')
      return
    }
    // Said once, because it is a change to the user's own folder.
    setNote(result.data?.upgraded ? 'Saved — upgraded to v2, original kept as info.json.bak' : 'Saved to info.json')
  }

  const pickAxis = (axis: 'x' | 'y' | 'z', column: string) => {
    setAxis(axis, column)
    void save({ table: { [`${axis}_3d`]: column } })
  }

  return (
    <div className="sv-topbar-menu" ref={menu}>
      <button
        type="button"
        className="sv-icon-btn"
        onClick={() => setOpen((on) => !on)}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Columns"
        aria-label="Columns"
      >
        <i className="bi bi-sliders" />
      </button>

      {open && (
        <div className="sv-menu sv-menu-right sv-config" role="menu">
          {/* Axes only. Colour lives in the rail beside the colormap: it is
              looked at while reading the scene, where this popover is for
              what the dataset's columns mean, set once and left. */}
          <span className="sv-section-label">3D axes</span>
          <div className="sv-config-grid">
            {(['x', 'y', 'z'] as const).map((axis) => (
              <Field
                key={axis}
                label={axis.toUpperCase()}
                value={axes[axis]}
                choices={numeric}
                onChange={(column) => pickAxis(axis, column)}
              />
            ))}
          </div>

          <div className="sv-divider" />

          <span className="sv-section-label">Frame slider</span>
          <p className="sv-rail-note">
            Changing this re-indexes the log, so it reloads the table.
          </p>
          <Field
            label="Column"
            value={table.frameKey}
            choices={every}
            onChange={(column) => {
              void save({ table: { slider: column } }).then(() => reopen(column))
            }}
          />

          {reference && reference.available.length > 0 && (
            <>
              <div className="sv-divider" />
              <span className="sv-section-label">Reference pose</span>
              <p className="sv-rail-note">
                From {stem}&rsquo;s own sidecar. Leave one empty for a field it
                does not carry.
              </p>
              <div className="sv-config-grid">
                {POSE_FIELDS.map((field) => (
                  <Field
                    key={field}
                    label={field}
                    value={reference.resolved[field] ?? ''}
                    // The empty option is NO_COLUMN, which the normalizer
                    // treats as a decision rather than as "unset" -- so a
                    // field cleared here is not guessed straight back.
                    choices={['', ...reference.available]}
                    onChange={(column) => {
                      setReference({
                        ...reference,
                        resolved: { ...reference.resolved, [field]: column || null }
                      })
                      void save({ reference: { [field]: column } })
                    }}
                  />
                ))}
              </div>
            </>
          )}

          {note && (
            <p className="sv-rail-note sv-config-note" role="status">
              {note}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function Field({
  label,
  value,
  choices,
  onChange
}: {
  label: string
  value: string
  choices: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="sv-pane-field">
      <span className="sv-section-label">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {choices.map((choice) => (
          <option key={choice || '(none)'} value={choice}>
            {choice || '(none)'}
          </option>
        ))}
      </select>
    </label>
  )
}
