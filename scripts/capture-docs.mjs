// Regenerate the README's screenshots and GIFs from the bundled NuScenes case.
//
//   node scripts/capture-docs.mjs [--case <dir>] [--skip-build]
//
// Drives the built app through a storyboard (see SENSORVIEW_SMOKE_LOOK_REEL in
// src/main/smoke.ts), collects a PNG per frame, then assembles them with the
// ffmpeg the app already ships. Output goes to assets/.
//
// The app saves theme and dock choices to the user's settings, so the
// storyboard puts both back at the end.

import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const args = process.argv.slice(2)
const caseDir = resolve(args.includes('--case') ? args[args.indexOf('--case') + 1] : 'data/NuScenes')
const assets = resolve('assets')
const ffmpeg = createRequire(import.meta.url)('ffmpeg-static')

if (!args.includes('--skip-build')) {
  const built = spawnSync('npm run build', { stdio: 'inherit', shell: true })
  if (built.status !== 0) process.exit(built.status ?? 1)
}

const work = mkdtempSync(join(tmpdir(), 'sensorview-docs-'))
const frameOf = (clip, i) => join(work, `${clip}-${String(i).padStart(3, '0')}.png`)
const shotOf = (name) => join(work, `${name}.png`)

const SLIDER = `document.querySelector('.sv-transport input[type=range]')`
const flipTheme = `Array.from(document.querySelectorAll('.sv-topbar-actions .sv-icon-btn')).find(b => /Switch to/.test(b.title)).click()`
const pressed = (selector) => `press(document.querySelector(${JSON.stringify(selector)}))`
const preset = (name) =>
  `Array.from(document.querySelectorAll('.sv-gl-preset')).find(b => b.title.toLowerCase().includes(${JSON.stringify(name)})).click()`
const dockView = (i) => `
  const picker = document.querySelector('.sv-slot-picker .sv-select')
  window.__views = window.__views || (await optionsOf(picker)).filter(Boolean)
  await setSelectValue(picker, window.__views[${i} % window.__views.length])`
// Negative ticks zoom in.
const zoom = (ticks) => `
  const canvas = document.getElementById('gl-canvas')
  const box = canvas.getBoundingClientRect()
  for (let i = 0; i < ${Math.abs(ticks)}; i++) {
    canvas.dispatchEvent(new WheelEvent('wheel', {
      deltaY: ${Math.sign(ticks) * 100}, bubbles: true, cancelable: true,
      clientX: box.left + box.width / 2, clientY: box.top + box.height / 2
    }))
  }`
const LIDAR = `switchRow(document.querySelector('.sv-rail'), 'LIDAR')`

const story = []
const add = (js, wait = 300, out) => story.push({ js, wait, out })

// What to put back afterwards.
add(`
  window.__orig = {
    dark: Array.from(document.querySelectorAll('.sv-topbar-actions .sv-icon-btn'))
      .some(b => /Switch to light/.test(b.title)),
    slots: Array.from(document.querySelectorAll('.sv-slot-picker .sv-select')).map(s => s.dataset.value),
    cloud: isOn(${LIDAR})
  }
  if (!window.__orig.cloud) flip(${LIDAR})
  await new Promise(r => setTimeout(r, 2500))
  ${preset('iso')}`, 1200)
// The ego sits a little left of the orbit target, so zooming would drift it
// off-centre; a right-button drag pans it onto the target first.
const drag = (from, to, steps = 8) => [
  { type: 'mouseDown', x: from[0], y: from[1], button: 'right', clickCount: 1 },
  ...Array.from({ length: steps }, (_, i) => ({
    type: 'mouseMove',
    x: Math.round(from[0] + ((to[0] - from[0]) * (i + 1)) / steps),
    y: Math.round(from[1] + ((to[1] - from[1]) * (i + 1)) / steps),
    modifiers: ['rightButtonDown']
  })),
  { type: 'mouseUp', x: to[0], y: to[1], button: 'right', clickCount: 1 }
]
story.push({ input: drag([800, 300], [824, 307]), wait: 500 })
add(`
  ${zoom(-28)}
  setRangeValue(${SLIDER}, Math.round(Number(${SLIDER}.max) * 0.3))`, 1500)

// Hero: scrub through the log.
const HERO = 24
for (let i = 0; i < HERO; i++) {
  add(`setRangeValue(${SLIDER}, Math.round(${i} / ${HERO - 1} * Number(${SLIDER}.max)))`, 450, frameOf('scrub', i))
}
add(`setRangeValue(${SLIDER}, Math.round(Number(${SLIDER}.max) * 0.3))`, 600)

// Camera presets.
for (const [i, name] of ['iso', 'top', 'front', 'side', 'iso'].entries()) {
  add(preset(name), 1000, frameOf('views', i))
}

// Filters: drop a category, narrow a range, put both back.
add(`window.__chips = []`, 100, frameOf('filter', 0))
add(`
  const chip = document.querySelector('.sv-filter .sv-chip-on')
  if (chip) { window.__chips.push(chip); press(chip) }`, 900, frameOf('filter', 1))
add(`
  const range = document.querySelector('.sv-range')
  const box = range.querySelectorAll('.sv-range-box')[1]
  const low = parseFloat(range.querySelectorAll('.sv-range-box')[0].value)
  window.__max = box.value
  const to = low + (parseFloat(box.value) - low) * 0.4
  setNativeValue(window.HTMLInputElement.prototype, box, to.toFixed(2))
  box.dispatchEvent(new Event('input', { bubbles: true }))
  box.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))`, 900, frameOf('filter', 2))
