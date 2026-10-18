// The top bar: who we are, what is open, and the theme.
//
// The breadcrumb is the case picker, as it was in the Dash top bar -- the path
// is the only thing worth showing there, so clicking it is the obvious way to
// change it rather than hiding that behind a separate button.

import { useEffect, useState } from 'react'

import { useStore } from '../store'
import { FIXTURE_FRAMES } from '../fixture'

export function TopBar() {
  const dir = useStore((s) => s.dir)
  const openCase = useStore((s) => s.openCase)
  const [theme, setTheme] = useState('dark')

  useEffect(() => {
    void window.sensorview.settings.get().then((stored) => {
      if (stored.ok && stored.data) {
        setTheme(stored.data.theme)
        document.documentElement.setAttribute('data-bs-theme', stored.data.theme)
      }
    })
  }, [])

  async function choose() {
    const result = await window.sensorview.openCase()
    if (result.ok && result.data) {
      // Until the readers land there is no frame count to ask for, so the
      // fixture's stands in. This is the one line that changes when P1 lands.
      openCase(result.data, FIXTURE_FRAMES)
    }
  }

  function flipTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-bs-theme', next)
    void window.sensorview.settings.set({ theme: next })
  }

  const name = dir ? dir.split(/[\\/]/).filter(Boolean).pop() : null

  return (
    <header className="sv-topbar">
      <div className="sv-brand">
        <span className="sv-brand-name">SensorView</span>
      </div>

      <button type="button" className="sv-breadcrumb" onClick={choose} title={dir ?? undefined}>
        <span className="sv-crumb">{name ?? 'No case'}</span>
        <span className="sv-crumb-sep">/</span>
        <span className={`sv-crumb sv-crumb-file${name ? '' : ' sv-crumb-empty'}`}>
          {name ? 'fixture' : 'open a case …'}
        </span>
      </button>

      <div className="sv-topbar-spacer" />

      <div className="sv-topbar-actions">
        <button
          type="button"
          className="sv-icon-btn"
          onClick={flipTheme}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          aria-label="Toggle theme"
        >
          <i className={theme === 'dark' ? 'bi bi-moon-fill' : 'bi bi-sun-fill'} />
        </button>
      </div>
    </header>
  )
}
