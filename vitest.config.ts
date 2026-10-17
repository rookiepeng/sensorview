import { resolve } from 'node:path'

import { defineConfig } from 'vitest/config'

// Node environment, no jsdom. Logic that is worth testing lives in src/shared
// and src/data, both of which run in Node; the React tree is verified by
// running the app.
export default defineConfig({
  resolve: { alias: { '@shared': resolve('src/shared') } },
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node'
  }
})