add(`
  const range = document.querySelector('.sv-range')
  const box = range.querySelectorAll('.sv-range-box')[1]
  setNativeValue(window.HTMLInputElement.prototype, box, window.__max)
  box.dispatchEvent(new Event('input', { bubbles: true }))
  box.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
  window.__chips.forEach(c => press(c))`, 900, frameOf('filter', 3))

// Dock: pull its splitter up so the charts get the room, then every chart in the first slot.
const dragSplitter = (dy) => `
  const sep = document.querySelector('.sv-center .sv-splitter-row').getBoundingClientRect()
  const x = Math.round(sep.left + sep.width / 2)
  const y0 = Math.round(sep.top + sep.height / 2)
  const y1 = y0 + (${dy})
  return [
    { type: 'mouseDown', x, y: y0, button: 'left', clickCount: 1 },
    ...Array.from({ length: 10 }, (_, i) => ({
      type: 'mouseMove', x, y: Math.round(y0 + ((y1 - y0) * (i + 1)) / 10), modifiers: ['leftButtonDown']
    })),
    { type: 'mouseUp', x, y: y1, button: 'left', clickCount: 1 }
  ]`
const DOCK = `document.querySelector('.sv-dock').getBoundingClientRect().height`
story.push({ js: `window.__dock0 = ${DOCK}`, inputJs: dragSplitter(-260), wait: 1200 })
for (let i = 0; i < 6; i++) {
  add(dockView(i), 1500, frameOf('dock', i))
}
add(dockView(0), 800)
story.push({ inputJs: dragSplitter(`${DOCK} - window.__dock0`), wait: 1000 })

// Panels: hide the rail, the inspector and the dock in turn, then bring them back.
const hideAll = (root) => `Array.from(document.querySelectorAll('${root} .sv-group-hide')).forEach(b => press(b))`
const dockToggle = (word) => `press(Array.from(document.querySelectorAll('.sv-dock-head .sv-icon-btn'))
  .find(b => b.getAttribute('aria-label') === '${word} the dock'))`
add(`setRangeValue(${SLIDER}, Math.round(Number(${SLIDER}.max) * 0.3))`, 1000, frameOf('panels', 0))
add(hideAll('.sv-rail'), 900, frameOf('panels', 1))
add(hideAll('.sv-inspector'), 900, frameOf('panels', 2))
add(dockToggle('Collapse'), 1200, frameOf('panels', 3))
add('', 1000, frameOf('panels', 4))
add(`
  Array.from(document.querySelectorAll('.sv-tray button')).forEach(b => press(b))
  ${dockToggle('Expand')}`, 1200, frameOf('panels', 5))

// Screenshots.
add(`setRangeValue(${SLIDER}, Math.round(Number(${SLIDER}.max) * 0.3))`, 1200, shotOf('workbench-dark'))
add(flipTheme, 1800, shotOf('workbench-light'))
add(flipTheme, 1200)
add(pressed('.sv-export .sv-icon-btn'), 600, shotOf('export'))
add(`escape()`, 400)
add(`
  const buttons = Array.from(document.querySelectorAll('.sv-crumb-btn'))
  press(buttons[buttons.length - 1])`, 600, shotOf('logs'))
add(`escape()`, 400)
add(pressed('.sv-topbar-menu .sv-icon-btn'), 600, shotOf('columns'))
add(`escape()`, 400)

// Put the user's settings back.
add(`
  const dark = Array.from(document.querySelectorAll('.sv-topbar-actions .sv-icon-btn'))
    .some(b => /Switch to light/.test(b.title))
  if (dark !== window.__orig.dark) { ${flipTheme} }
  const pickers = Array.from(document.querySelectorAll('.sv-slot-picker .sv-select'))
  for (const [i, value] of window.__orig.slots.entries()) await setSelectValue(pickers[i], value)
  if (isOn(${LIDAR}) !== window.__orig.cloud) flip(${LIDAR})`, 800)

const reel = join(work, 'reel.json')
writeFileSync(reel, JSON.stringify(story))

const shot = spawnSync(process.execPath, ['scripts/smoke.mjs', '--case', caseDir, '--look', shotOf('first')], {
  stdio: 'inherit',
  env: { ...process.env, SENSORVIEW_SMOKE_LOOK_REEL: reel }
})
if (shot.status !== 0) {
  console.error(`capture failed; frames kept in ${work}`)
  process.exit(shot.status ?? 1)
}

mkdirSync(assets, { recursive: true })
const run = (argv) => {
  const done = spawnSync(ffmpeg, ['-y', '-loglevel', 'error', ...argv], { stdio: 'inherit' })
  if (done.status !== 0) process.exit(done.status ?? 1)
}
const gif = (clip, fps, name = clip) => {
  const filter =
    'scale=900:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4'
  const out = join(assets, `${name}.gif`)
  run(['-framerate', String(fps), '-i', join(work, `${clip}-%03d.png`), '-vf', filter, '-loop', '0', out])
  console.log(`${out}  ${(statSync(out).size / 1e6).toFixed(1)} MB`)
}

gif('scrub', 8, 'screenshot')
gif('views', 1, 'views')
gif('filter', 1, 'filters')
gif('dock', 1, 'dock')
gif('panels', 1, 'panels')
for (const name of ['workbench-dark', 'workbench-light', 'export', 'logs', 'columns']) {
  const out = join(assets, `${name}.png`)
  run(['-i', shotOf(name), '-vf', 'scale=1400:-1:flags=lanczos', out])
  console.log(`${out}  ${(statSync(out).size / 1e6).toFixed(1)} MB`)
}

rmSync(work, { recursive: true, force: true })
