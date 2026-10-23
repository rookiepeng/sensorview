import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Shown beside the name in the top bar. Read here rather than imported in
// the renderer, which would bundle the whole of package.json.
const { version } = JSON.parse(readFileSync(resolve('package.json'), 'utf8')) as {
  version: string
}

// The renderer in a plain browser tab, against a fixture.
//
// The UI is most of the remaining work, and HMR in a browser beats restarting
// Electron on every edit. It costs almost nothing to keep working because the
// renderer never imports from electron: it only ever calls
// `window.sensorview`, which the preload installs inside Electron and
// `src/renderer/lib/webBridge.ts` installs here. One interface, two
// implementations, and no conditionals in app code.
//
//   npm run web
export default defineConfig({
  root: 'src/renderer',
  plugins: [react()],
    // Plotly still reaches for Node's `global`, which no browser has and
    // Vite does not shim. Without this the renderer throws at import and the
    // page comes up blank -- no error visible anywhere but the console.
    define: { global: 'globalThis', __APP_VERSION__: JSON.stringify(version) },

  resolve: {
    alias: {
      '@shared': resolve('src/shared'),
      '@gl': resolve('src/renderer/gl')
    }
  },
  server: {
    port: Number(process.env.PORT ?? 5180),
    // The fixtures are read from the repo root, outside the Vite root.
    fs: { allow: [resolve('.')] }
  }
})
