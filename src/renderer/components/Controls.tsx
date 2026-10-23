// The pieces of chrome every panel was rebuilding by hand.
//
// None of these is interesting on its own. They exist because the same four
// shapes were written out five, three, four and two times respectively, and
// each copy had drifted: an icon button that forgot `aria-hidden` on its
// glyph, a select whose label was a sibling `<span>` rather than a `<label>`
// and so named nothing, a collapse button whose tooltip and accessible name
// disagreed about what it did.
//
// Class names are load-bearing beyond CSS: `src/main/smoke.ts` drives the
// real DOM by `.sv-icon-btn`, `.sv-switch-row` and friends, and finds some of
// them by index. Keep the markup these emit as it was.

import type { ReactNode } from 'react'

/** A bootstrap-icons name without the `bi-` prefix, e.g. `chevron-down`. */
type Icon = string

export function IconButton({
  icon,
  title,
  label,
  onClick,
  disabled,
  className
}: {
  icon: Icon
  /** The tooltip. Also the accessible name unless `label` overrides it. */
  title: string
  label?: string
  onClick: () => void
  disabled?: boolean
  className?: string
}) {
  return (
    <button
      type="button"
      className={className ? `sv-icon-btn ${className}` : 'sv-icon-btn'}
      title={title}
      aria-label={label ?? title}
      disabled={disabled}
      onClick={onClick}
    >
      {/* The glyph is the button's whole visible content, and the button is
          already named. Announced, it would read the name twice. */}
      <i className={`bi bi-${icon}`} aria-hidden="true" />
    </button>
  )
}

/**
 * The toggle on a panel that can fold away.
 *
 * `edge` is the side the panel collapses toward, which is what decides the
 * chevron: a rail that folds left points left while it is open and right once
 * it has, so the arrow always points the way the next click will move it.
 */
export function CollapseButton({
  collapsed,
  onToggle,
  subject,
  edge
}: {
  collapsed: boolean
  onToggle: () => void
  /** Named in the accessible label: "Collapse the inspector". */
  subject: string
  edge: 'left' | 'right' | 'bottom'
}) {
  const [open, shut] =
    edge === 'bottom' ? (['down', 'up'] as const) : edge === 'right' ? (['right', 'left'] as const) : (['left', 'right'] as const)
  const words = `${collapsed ? 'Expand' : 'Collapse'} the ${subject}`
  return (
    <IconButton
      icon={`chevron-${collapsed ? shut : open}`}
      // One string for both. They used to disagree -- "Collapse" in the
      // tooltip, "Collapse the dock" to a screen reader -- which is two
      // answers to the same question.
      title={words}
      onClick={onToggle}
    />
  )
}

export function PanelHead({
  icon,
  title,
  children,
  collapse
}: {
  icon: Icon
  title: string
  /** Anything that sits between the title and the collapse toggle. */
  children?: ReactNode
  collapse?: { collapsed: boolean; onToggle: () => void; subject: string; edge: 'left' | 'right' }
}) {
  return (
    <div className="sv-panel-head">
      <span className="sv-panel-title">
        <i className={`bi bi-${icon}`} aria-hidden="true" />
        <span className="sv-panel-label">{title}</span>
      </span>
      {children}
      {collapse && (
        <CollapseButton
          collapsed={collapse.collapsed}
          onToggle={collapse.onToggle}
          subject={collapse.subject}
          edge={collapse.edge}
        />
      )}
    </div>
  )
}

/**
 * One overlay: a titled plate floating over the scene.
 *
 * It has two states and the caller owns them -- it is here, or it is not.
 * There was a fold in between, which turned out to be a third answer to a
 * question with two: a plate showing only its head takes the same column
 * from the scene as one showing its controls.
 *
 * The head's title is deliberately not a `.sv-section-label`. `smoke.ts` reads
 * every one of those in the rail and asserts "colour by" is immediately
 * followed by "colormap"; a heading joining that list is a thing that breaks
 * quietly.
 */
export function Group({
  icon,
  title,
  children,
  reading,
  actions,
  onHide,
  className
}: {
  /** Names the overlay here, and the button that brings it back. */
  icon: Icon
  title: string
  children: ReactNode
  /**
   * What the overlay is worth at a glance -- the column the scene is
   * coloured by, how many filters are on.
   */
  reading?: ReactNode
  /** Rendered at the end of the head -- a Reset, a picker. */
  actions?: ReactNode
  /** Takes the overlay away. It comes back from the tray in its corner. */
  onHide?: () => void
  className?: string
}) {
  return (
    <section className={className ? `sv-group ${className}` : 'sv-group'}>
      <div className="sv-group-head">
        <span className="sv-group-title">
          <i className={`bi bi-${icon} sv-group-icon`} aria-hidden="true" />
          <span className="sv-group-label">{title}</span>
        </span>
        {reading ? <span className="sv-group-reading">{reading}</span> : null}
        {actions}
        {onHide && (
          <IconButton
            icon="x-lg"
            title={`Hide ${title}`}
            onClick={onHide}
            className="sv-group-hide"
          />
        )}
      </div>
      <div className="sv-group-body">{children}</div>
    </section>
  )
}

export function Switch({
  checked,
  onChange,
  children
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  /** The label. Wrapped by the `<label>`, so it names the input. */
  children: ReactNode
}) {
  return (
    <label className="sv-switch-row">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{children}</span>
    </label>
  )
}

export type Choice = string | { value: string; label: string }

/**
 * A select with a label that names it.
 *
 * The `<label>` wrapper is the point. The rail wrote the same thing with a
 * sibling `<span>`, which looks identical and leaves the control anonymous.
 */
export function Picker({
  label,
  value,
  choices,
  onChange,
  className = 'sv-pane-field',
  disabled = false,
  hint
}: {
  label: string
  value: string
  choices: readonly Choice[]
  onChange: (value: string) => void
  className?: string
  /** Inert because something else supersedes it, not because it is broken. */
  disabled?: boolean
  /** One line saying why, shown under the control. */
  hint?: string
}) {
  return (
    <label className={`${className}${disabled ? ' sv-field-off' : ''}`}>
      <span className="sv-section-label">{label}</span>
      <select
        value={value}
        disabled={disabled}
        // A picker in a dock pane is as narrow as the strip can make it, so
        // a long column name is clipped. The tooltip is the whole value.
        title={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {choices.map((choice) => {
          const [key, text] = typeof choice === 'string' ? [choice, choice] : [choice.value, choice.label]
          return (
            <option key={key} value={key}>
              {text}
            </option>
          )
        })}
      </select>
      {hint && <span className="sv-field-value">{hint}</span>}
    </label>
  )
}
