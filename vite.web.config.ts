import { resolve } from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

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
