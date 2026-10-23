import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'electron-vite'

// Shown beside the name in the top bar. Read here rather than imported in
// the renderer, which would bundle the whole of package.json.
const { version } = JSON.parse(readFileSync(resolve('package.json'), 'utf8')) as {
  version: string
}

// electron-vite infers the three entries from src/main, src/preload and
// src/renderer by convention, so there is no build.lib boilerplate here.
export default defineConfig({
  main: {
    build: {
      externalizeDeps: true,
      rollupOptions: {
        // Two entries: the app, and the data layer it forks as a utility
        // process. They are built together because electron-builder ships one
        // `out/` tree, but they never share a module instance -- the native
        // Parquet addon and the HDF5 WASM load only in the second.
        input: {
          index: resolve('src/main/index.ts'),
          data: resolve('src/data/index.ts')
        }
      }
    }
  },
  preload: {
    build: {
      externalizeDeps: true,
      // A sandboxed preload has no ESM loader, so it must be CommonJS. The
      // main process references it by this exact name.
      rollupOptions: { output: { format: 'cjs', entryFileNames: '[name].cjs' } }
    }
  },
  renderer: {
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
    }
  }
})
