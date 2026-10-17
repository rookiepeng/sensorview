// Renderer entry.
//
// A placeholder until the views land. It is not nothing, though: it exercises
// the preload bridge, the data process and the settings store, so a packaged
// build that opens this window has proved the whole spine works.

import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'

import './styles/shell.css'

function App() {
  const [pid, setPid] = useState<string>('…')
  const [theme, setTheme] = useState<string>('dark')
  const [caseDir, setCaseDir] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      const ping = await window.sensorview.data('ping', undefined)
      setPid(ping.ok ? String(ping.data?.pid) : `unavailable (${ping.error})`)

      const stored = await window.sensorview.settings.get()
      if (stored.ok && stored.data) {
        setTheme(stored.data.theme)
        document.documentElement.setAttribute('data-bs-theme', stored.data.theme)
      }
    })()
  }, [])

  async function open() {
    const result = await window.sensorview.openCase()
    if (result.ok && result.data) {
      setCaseDir(result.data)
    }
  }

  async function flipTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-bs-theme', next)
    await window.sensorview.settings.set({ theme: next })
  }

  return (
    <main className="shell">
      <h1>SensorView</h1>
      <p className="note">
        The Electron shell is up. The views are still Dash — run with{' '}
        <code>SENSORVIEW_DASH=1</code> to point this window at them.
      </p>
      <dl>
        <dt>Data process</dt>
        <dd>pid {pid}</dd>
        <dt>Platform</dt>
        <dd>{window.sensorview.platform}</dd>
        <dt>Case</dt>
        <dd>{caseDir ?? 'none open'}</dd>
      </dl>
      <div className="row">
        <button type="button" onClick={open}>
          Open case…
        </button>
        <button type="button" onClick={flipTheme}>
          Theme: {theme}
        </button>
      </div>
    </main>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
