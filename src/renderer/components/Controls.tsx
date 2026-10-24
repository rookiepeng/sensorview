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
import { Select as RadixSelect, Switch as RadixSwitch } from 'radix-ui'
import { Icon, type IconName } from './Icon'

export function IconButton({
  icon,
  title,
  label,
  onClick,
  disabled,
  className
}: {
  icon: IconName
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
      <Icon name={icon} />
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

/**
 * One overlay: a titled plate floating over the scene.
 *
 * It has two states and the caller owns them -- it is here, or it is not.
 * There was a fold in between, which turned out to be a third answer to a
 * question with two: a plate showing only its head takes the same column
 * from the scene as one showing its controls.
 *
 * The head's title is deliberately not a `.sv-section-label`. `smoke.ts` reads
 * every one of those in the rail and asserts "color by" is immediately
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
  icon: IconName
  title: string
  children: ReactNode
  /**
   * What the overlay is worth at a glance -- the column the scene is
   * colored by, how many filters are on.
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
          <Icon name={icon} className="sv-group-icon" />
          <span className="sv-group-label">{title}</span>
        </span>
        {reading ? <span className="sv-group-reading">{reading}</span> : null}
        {actions}
        {onHide && (
          <IconButton
            icon="close"
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

/**
 * An on/off setting, drawn as a toggle switch.
 *
 * The `<label>` wraps both the switch and its words, so clicking the words
 * flips it and the words name it. Radix's switch is a `button role=switch`,
 * which `smoke.ts` reads by `aria-checked`.
 */
export function Switch({
  checked,
  onChange,
  children,
  disabled
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  /** The label. Wrapped by the `<label>`, so it names the switch. */
  children: ReactNode
  disabled?: boolean
}) {
  return (
    <label className={`sv-switch-row${disabled ? ' sv-field-off' : ''}`}>
      <RadixSwitch.Root
        className="sv-switch"
        checked={checked}
        disabled={disabled}
        onCheckedChange={onChange}
      >
        <RadixSwitch.Thumb className="sv-switch-thumb" />
      </RadixSwitch.Root>
      <span>{children}</span>
    </label>
  )
}

export type Choice = string | { value: string; label: string; icon?: IconName }

/**
 * Radix reserves the empty string for "nothing chosen", and several pickers
 * use it for "all". This stands in for it inside the select only.
 */
const EMPTY = '__sv_empty__'
const encode = (value: string) => (value === '' ? EMPTY : value)
const decode = (value: string) => (value === EMPTY ? '' : value)

/**
 * A themed dropdown select with no label of its own.
 *
 * The list is portalled to the body and kept inside the window, rather than
 * being the OS popup a native `<select>` opens -- which used the system font
 * and highlight, and could hang outside the app window.
 *
 * The trigger and every item carry `data-value`, which is how `smoke.ts`
 * reads and drives them.
 */
export function SelectMenu({
  value,
  choices,
  onChange,
  disabled = false,
  label,
  title,
  className
}: {
  value: string
  choices: readonly Choice[]
  onChange: (value: string) => void
  disabled?: boolean
  /** The accessible name, when no `<label>` wraps this. */
  label?: string
  title?: string
  className?: string
}) {
  const items: { value: string; label: string; icon?: IconName }[] = choices.map((choice) =>
    typeof choice === 'string' ? { value: choice, label: choice } : choice
  )
  const current = items.find((item) => item.value === value)
  const shown = current?.label ?? value
  return (
    <RadixSelect.Root
      value={encode(value)}
      disabled={disabled}
      onValueChange={(next) => onChange(decode(next))}
    >
      <RadixSelect.Trigger
        className={className ? `sv-select ${className}` : 'sv-select'}
        aria-label={label}
        title={title ?? shown}
        data-value={value}
      >
        {current?.icon && <Icon name={current.icon} className="sv-select-icon" />}
        <span className="sv-select-value">
          <RadixSelect.Value>{shown}</RadixSelect.Value>
        </span>
        <RadixSelect.Icon asChild>
          <Icon name="chevron-down" className="sv-select-caret" />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content
          className="sv-menu sv-select-menu"
          position="popper"
          side="bottom"
          align="start"
          sideOffset={4}
          collisionPadding={8}
        >
          <RadixSelect.Viewport className="sv-select-viewport">
            {items.map((item) => (
              <RadixSelect.Item
                key={item.value}
                value={encode(item.value)}
                className="sv-menu-item sv-select-item"
                data-value={item.value}
              >
                {item.icon && <Icon name={item.icon} className="sv-select-icon" />}
                <RadixSelect.ItemText>{item.label}</RadixSelect.ItemText>
                <RadixSelect.ItemIndicator className="sv-menu-check">
                  <Icon name="check" />
                </RadixSelect.ItemIndicator>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  )
}

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
      {/* A picker in a dock pane is as narrow as the strip can make it, so a
          long column name is clipped. The tooltip is the whole value. */}
      <SelectMenu value={value} choices={choices} onChange={onChange} disabled={disabled} />
      {hint && <span className="sv-field-value">{hint}</span>}
    </label>
  )
}

/**
 * How far one arrow press moves a number.
 *
 * One unit at 1 and above, and a decade below that, so a bin width of 0.05
 * steps to 0.06 rather than to 1.05. Stepping toward zero from a power of
 * ten drops a decade first (1 → 0.9, 0.1 → 0.09), so a positive value never
 * lands on zero by stepping.
 */
export function stepFor(value: number, direction: 1 | -1): number {
  const size = Math.abs(value)
  if (size === 0) {
    return 1
  }
  let exponent = Math.floor(Math.log10(size))
  const towardZero = Math.sign(value) !== direction
  if (towardZero && Number((10 ** exponent).toPrecision(12)) === Number(size.toPrecision(12))) {
    exponent -= 1
  }
  return 10 ** Math.min(exponent, 0)
}

/** `value` moved one step, with the float noise rounded off. */
export function stepped(value: number, direction: 1 | -1): number {
  return Number((value + direction * stepFor(value, direction)).toPrecision(12))
}

/**
 * A number box with its own up/down arrows.
 *
 * The native spinners cannot be styled -- they draw in the platform's own
 * light chrome on a dark panel -- so they are hidden and replaced with two
 * buttons that look like the select's caret.
 *
 * Kept as a string, like the limits it is used for: empty means "auto".
 *
 * @param seed Where the arrows start from while the box is empty: what
 *     "auto" currently is, when the caller can tell.
 */
export function NumberStepper({
  value,
  onChange,
  placeholder,
  title,
  positive = false,
  seed
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  title?: string
  /** Never step to zero or below. */
  positive?: boolean
  seed?: () => number | undefined
}) {
  const nudge = (direction: 1 | -1) => {
    const typed = value.trim() === '' ? NaN : Number(value)
    const start = Number.isFinite(typed) ? typed : (seed?.() ?? (positive ? 1 : 0))
    if (!Number.isFinite(start)) {
      return
    }
    // A seed is shown as is on the first press, so the box takes over from
    // "auto" without the picture jumping a step.
    const next = Number.isFinite(typed) ? stepped(start, direction) : Number(start.toPrecision(6))
    if (positive && next <= 0) {
      return
    }
    onChange(String(next))
  }

  return (
    <span className="sv-stepper">
      <input
        type="number"
        step="any"
        min={positive ? 0 : undefined}
        value={value}
        placeholder={placeholder}
        title={title}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
            event.preventDefault()
            nudge(event.key === 'ArrowUp' ? 1 : -1)
          }
        }}
      />
      {/* Out of the tab order: the arrow keys in the box do the same. */}
      <span className="sv-stepper-arrows">
        <button type="button" tabIndex={-1} aria-label="Increase" onClick={() => nudge(1)}>
          <Icon name="chevron-up" />
        </button>
        <button type="button" tabIndex={-1} aria-label="Decrease" onClick={() => nudge(-1)}>
          <Icon name="chevron-down" />
        </button>
      </span>
    </span>
  )
}
