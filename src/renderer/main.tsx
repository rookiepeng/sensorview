// Renderer entry.
//
// Stylesheet order is load-bearing: `reset.css` supplies what Bootstrap's
// reboot used to, `app.css` carries the design tokens and the region geometry,
// and `hud.css` overrides the panels into glass over the scene. Under Dash
// this was arranged by filename, because assets were served alphabetically.

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Icons are Lucide SVGs, imported per glyph: see `components/Icon.tsx`.

import './styles/reset.css'
import './styles/app.css'
import './styles/hud.css'

import { App } from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import { installWebBridge } from './lib/webBridge'

// A no-op inside Electron, where the preload got there first. In a browser tab
// it installs the same interface backed by localStorage and a fixture, which
// is what lets the UI be developed with hot reload instead of an Electron
// restart per edit.
installWebBridge()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>
)
