// Which column means what.
//
// The axes, the color, the frame slider and the reference sidecar's pose
// fields. All of it is the dataset author's choice rather than this app's, so
// all of it is written back to `info.json` -- which is the one thing
// SensorView writes, and the reason §8 R1 of the plan is about manifest
// formatting at all.
//
// The manifest mutates only the paths given and writes the parsed object back
// as-is, so a save here does not reformat the rest of someone's file.

import { useEffect, useState } from 'react'
import { Popover } from 'radix-ui'

import { Picker } from './Controls'
import { useStore } from '../store'
import { Icon } from './Icon'

/** Pose fields, grouped as they are read: position, orientation, frame. */
const POSE_ROWS = [['x', 'y', 'z'], ['yaw', 'pitch', 'roll'], ['frame']] as const

const POSE_LABELS: Record<string, string> = {
  x: 'X',
  y: 'Y',
  z: 'Z',
  yaw: 'Yaw',
  pitch: 'Pitch',
  roll: 'Roll',
  frame: 'Frame key'
}

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
    setNote('Saved to info.json')
  }

  const pickAxis = (axis: 'x' | 'y' | 'z', column: string) => {
    setAxis(axis, column)
    // The scanned summary is what the next log opens with, so it follows the
    // file it was read from.
    const summary = useStore.getState().summary
    if (summary) {
      useStore.getState().setSummary({ ...summary, axes: { ...summary.axes, [axis]: column } })
    }
    void save({ table: { [`${axis}_3d`]: column } })
  }

  return (
    // `modal` stays false -- the default, said out loud because it matters
    // here. A modal popover puts `pointer-events: none` on the body and
    // `aria-hidden` on everything outside it, which would make the scene
    // inert behind a popover that is meant to be read against it.
    <Popover.Root open={open} onOpenChange={setOpen} modal={false}>
      <div className="sv-topbar-menu">
        <Popover.Trigger asChild>
          {/* No `aria-haspopup` or `aria-expanded` here: Radix sets both, and
              a second copy is a second answer that can disagree. */}
          <button type="button" className="sv-icon-btn" title="Columns" aria-label="Columns">
            <Icon name="columns" />
          </button>
        </Popover.Trigger>

        {/* Portalled, so the glass top bar is not its containing block and
            Radix can keep it inside the window. It is a grid of selects, so
            Radix's `role="dialog"` describes it better than `role="menu"`. */}
        <Popover.Portal>
        <Popover.Content
          className="sv-menu sv-config"
          data-sv-menu="config"
          side="bottom"
          align="end"
          sideOffset={5}
          collisionPadding={8}
        >
          <header className="sv-config-head">
            <span className="sv-config-title">Columns</span>
            <span className="sv-config-sub">Changes save to info.json</span>
          </header>

          {/* Axes only. Color lives in the rail beside the colormap: it is
              looked at while reading the scene, where this popover is for
              what the dataset's columns mean, set once and left. */}
          <section className="sv-config-section">
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
          </section>

          <section className="sv-config-section">
            <span className="sv-section-label">Frame slider</span>
            <Field
              label="Frame key"
              value={table.frameKey}
              choices={every}
              hint="Changing this re-indexes the log and reloads the table."
              onChange={(column) => {
                void save({ table: { slider: column } }).then(() => reopen(column))
              }}
            />
          </section>

          {reference && reference.available.length > 0 && (
            <section className="sv-config-section">
              <span className="sv-section-label">Reference pose</span>
              <p className="sv-rail-note">
                From {stem}&rsquo;s own sidecar. Pick (none) for a field it
                does not carry.
              </p>
              {/* Position, then orientation, then the frame key: three rows
                  that each read as one thing, rather than seven fields
                  wrapped two to a row. */}
              {POSE_ROWS.map((row) => (
                <div key={row.join()} className="sv-config-grid">
                  {row.map((field) => (
                    <Field
                      key={field}
                      label={POSE_LABELS[field]}
                      value={reference.resolved[field] ?? ''}
                      wide={row.length === 1}
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
              ))}
            </section>
          )}

          {note && (
            <p className="sv-config-note" role="status">
              {note}
            </p>
          )}
        </Popover.Content>
        </Popover.Portal>
      </div>
    </Popover.Root>
  )
}

function Field({
  label,
  value,
  choices,
  onChange,
  hint,
  wide = false
}: {
  label: string
  value: string
  choices: string[]
  onChange: (value: string) => void
  hint?: string
  /** Spans the whole grid row, for a field with no siblings. */
  wide?: boolean
}) {
  return (
    <Picker
      className={`sv-pane-field sv-config-field${wide ? ' sv-config-wide' : ''}`}
      label={label}
      value={value}
      hint={hint}
      choices={choices.map((choice) => ({ value: choice, label: choice || '(none)' }))}
      onChange={onChange}
    />
  )
}
