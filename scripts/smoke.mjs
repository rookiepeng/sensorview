// Run the end-to-end spine check inside Electron.
//
//   node scripts/smoke.mjs [media-file] [--url http://127.0.0.1:8050]
//
// Spawns the built main process with SENSORVIEW_SMOKE set, which makes it run
// the checks in src/main/smoke.ts and exit with the failure count instead of
// opening a window. Given --url it also loads that page in a hidden window,
// which is how the Dash-hosting arrangement is checked.
//
// A thin wrapper rather than an npm script because setting an environment
// variable in one is not portable.

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { createRequire } from 'node:module'

const DEFAULT_MEDIA = 'data/NuScenes/scene_0061.mp4'

const args = process.argv.slice(2)
const urlAt = args.indexOf('--url')
const url = urlAt === -1 ? undefined : args[urlAt + 1]
const positional = args.filter((_, i) => i !== urlAt && i !== urlAt + 1)

const media = resolve(positional[0] ?? DEFAULT_MEDIA)
if (!existsSync(media)) {
  console.error(`smoke: no media file at ${media}`)
  console.error('Pass one as an argument, or put a case under data/.')
  process.exit(2)
}

if (!existsSync(resolve('out/main/index.js'))) {
  console.error('smoke: out/main/index.js is missing — run `npm run build` first.')
  process.exit(2)
}

const electron = createRequire(import.meta.url)('electron')

console.log(`smoke: ${media}`)
const child = spawn(electron, ['.'], {
  stdio: 'inherit',
  env: {
    ...process.env,
    SENSORVIEW_SMOKE: media,
    ...(url ? { SENSORVIEW_SMOKE_URL: url } : {})
  }
})
child.on('exit', (code) => process.exit(code ?? 1))
