// The behaviour a floating menu is expected to have.
//
// Both menus in the app declared `role="menu"` and implemented about a third
// of what that promises. The export menu closed on an outside click and
// nothing else; the log picker closed on neither, and the ref it would have
// needed to was declared, attached, and never read by anything. Neither
// closed on Escape, neither moved focus into itself, and neither gave focus
// back -- running an export unmounted the focused button and dropped focus to
// the body.
//
// One hook so there is one answer, and so the next menu starts with it.

import { useCallback, useEffect, useRef, useState } from 'react'

export interface Menu {
  open: boolean
  /** Open, close, or flip. Closing always returns focus to the trigger. */
  toggle: () => void
  close: () => void
  /** Goes on the element wrapping both the trigger and the popup. */
  containerRef: React.RefObject<HTMLDivElement | null>
  /** Goes on the popup itself, for the arrow keys to find its items. */
  menuRef: React.RefObject<HTMLDivElement | null>
  /** Spread onto the trigger. */
  triggerProps: {
    ref: React.RefObject<HTMLButtonElement | null>
    'aria-haspopup': 'menu'
    'aria-expanded': boolean
  }
}

/** Everything inside the popup that arrow keys should walk. */
const ITEMS = '[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]'

export function useMenu(): Menu {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)
  const trigger = useRef<HTMLButtonElement | null>(null)

  // Focus goes back to what opened the menu, not to the body. Without this,
  // dismissing a menu with Escape leaves the keyboard at the top of the
  // document -- which for this app means tabbing in from the brand again.
  const close = useCallback(() => {
    setOpen((was) => {
      if (was) {
        trigger.current?.focus()
      }
      return false
    })
  }, [])

  const toggle = useCallback(() => setOpen((on) => !on), [])

  useEffect(() => {
    if (!open) {
      return
    }

    // Capture phase, and `mousedown` rather than `click`: a click that lands
    // on a control outside the menu should close the menu *and* reach the
    // control, which is what the export menu already did.
    const onDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
        return
      }
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') {
        return
      }
      const items = [...(menuRef.current?.querySelectorAll<HTMLElement>(ITEMS) ?? [])]
      if (items.length === 0) {
        return
      }
      event.preventDefault()
      const at = items.indexOf(document.activeElement as HTMLElement)
      const step = event.key === 'ArrowDown' ? 1 : -1
      // Wrapping, and an unfocused menu enters at whichever end the key
      // points to -- Down lands on the first item, Up on the last.
      const next = at === -1 ? (step === 1 ? 0 : items.length - 1) : (at + step + items.length) % items.length
      items[next]?.focus()
    }

    document.addEventListener('mousedown', onDown, true)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown, true)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, close])

  return {
    open,
    toggle,
    close,
    containerRef,
    menuRef,
    triggerProps: { ref: trigger, 'aria-haspopup': 'menu', 'aria-expanded': open }
  }
}
