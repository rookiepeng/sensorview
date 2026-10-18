// Run the end-to-end spine check inside Electron.
//
//   node scripts/smoke.mjs [media-file] [--url <page>] [--case <dir>] [--packaged]
//
// --case adds the native-module spike: polars against the real table and
// h5wasm against the real cloud, through the forked data process.
//
// --packaged runs dist/win-unpacked instead of the dev build, which is the
// only configuration where an asar or a missing runtime can show up.
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
const flag = (name) => {
  const at = args.indexOf(name)
  return at === -1 ? undefined : args[at + 1]
}
const url = flag('--url')
const caseDir = flag('--case')
const packaged = args.includes('--packaged')

const consumed = new Set()
for (const name of ['--url', '--case']) {
  const at = args.indexOf(name)
  if (at !== -1) {
    consumed.add(at).add(at + 1)
  }
}
const positional = args.filter((a, i) => !consumed.has(i) && !a.startsWith('--'))

const media = resolve(positional[0] ?? DEFAULT_MEDIA)
if (!existsSync(media)) {
  console.error(`smoke: no media file at ${media}`)
  console.error('Pass one as an argument, or put a case under data/.')
  process.exit(2)
}

// The packaged app is the configuration that matters: a native addon has to
// load from outside the asar, and that path does not exist in a dev build.
const PACKAGED = resolve('dist/win-unpacked/SensorView.exe')
if (packaged && !existsSync(PACKAGED)) {
  console.error('smoke: no packaged build — run `npm run dist` first.')
  process.exit(2)
}
if (!packaged && !existsSync(resolve('out/main/index.js'))) {
  console.error('smoke: out/main/index.js is missing — run `npm run build` first.')
  process.exit(2)
}

const electron = packaged ? PACKAGED : createRequire(import.meta.url)('electron')

console.log(`smoke: ${media}${packaged ? ' (packaged)' : ''}`)
const child = spawn(electron, packaged ? [] : ['.'], {
  stdio: 'inherit',
  env: {
    ...process.env,
    SENSORVIEW_SMOKE: media,
    ...(url ? { SENSORVIEW_SMOKE_URL: url } : {}),
    ...(caseDir ? { SENSORVIEW_SMOKE_CASE: resolve(caseDir) } : {})
  }
})
child.on('exit', (code) => process.exit(code ?? 1))
