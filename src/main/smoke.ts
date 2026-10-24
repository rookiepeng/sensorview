// An end-to-end check of the spine, run inside real Electron.
//
// Two things in P0 can only be proved by running: that `sv://` honours Range
// (the whole reason the scheme exists -- without it the camera panel cannot
// seek), and that the data utility process forks and answers. Both fail in
// ways a unit test cannot see: a privilege flag missing from the scheme
// registration, a preload path that is wrong only in a packaged build, a
// native module that loads in `dev` and not from inside the asar.
//
// Run with `npm run smoke`, or `SENSORVIEW_SMOKE=<file> electron .` against a
// packaged build. Exits non-zero on the first failure so CI can gate on it.

import { BrowserWindow, net } from 'electron'

import type { DataClient } from './dataClient'
import { allowRoot, isAllowed, mediaUrl } from './protocol'

interface Check {
  name: string
  run: () => Promise<string>
}

function expect(condition: unknown, message: string): void {
  if (!condition) {
    throw new Error(message)
  }
}

/**
 * The handful of ways these checks reach into the page.
 *
 * Each of these was written out three or four times, and the copies had
 * already drifted: of the three writes to a picker, two went through the
 * prototype's own setter and the third assigned `.value` -- which a
 * React-controlled select is free to ignore, because React compares against
 * the last value it wrote itself. One answer each, so the next check starts
 * with it, and so a control that stops being a native element is one edit
 * here rather than ten across this file.
 *
 * Injected as the first statements *inside* each script's IIFE rather than
 * declared once at the top of one: `executeJavaScript` evaluates in the page's
 * own realm, so a `const` at the script's top level would be redeclared -- and
 * throw -- on the second call into the same window.
 *
 * No backslash escapes in here, for the reason given at the posed-reference
 * check below: this is a TypeScript template literal first and JavaScript
 * second.
 */
const DRIVE = `
               // A Radix trigger opens on pointer-down, not on click, so that
               // a press-drag-release picks an item. 'click()' alone dispatches
               // only the click and the menu never opens. The trailing click
               // is what every plain button still needs, so this one call is
               // right for both.
               // Resolves after n animation frames; false if they never came.
               // Anything the app asked to run on the next frame has run by
               // then, because frame callbacks run in the order they were asked
               // for. A hidden window does get frames, but late and unevenly,
               // so a fixed wait is a guess where this is an ordering -- and
               // polling for a size to stop moving reads one that has not
               // started moving yet.
               const frames = (n) => new Promise((done) => {
                 setTimeout(() => done(false), 5000)
                 const step = (left) => (left === 0
                   ? done(true)
                   : requestAnimationFrame(() => step(left - 1)))
                 step(n)
               })

               const press = (el) => {
                 const opts = { bubbles: true, cancelable: true, button: 0, pointerId: 1, isPrimary: true }
                 el.dispatchEvent(new PointerEvent('pointerdown', opts))
                 el.dispatchEvent(new PointerEvent('pointerup', opts))
                 el.click()
               }

               // Through the prototype's setter, or React treats the write as
               // one it already knows about and the event means nothing.
               const setNativeValue = (proto, el, value) => {
                 Object.getOwnPropertyDescriptor(proto, 'value')
                   .set.call(el, String(value))
               }
               // A picker is a Radix select: a trigger button carrying the
               // current value as 'data-value', and a list of
               // role=option items that exists only while it is open.
               const selectIn = (root) => root.querySelector('.sv-select')
               const escape = () => (document.activeElement || document.body)
                 .dispatchEvent(new KeyboardEvent('keydown', {
                   key: 'Escape', bubbles: true, cancelable: true
                 }))
               const openOptions = async (trigger) => {
                 press(trigger)
                 await frames(3)
                 return Array.from(document.querySelectorAll('[role="option"]'))
               }
               const optionsOf = async (trigger) => {
                 const values = (await openOptions(trigger)).map(o => o.dataset.value)
                 escape()
                 await frames(3)
                 return values
               }
               const setSelectValue = async (trigger, value) => {
                 if (!trigger || trigger.dataset.value === String(value)) return
                 const item = (await openOptions(trigger))
                   .find(o => o.dataset.value === String(value))
                 if (item) press(item)
                 else escape()
                 await frames(3)
               }
               const setRangeValue = (el, value) => {
                 setNativeValue(window.HTMLInputElement.prototype, el, value)
                 el.dispatchEvent(new Event('input', { bubbles: true }))
               }

               // A labelled toggle, found by the text beside it. The root
               // matters: one caller searches the whole window, the rest only
               // the rail.
               const switchRow = (root, text) =>
                 Array.from(root.querySelectorAll('.sv-switch-row'))
                   .find(r => (r.textContent || '').indexOf(text) !== -1)
               // Both of these also take a '.sv-menu-combine' row, which
               // carries its checkbox the same way.
               // A rail toggle is a Radix 'role=switch' button; a combine
               // row still holds a native checkbox.
               const isOn = (row) => {
                 const toggle = row.querySelector('[role="switch"]')
                 return toggle
                   ? toggle.getAttribute('aria-checked') === 'true'
                   : row.querySelector('input').checked
               }
               const flip = (row) =>
                 press(row.querySelector('[role="switch"]') || row.querySelector('input'))
`

/**
 * @param media An existing media file to exercise Range against.
 * @param data The client for the forked data process.
 * @param rendererHtml The built renderer's entry, passed in rather than
 *     derived: this module is bundled into a chunk, so its own __dirname is
 *     `out/main/chunks` and every relative path from here is wrong by one
 *     level -- in a way that only shows at runtime.
 * @param pageUrl Optional page to load in a hidden window -- the Dash dev server
 *     while the views still live there. Checks that the window can actually
 *     reach and render it, which is the one thing the transitional setup
 *     depends on and the one thing a unit test cannot see.
 */
export async function runSmoke(
  media: string,
  data: DataClient,
  rendererHtml: string,
  pageUrl?: string
): Promise<number> {
  const { dirname } = await import('node:path')
  const { promises: fs } = await import('node:fs')

  const look = process.env.SENSORVIEW_SMOKE_LOOK
  const lookCase = process.env.SENSORVIEW_SMOKE_CASE
  if (look && lookCase) {
    return lookAt(lookCase, look, rendererHtml)
  }

  allowRoot(dirname(media))
  const size = (await fs.stat(media)).size
  const url = mediaUrl(media)

  const checks: Check[] = [
    {
      name: 'data process answers',
      run: async () => {
        const result = await data.call('ping', undefined)
        expect(result.ok, `ping failed: ${result.error}`)
        expect(typeof result.data?.pid === 'number', 'ping returned no pid')
        // A different pid is the point: the readers must not be sharing this
        // process with the window.
        expect(result.data!.pid !== process.pid, 'data layer is not a separate process')
        return `pid ${result.data!.pid}, separate from main (${process.pid})`
      }
    },
    {
      name: 'sv:// serves a whole file',
      run: async () => {
        const response = await net.fetch(url)
        expect(response.status === 200, `expected 200, got ${response.status}`)
        expect(
          response.headers.get('accept-ranges') === 'bytes',
          'Accept-Ranges missing: a media element will not try to seek'
        )
        const body = await response.arrayBuffer()
        expect(body.byteLength === size, `got ${body.byteLength} bytes, file is ${size}`)
        return `${size} bytes, ${response.headers.get('content-type')}`
      }
    },
    {
      name: 'sv:// honours a byte range',
      run: async () => {
        const response = await net.fetch(url, { headers: { Range: 'bytes=100-199' } })
        expect(response.status === 206, `expected 206, got ${response.status}`)
        expect(
          response.headers.get('content-range') === `bytes 100-199/${size}`,
          `bad Content-Range: ${response.headers.get('content-range')}`
        )
        const body = await response.arrayBuffer()
        expect(body.byteLength === 100, `expected 100 bytes, got ${body.byteLength}`)
        return 'bytes 100-199 returned as 206'
      }
    },
    {
      name: 'sv:// honours a suffix range',
      run: async () => {
        // `bytes=-N` is what a player sends to read the trailing moov atom of
        // an mp4 that was not written with +faststart.
        const response = await net.fetch(url, { headers: { Range: 'bytes=-64' } })
        expect(response.status === 206, `expected 206, got ${response.status}`)
        expect(
          response.headers.get('content-range') === `bytes ${size - 64}-${size - 1}/${size}`,
          `bad Content-Range: ${response.headers.get('content-range')}`
        )
        return 'last 64 bytes returned as 206'
      }
    },
    {
      name: 'sv:// refuses an unsatisfiable range',
      run: async () => {
        const response = await net.fetch(url, { headers: { Range: `bytes=${size + 10}-` } })
        expect(response.status === 416, `expected 416, got ${response.status}`)
        return '416 with Content-Range'
      }
    },
    {
      name: 'sv:// refuses a path outside an opened case',
      run: async () => {
        // The security property the Flask routes had: a path is readable
        // because the user opened its directory, never because it was named.
        const outside = process.execPath
        expect(!isAllowed(outside), 'the Electron binary should not be allowed')
        const response = await net.fetch(mediaUrl(outside))
        expect(response.status === 404, `expected 404, got ${response.status}`)
        return '404, indistinguishable from missing'
      }
    }
  ]

  // The native-module spike. These are the checks that decide whether the data
  // layer can be TypeScript at all: `nodejs-polars` is a native addon that has
  // to `dlopen` from outside the asar, and `h5wasm` is an Emscripten build that
  // fetches its .wasm from beside its own .js. Both load in `npm run dev` and
  // can still fail in a packaged build, which is why this runs here rather
  // than in vitest.
  const caseDir = process.env.SENSORVIEW_SMOKE_CASE
  if (caseDir) {
    const { join } = await import('node:path')
    const table = join(caseDir, 'scene_0061.parquet')
    const cloud = join(caseDir, 'scene_0061.cloud.h5')

    checks.push({
      name: 'polars reads the table',
      run: async () => {
        const result = await data.call('readTable', { path: table })
        expect(result.ok, `readTable failed: ${result.error}`)
        const { rows, columns } = result.data!
        expect(rows === 19756, `expected 19756 rows, got ${rows}`)
        expect(columns.length === 16, `expected 16 columns, got ${columns.length}`)

        const numeric = columns.filter((c) => c.kind === 'number').length
        const text = columns.filter((c) => c.kind === 'string').length
        expect(numeric === 11, `expected 11 numeric columns, got ${numeric}`)
        expect(text === 5, `expected 5 categorical columns, got ${text}`)

        const sensor = columns.find((c) => c.name === 'Sensor')
        expect(sensor?.levels?.length === 5, `expected 5 sensors, got ${sensor?.levels?.length}`)
        return `${rows} rows, ${numeric} numeric + ${text} categorical`
      }
    });

    checks.push({
      name: 'polars pushes the projection down',
      run: async () => {
        // One column out of sixteen. This is what makes opening a case fast on
        // a table far larger than this one, and it is the main reason the
        // reader is polars rather than a pure-JS Parquet parser.
        const result = await data.call('frameIds', { path: table, frameKey: 'Frame' })
        expect(result.ok, `frameIds failed: ${result.error}`)
        const ids = result.data!
        expect(ids.length === 39, `expected 39 frames, got ${ids.length}`)
        expect(ids[0] === 0, `expected first frame 0, got ${ids[0]}`)
        const ascending = ids.every((v, i) => i === 0 || v > ids[i - 1]!)
        expect(ascending, 'frame ids are not ascending')
        return `${ids.length} frames, ${ids[0]}..${ids[ids.length - 1]}`
      }
    });

    checks.push({
      name: 'a case lists its logs and sidecars',
      run: async () => {
        const result = await data.call('scanCase', { dir: caseDir })
        expect(result.ok, `scanCase failed: ${result.error}`)
        const summary = result.data!
        expect(summary.logs.length === 5, `expected 5 logs, got ${summary.logs.length}`)

        // The pose sidecar is Parquet like the table; without the exclusion it
        // would be listed as a log with none of the manifest's columns.
        const posed = summary.logs.filter((log) => log.stem.endsWith('.reference'))
        expect(posed.length === 0, 'a reference sidecar was listed as a log')

        const first = summary.logs[0]!
        expect(first.hasCloud, `${first.stem} should have a cloud`)
        expect(first.hasCurve, `${first.stem} should have curves`)
        expect(first.hasImage, `${first.stem} should have an image stream`)
        expect(first.hasReference, `${first.stem} should have a pose`)
        expect(summary.frameKey === 'Frame', `frame key was ${summary.frameKey}`)
        return `${summary.logs.length} logs, keys on "${summary.frameKey}"`
      }
    });

    checks.push({
      name: 'a cloud frame resolves through the manifest',
      run: async () => {
        // The path is built from the manifest's pattern and the session's own
        // case directory, never from anything the renderer said -- the
        // property the Flask routes had and the reason this is not just a
        // file read.
        const result = await data.call('logCloudFrame', {
          dir: caseDir,
          stem: 'scene_0061',
          frameId: 0
        })
        expect(result.ok, `logCloudFrame failed: ${result.error}`)
        expect(result.data !== null, 'no cloud came back')
        expect(result.data!.count === 11120, `got ${result.data!.count} points`)
        return `${result.data!.count} points via the manifest pattern`
      }
    });

    checks.push({
      name: 'h5wasm reads a gzip-chunked cloud frame',
      run: async () => {
        const result = await data.call('cloudFrame', { path: cloud, dataset: 'frame_0' })
        expect(result.ok, `cloudFrame failed: ${result.error}`)
        const frame = result.data
        expect(frame !== null, 'no frame came back')
        expect(frame!.count === 11120, `expected 11120 points, got ${frame!.count}`)
        expect(
          frame!.position.length === 11120 * 3,
          `expected interleaved xyz, got ${frame!.position.length}`
        )
        expect(
          Number.isFinite(frame!.position[0]!),
          'first coordinate is not a finite number'
        )
        return `${frame!.count} points, ${(frame!.position.byteLength / 1024).toFixed(0)} KB`
      }
    });

    checks.push({
      name: 'a recording resolves and counts its frames',
      run: async () => {
        const result = await data.call('logImageStreams', {
          dir: caseDir,
          stem: 'scene_0061'
        })
        expect(result.ok, `logImageStreams failed: ${result.error}`)
        const streams = result.data!
        expect(streams.length > 0, 'the log declares no camera')
        const first = streams[0]!
        // An mp4 goes through untouched; the count is demuxed rather than
        // read off the container, which routinely declares nothing.
        expect(first.file.endsWith('.mp4'), `not playable: ${first.file}`)
        expect(
          (first.frames ?? 0) > 0,
          `ffmpeg counted no frames -- is ffmpeg-static unpacked? got ${first.frames}`
        )
        return `${streams.length} stream(s), "${first.label}" with ${first.frames} frames`
      }
    })

    checks.push({
      name: 'a curve plot reads its traces',
      run: async () => {
        const result = await data.call('logCurves', {
          dir: caseDir,
          stem: 'scene_0061',
          frameId: 0
        })
        expect(result.ok, `logCurves failed: ${result.error}`)
        const plots = result.data!
        expect(plots.length > 0, 'no plots came back')
        const traces = plots.flatMap((plot) => plot.traces)
        expect(traces.length > 0, 'every plot came back empty')
        const sample = traces[0]!
        expect(sample.y.length > 0, 'a trace came back with no samples')
        return `${plots.length} plots, ${traces.length} traces, ${sample.y.length} samples in "${sample.label}"`
      }
    })

    checks.push({
      name: 'the reference pose places its mesh',
      run: async () => {
        const result = await data.call('logReference', {
          dir: caseDir,
          stem: 'scene_0061',
          frameId: 0
        })
        expect(result.ok, `logReference failed: ${result.error}`)
        const reference = result.data
        expect(reference !== null, 'no pose for frame 0')
        expect(reference!.mesh !== null, 'the manifest declares a mesh but none was built')
        // Three vertices per triangle, three floats per vertex.
        expect(
          reference!.mesh!.length % 9 === 0,
          `mesh is not whole triangles: ${reference!.mesh!.length} floats`
        )
        expect(
          reference!.mesh!.every((v) => Number.isFinite(v)),
          'the posed mesh carries a non-finite coordinate'
        )

        const bounds = await data.call('logReferenceBounds', {
          dir: caseDir,
          stems: ['scene_0061']
        })
        expect(bounds.ok && bounds.data !== null, 'no reference bounds')
        return (
          `${reference!.mesh!.length / 9} triangles at ` +
          `(${reference!.pose.x.toFixed(1)}, ${reference!.pose.y.toFixed(1)}), ` +
          `yaw ${reference!.pose.yaw.toFixed(2)}`
        )
      }
    })
  }

  // The renderer, opening the real case end to end. Everything above checks a
  // layer; this checks that the layers meet -- the table crossing the process
  // boundary as typed arrays, the frame index surviving it, and the scene
  // drawing what came out.
  if (caseDir) {
    checks.push({
      name: 'the renderer opens the case and draws it',
      run: async () => {
        const { dirname: dirOf, join: joinPath } = await import('node:path')
        // Shown only when a shot was asked for: capturePage on a window that
        // was never shown comes back blank, because there is no compositor
        // output to read.
        const shotPath = process.env.SENSORVIEW_SMOKE_SHOT
        const probe = new BrowserWindow({
          show: Boolean(shotPath),
          // Wide enough for the arrangement this check is about: two
          // overlays down each side and a dock with room for its two panes.
          // At 1280 the gap between the overlays is under the dock's
          // two-pane floor, so the dock shows one and the checks below find
          // a single view picker where they expect a pair.
          width: 1800,
          height: 1000,
          webPreferences: {
            preload: joinPath(dirOf(rendererHtml), '../preload/index.cjs'),
            contextIsolation: true,
            sandbox: true,
            // Load-bearing, and the reason this check once failed only with
            // --shot: a shown window that something else covers is occluded,
            // and Chromium stops an occluded window's compositor, so
            // requestAnimationFrame never fires and the scene stops advancing.
            // A hidden window is never occluded, which is why the invisible
            // run passed. The real window sets this for the same reason.
            backgroundThrottling: false
          }
        })
        let exports = 'exports not run'
        let multi: string
        let selection: string
        try {
          // Set SENSORVIEW_SMOKE_VERBOSE to see what the page says. The
          // single-object form of this event, not the old positional one --
          // under the positional signature the message is undefined and this
          // prints nothing, which looks exactly like a silent page.
          if (process.env.SENSORVIEW_SMOKE_VERBOSE) {
            probe.webContents.on('console-message', (event) => {
              console.log(`      renderer: ${event.message}`)
            })
          }
          process.env.SENSORVIEW_OPEN_CASE = caseDir
          await probe.loadFile(rendererHtml)

          // The app opens the case itself; wait for the scene to say what it
          // drew. This is the check that the layers meet -- a table that
          // crossed the boundary intact but produced no geometry would pass
          // every other check here.
          // No backslash escapes inside the injected source: this is a
          // TypeScript template literal, so an escape sequence is processed
          // here and arrives as the character it denotes -- a newline landing
          // inside a string literal there, which then does not parse.
          const drew = await probe.webContents.executeJavaScript(
            `(async () => {
               const deadline = Date.now() + 20000
               while (Date.now() < deadline) {
                 const error = document.querySelector('.sv-topbar-error')
                 if (error) return { error: error.textContent }
                 const stats = document.getElementById('gl-stats')
                 const text = stats ? stats.textContent || '' : ''
                 // Wait for a frame with something in it. The scene renders
                 // once while empty before the case has loaded, and taking
                 // that as the answer is how this check would pass without
                 // ever drawing the data.
                 const words = text.split(/[^0-9a-zA-Z.]+/)
                 const at = words.indexOf('pts')
                 const drawn = at > 0 ? parseFloat(words[at - 1]) : 0
                 // Points and labels, not points alone. The tick labels are
                 // CSS2D elements placed after the draw that reports the
                 // points, so reading on the first non-empty frame caught
                 // the scene between the two -- which failed about one run
                 // in five, and never on the same check twice.
                 const ticks = Number(
                   (document.getElementById('gl-stage') || {}).dataset?.tickLabels || 0
                 )
                 if (drawn > 0 && ticks > 0) {
                   console.log('scene settled: ' + text)
                   const legend = document.getElementById('gl-legend')
                   return {
                     stats: text,
                     legend: legend ? legend.children.length : 0,
                     ticks: Number(
                       (document.getElementById('gl-stage') || {}).dataset?.tickLabels || 0
                     ),
                     groups: document.querySelectorAll('.sv-gl-legend-row').length
                   }
                 }
                 await new Promise(r => setTimeout(r, 200))
               }
               const stats = document.getElementById('gl-stats')
               const canvas = document.querySelector('canvas')
               return {
                 error: 'the scene never reported drawing anything'
                   + ' | stats=' + JSON.stringify(stats ? stats.textContent : null)
                   + ' | canvas=' + (canvas ? canvas.width + 'x' + canvas.height : 'none')
                   + ' | ticks=' + ((document.getElementById('gl-stage') || {})
                       .dataset?.tickLabels || 0)
                   + ' | legend=' + document.querySelectorAll('.sv-gl-legend-row').length
                   + ' | chips=' + document.querySelectorAll('.sv-chip').length
                   + ' | crumb=' + JSON.stringify(
                       (document.querySelector('.sv-crumb-file') || {}).textContent || null)
               }
             })()`
          )

          expect(!drew.error, `renderer: ${drew.error}`)
          // "idle | 12.0k pts | 27 draws" -- the number before "pts".
          const words = String(drew.stats).split(/\s+/)
          const at = words.indexOf('pts')
          const drawn = at > 0 ? parseFloat(words[at - 1]!) : 0
          expect(drawn > 0, `drew no points: "${drew.stats}"`)
          expect(drew.ticks > 0, 'the axes drew no tick labels')
          expect(drew.legend > 0, 'the legend is empty')

          // And the readers agree with what is on screen.
          const summary = await probe.webContents.executeJavaScript(
            `(async () => {
               const scan = await window.sensorview.data('scanCase', { dir: ${JSON.stringify(caseDir)} })
               if (!scan.ok) return { error: scan.error }
               const log = scan.data.logs[0]
               const read = await window.sensorview.data('readTable', { path: log.file })
               if (!read.ok) return { error: read.error }
               return {
                 logs: scan.data.logs.length,
                 stem: log.stem,
                 rows: read.data.rows,
                 columns: read.data.columns.length,
                 numeric: read.data.columns.filter(c => c.kind === 'number').length,
                 firstValues: Array.from(read.data.columns.find(c => c.name === 'X').values.slice(0, 3))
               }
             })()`
          )

          // And a filter reaches the scene. Clicking off one category is the
          // shortest path from a control to a redraw, and it is the part of
          // the chain -- rail to store to frame build to GPU -- that nothing
          // else here touches.
          const filtered = await probe.webContents.executeJavaScript(
            `(async () => {${DRIVE}
               // Waited for, not read once: the scene settling is not the
               // rail settling. They come from one store but not necessarily
               // one commit, and the rail is the heavier half -- a slider
               // and a chip group per column.
               //
               // This did not fix the intermittent failure it was written
               // for, which turned out to be a render loop taking the whole
               // tree. It is kept because a single read was an assumption
               // about commit order that nothing guaranteed.
               let chips = []
               const ready = Date.now() + 5000
               while (Date.now() < ready) {
                 chips = Array.from(document.querySelectorAll('.sv-filter .sv-chip-on'))
                 if (chips.length >= 2) break
                 await new Promise(r => setTimeout(r, 100))
               }
               if (chips.length < 2) {
                 // Say whether the rail is missing or the window is: a React
                 // render loop takes the whole tree, and "no categorical
                 // filter to flip" on its own sends you looking at filters.
                 const crash = document.querySelector('.sv-crash p')
                 return { error: 'no categorical filter to flip -- '
                   + (crash
                     ? 'the renderer crashed: ' + crash.textContent
                     : document.querySelectorAll('.sv-filter').length + ' filters in the rail') }
               }
               const before = document.getElementById('gl-stats').textContent
               press(chips[0])
               const deadline = Date.now() + 5000
               while (Date.now() < deadline) {
                 const after = document.getElementById('gl-stats').textContent
                 if (after !== before) return { before: before, after: after }
                 await new Promise(r => setTimeout(r, 100))
               }
               return { error: 'the scene did not redraw after a filter change' }
             })()`
          )

          expect(!filtered.error, `filter: ${filtered.error}`)
          // "idle | 11.7k pts | 9 draws". The HUD abbreviates a thousand and
          // up, so reading the number without the suffix makes a cloud of
          // 11,700 points smaller than a frame of 582.
          const pointsIn = (text: string) => {
            const parts = String(text).split(/\s+/)
            const at = parts.indexOf('pts')
            if (at <= 0) {
              return 0
            }
            const word = parts[at - 1]!
            return parseFloat(word) * (word.endsWith('k') ? 1000 : 1)
          }
          expect(
            pointsIn(filtered.after) < pointsIn(filtered.before),
            `turning a category off did not remove points: ${filtered.before} -> ${filtered.after}`
          )

          // The cloud, which is the only thing in the view that costs a read
          // per frame. Switching it on has to reach the HDF5 reader in the
          // data process and come back as geometry.
          const clouded = await probe.webContents.executeJavaScript(
            `(async () => {${DRIVE}
               const row = switchRow(document, 'LIDAR')
               if (!row) return { error: 'no cloud switch -- the case declares none?' }
               const before = document.getElementById('gl-stats').textContent
               flip(row)
               const deadline = Date.now() + 15000
               while (Date.now() < deadline) {
                 const after = document.getElementById('gl-stats').textContent
                 if (after !== before) {
                   // Off again. The cloud is part of the case's view and now
                   // survives a log switch, and seven thousand cloud points
                   // round every later count to the same "7.6k" -- which hid
                   // the 25 detections the hiding check takes away.
                   flip(row)
                   const off = Date.now() + 5000
                   while (Date.now() < off
                     && document.getElementById('gl-stats').textContent === after) {
                     await new Promise(r => setTimeout(r, 100))
                   }
                   return { before: before, after: after }
                 }
                 await new Promise(r => setTimeout(r, 200))
               }
               return { error: 'the cloud never reached the scene' }
             })()`
          )

          expect(!clouded.error, `cloud: ${clouded.error}`)
          expect(
            pointsIn(clouded.after) > pointsIn(clouded.before),
            `the cloud added no points: ${clouded.before} -> ${clouded.after}`
          )

          // Switching logs. A case here holds five, and the picker has to
          // reach the reader for the one chosen rather than redrawing the
          // table already in memory -- so this asserts the scene changed and
          // the breadcrumb followed it.
          const switched = await probe.webContents.executeJavaScript(
            `(async () => {${DRIVE}
               const crumb = document.querySelector('.sv-crumb-file')
               const was = crumb ? crumb.textContent : null
               const buttons = Array.from(document.querySelectorAll('.sv-crumb-btn'))
               const picker = buttons[buttons.length - 1]
               if (!picker) return { error: 'no breadcrumb' }
               press(picker)
               await new Promise(r => setTimeout(r, 200))
               // The name is a button inside the row now: the row also
               // carries the combine checkbox, and clicking it must not be
               // the same thing as opening the log alone.
               const items = Array.from(document.querySelectorAll('[data-sv-menu="logs"] .sv-menu-open'))
               if (items.length < 2) return { error: 'the picker listed ' + items.length + ' logs' }
               const other = items.find(i => i.textContent.indexOf(was) === -1)
               if (!other) return { error: 'every entry is the open log' }
               const before = document.getElementById('gl-stats').textContent
               press(other)
               const deadline = Date.now() + 20000
               while (Date.now() < deadline) {
                 const now = document.querySelector('.sv-crumb-file')
                 const after = document.getElementById('gl-stats').textContent
                 if (now && now.textContent !== was && after !== before) {
                   return { logs: items.length, was: was, now: now.textContent, after: after }
                 }
                 await new Promise(r => setTimeout(r, 200))
               }
               return { error: 'the other log never opened' }
             })()`
          )

          expect(!switched.error, `log picker: ${switched.error}`)
          expect(pointsIn(switched.after) > 0, `the other log drew nothing: ${switched.after}`)

          // The inspector and the reference, both of which only exist once
          // the renderer, the data process and the sv:// handler all agree.
          const inspector = await probe.webContents.executeJavaScript(
            `(async () => {
               const deadline = Date.now() + 20000
               while (Date.now() < deadline) {
                 const videos = Array.from(document.querySelectorAll('video.sv-video'))
                 const plots = document.querySelectorAll('.sv-curve-graph.js-plotly-plot')
                 const ready = videos.filter(v => v.readyState >= 1 && v.videoWidth > 0)
                 if (ready.length > 0 && plots.length > 0) {
                   const traces = document.querySelectorAll('.sv-curve-graph .scatterlayer .trace')
                   return {
                     videos: videos.length,
                     ready: ready.length,
                     size: ready[0].videoWidth + 'x' + ready[0].videoHeight,
                     seeked: ready[0].currentTime,
                     plots: plots.length,
                     traces: traces.length
                   }
                 }
                 await new Promise(r => setTimeout(r, 250))
               }
               const videos = Array.from(document.querySelectorAll('video.sv-video'))
               return {
                 error: 'the inspector never filled'
                   + ' | videos=' + videos.length
                   + ' | readyState=' + videos.map(v => v.readyState).join(',')
                   + ' | plots=' + document.querySelectorAll('.sv-curve-graph.js-plotly-plot').length
               }
             })()`
          )

          expect(!inspector.error, `inspector: ${inspector.error}`)
          // A video that decoded a frame proves the whole sv:// path: the
          // renderer asked, main checked the path against the opened case,
          // and the Range request came back as 206.
          expect(inspector.ready > 0, 'no recording decoded a frame')
          expect(inspector.traces > 0, 'the curve plots drew no traces')

          // And the reference mesh reached the scene. Counted off the draw
          // calls, which rise by one for the mesh and one for its wireframe.
          const posed = await probe.webContents.executeJavaScript(
            `(() => {
               // No backslash escapes in here: this is a TypeScript template
               // literal, so a regex like /[backslash]s+/ arrives with the
               // escape already processed and matches the letter instead.
               const text = document.getElementById('gl-stats').textContent || ''
               const parts = text.split(' ')
               const at = parts.indexOf('draws')
               return at > 0 ? parseInt(parts[at - 1], 10) : 0
             })()`
          )
          expect(posed > 8, `the reference drew nothing: ${posed} draws`)

          // Every dock view, one after another. Each is a different trace
          // type with a different binning path behind it, and a view that
          // throws takes the React tree with it -- so this cycles the picker
          // rather than trusting the one that happens to be on screen.
          const dock = await probe.webContents.executeJavaScript(
            `(async () => {${DRIVE}
               const settle = async () => {
                 for (let i = 0; i < 60; i++) {
                   await new Promise(r => setTimeout(r, 250))
                   const pane = document.querySelector('.sv-pane-graph.js-plotly-plot')
                   if (pane && pane.data && pane.data.length) return pane
                 }
                 return null
               }
               const picker = document.querySelector('.sv-slot-picker .sv-select')
               if (!picker) return { error: 'no dock' }
               const views = (await optionsOf(picker))
                 .filter(v => v && v.length > 0)

               const drawn = {}
               for (const view of views) {
                 const started = performance.now()
                 await setSelectValue(picker, view)
                 const pane = await settle()
                 const took = Math.round(performance.now() - started)
                 if (!pane) return { error: 'the ' + view + ' view drew nothing' }
                 // A trace that exists is not a trace that rendered. Plotly
                 // replaces a pane it cannot draw with a notice, and the
                 // scattergl one looked fine until this looked for marks.
                 // What each trace type actually puts in the DOM. Counted
                 // rather than assumed: a trace that exists is not a trace
                 // that rendered, which is how the scattergl notice hid.
                 const marks = pane.querySelectorAll(
                   '.scatterlayer .point, .scatterlayer .points path,'
                   + ' .heatmaplayer image, .contourlayer .contour,'
                   + ' .barlayer .point, .violinlayer .trace,'
                   + ' .parcats .paths path, .parcats .dimension'
                 ).length
                 const notice = pane.querySelector('.no-webgl, .nowebgl')
                 if (notice) {
                   return {
                     error: view + ': ' + notice.textContent.trim()
                   }
                 }
                 const trace = pane.data[0]
                 const points = trace.x ? trace.x.length
                   : (trace.dimensions ? trace.dimensions[0].values.length : 0)
                 drawn[view] = {
                   traces: pane.data.length,
                   type: trace.type,
                   points: points,
                   marks: marks,
                   ms: took
                 }
               }
               return { views: views, drawn: drawn }
             })()`
          )

          expect(!dock.error, `dock: ${dock.error}`)
          expect(dock.views.length === 5, `expected five views, got ${dock.views.length}`)
          for (const view of dock.views) {
            const drawn = dock.drawn[view]!
            expect(drawn.traces > 0, `the ${view} view built no traces`)
            expect(drawn.points > 0, `the ${view} view drew no points`)
            expect(drawn.marks > 0, `the ${view} view built traces but rendered nothing`)
          }
          // The whole filtered table, not the frame on the slider -- a
          // histogram of one frame's few hundred detections says nothing, and
          // that is the distinction a port would quietly lose.
          expect(
            dock.drawn.histogram.points > 10000,
            `the dock drew ${dock.drawn.histogram.points} rows, not the whole table`
          )
          // The scatter is SVG, one node per point. Fine at this size and the
          // thing that will stop being fine first, so it is measured rather
          // than assumed.
          expect(
            dock.drawn.scatter.ms < 8000,
            `the scatter took ${dock.drawn.scatter.ms}ms for ${dock.drawn.scatter.points} points`
          )

          // Visibility, overlay and the 2D frame scope -- the four features
          // the staging never named, each of which is invisible when wrong:
          // a point hidden in one view but not another, a reference left
          // standing in overlay, a scatter silently showing every frame.
          const views = await probe.webContents.executeJavaScript(
            `(async () => {${DRIVE}
               const settle = (ms) => new Promise(r => setTimeout(r, ms))
               const pts = () => {
                 const text = document.getElementById('gl-stats').textContent || ''
                 const parts = text.split(' ')
                 const at = parts.indexOf('pts')
                 if (at <= 0) return 0
                 const word = parts[at - 1]
                 return parseFloat(word) * (word.indexOf('k') === word.length - 1 ? 1000 : 1)
               }
               const draws = () => {
                 const parts = (document.getElementById('gl-stats').textContent || '').split(' ')
                 const at = parts.indexOf('draws')
                 return at > 0 ? parseInt(parts[at - 1], 10) : 0
               }
               const marks = () => document.querySelectorAll(
                 '.sv-pane-graph .scatterlayer .points path'
               ).length
               const pick = (label) => Array.from(document.querySelectorAll('.sv-pane-field'))
                 .find(f => (f.textContent || '').indexOf(label) === 0)
               const setSelect = (field, value) =>
                 setSelectValue(selectIn(field), value)

               const out = {}
               const rail = document.querySelector('.sv-rail')

               // Click-to-hide is off until asked for: a stray click on the
               // scene must not silently remove a detection.
               const clickRow = switchRow(rail, 'Click a point')
               if (!clickRow) return { error: 'no click-to-hide toggle in the rail' }
               out.clickToHide = isOn(clickRow)

               // Color and colormap are in the rail, not behind the column
               // config: they are read while reading the scene.
               const labels = Array.from(rail.querySelectorAll('.sv-section-label'))
                 .map(l => l.textContent.trim().toLowerCase())
               out.colorInRail = labels.indexOf('color by') !== -1
               out.colormapInRail = labels.indexOf('colormap') !== -1
               out.colorAdjacent =
                 labels.indexOf('colormap') === labels.indexOf('color by') + 1

               // Both slots on a scatter, so the agreement below has two
               // views to agree between.
               const slots = Array.from(document.querySelectorAll('.sv-slot-picker .sv-select'))
               for (const slot of slots) {
                 await setSelectValue(slot, 'scatter')
               }
               await settle(1200)

               // Scope: the default is this frame, and "all" is the whole
               // filtered table.
               const scope = pick('FRAMES') || pick('Frames')
               if (!scope) return { error: 'no frame-scope picker on the scatter' }
               out.scopeCurrent = marks()
               await setSelect(scope, 'all')
               await settle(1500)
               out.scopeAll = marks()
               await setSelect(scope, 'current')
               await settle(1200)

               // The toolbar, which is how a selection is started at all.
               // Checked before the handler below, because the handler was
               // reachable by a synthetic event long before a user could
               // reach it with a mouse.
               const pane0 = document.querySelector('.sv-pane-graph.js-plotly-plot')
               const bar = pane0.querySelector('.modebar')
               if (!bar) return { error: 'the 2D panes have no toolbar' }
               const toolFor = (val) =>
                 bar.querySelector('[data-attr="dragmode"][data-val="' + val + '"]')
               const lassoBtn = toolFor('lasso')
               const selectBtn = toolFor('select')
               if (!lassoBtn || !selectBtn) {
                 return {
                   error: 'no lasso/box select in the toolbar, only '
                     + Array.from(bar.querySelectorAll('[data-attr="dragmode"]'))
                         .map(b => b.getAttribute('data-val')).join(', ')
                 }
               }
               press(lassoBtn)
               await settle(300)
               out.dragmode = pane0._fullLayout.dragmode

               // And the handler, as it sees a selection. Plotly's own drag
               // is not dispatchable; what is checked here is that the rows
               // reach the store and leave every view together.
               const pane = document.querySelector('.sv-pane-graph.js-plotly-plot')
               const rows = Array.from(pane.data[0].customdata || []).slice(0, 25)
               if (rows.length === 0) return { error: 'the scatter carries no row ids' }
               out.before = { scene: pts(), dock: marks() }
               pane.emit('plotly_selected', { points: rows.map(r => ({ customdata: r })) })
               await settle(400)

               const hide = Array.from(document.querySelectorAll('.sv-dock-selection button'))
                 .find(b => b.textContent.trim() === 'Hide')
               if (!hide) return { error: 'no Hide control appeared for the selection' }
               press(hide)
               await settle(1500)
               out.after = { scene: pts(), dock: marks() }
               out.rows = rows.length

               // The rail offers them back.
               const both = Array.from(document.querySelectorAll('.sv-field .sv-chip'))
                 .find(c => c.textContent.trim() === 'Both')
               if (!both) return { error: 'no visibility picker in the rail' }
               press(both)
               await settle(1500)
               out.shown = { scene: pts(), dock: marks() }

               const showAll = Array.from(document.querySelectorAll('.sv-rail-action'))
                 .find(b => b.textContent.indexOf('Show all') !== -1)
               if (showAll) press(showAll)
               await settle(1200)

               // Overlay: every filtered frame at once, and no reference,
               // because no single frame owns the pose.
               out.oneFrame = { pts: pts(), draws: draws() }
               const overlay = switchRow(rail, 'Overlay')
               if (!overlay) return { error: 'no overlay switch in the rail' }
               flip(overlay)
               await settle(2500)
               out.overlaid = { pts: pts(), draws: draws() }
               flip(overlay)
               await settle(1500)

               return out
             })()`
          )

          expect(!views.error, `views: ${views.error}`)

          expect(views.clickToHide === false, 'click-to-hide is on by default')
          expect(views.colorInRail, 'the color picker is not in the rail')
          expect(views.colormapInRail, 'the colormap picker is not in the rail')
          expect(views.colorAdjacent, 'colormap does not sit with the color picker')

          // The control exists and does what it says.
          expect(
            views.dragmode === 'lasso',
            `clicking lasso left dragmode at ${views.dragmode}`
          )

          // The scatter draws one frame by default, as the Dash view did.
          expect(
            views.scopeAll > views.scopeCurrent * 5,
            `scope: ${views.scopeCurrent} current vs ${views.scopeAll} all`
          )

          // One selection, and every view agrees -- the scene and the dock
          // both lose points. That they disagreed is what this is for.
          expect(
            views.after.scene < views.before.scene,
            `hiding left the scene at ${views.after.scene} (was ${views.before.scene}; dock ${views.before.dock} -> ${views.after.dock}, ${views.rows} rows)`
          )
          expect(
            views.after.dock < views.before.dock,
            `hiding left the dock at ${views.after.dock} of ${views.before.dock}`
          )

          // And "Both" brings them back, which is the two-or-more no-op the
          // Python had and nothing could reach until now.
          expect(
            views.shown.scene > views.after.scene,
            `showing hidden points left the scene at ${views.shown.scene}`
          )

          // Overlay draws every filtered frame at once.
          expect(
            views.overlaid.pts > views.oneFrame.pts * 5,
            `overlay drew ${views.overlaid.pts} against one frame's ${views.oneFrame.pts}`
          )
          // And drops the reference with it: there is no frame for a
          // per-frame pose to belong to.
          expect(
            views.overlaid.draws < views.oneFrame.draws,
            `overlay kept ${views.overlaid.draws} draws, so the reference is still drawn`
          )

          selection =
            `lasso reachable, ` +
            `scatter ${views.scopeCurrent} this frame / ${views.scopeAll} all, ` +
            `hiding ${views.rows} rows took the scene ${views.before.scene} -> ` +
            `${views.after.scene} and the dock ${views.before.dock} -> ${views.after.dock}, ` +
            `overlay ${views.oneFrame.pts} -> ${views.overlaid.pts} pts`

          // Combining logs. The case's logs number their frames end to end
          // rather than overlapping, so combining two makes one slider of
          // both -- and the second log's camera must be seeked by its own
          // frame number, not by the slider position. That is the failure
          // the plan calls out: silent, and with a plausible picture.
          const combined = await probe.webContents.executeJavaScript(
            `(async () => {${DRIVE}
               const openMenu = async () => {
                 const buttons = Array.from(document.querySelectorAll('.sv-crumb-btn'))
                 const picker = buttons[buttons.length - 1]
                 if (!document.querySelector('[data-sv-menu="logs"]')) {
                   press(picker)
                   await new Promise(r => setTimeout(r, 200))
                 }
                 return Array.from(document.querySelectorAll('.sv-menu-combine'))
               }

               const rows = await openMenu()
               if (rows.length < 2) return { error: 'fewer than two logs' }
               const nameOf = function (row) {
                 return row.querySelector('.sv-menu-label').textContent
               }
               const open = rows.find(function (r) { return isOn(r) })
               const other = rows.find(function (r) { return !isOn(r) })
               if (!open || !other) return { error: 'nothing to combine' }

               flip(other)

               const deadline = Date.now() + 30000
               let total = 0
               while (Date.now() < deadline) {
                 await new Promise(r => setTimeout(r, 250))
                 const label = document.querySelector('.sv-transport-count, .sv-frame-count')
                 const crumb = document.querySelector('.sv-crumb-more')
                 if (crumb) {
                   const slider = document.querySelector('.sv-transport input[type=range]')
                   total = slider ? Number(slider.max) + 1 : 0
                   if (total > 0) break
                 }
               }
               if (total === 0) return { error: 'the combination never loaded' }

               const slider = document.querySelector('.sv-transport input[type=range]')
               const setFrame = async function (at) {
                 setRangeValue(slider, at)
                 await new Promise(r => setTimeout(r, 900))
               }

               const seenAt = async function (at) {
                 await setFrame(at)
                 const videos = Array.from(document.querySelectorAll('video.sv-video'))
                 const labels = Array.from(document.querySelectorAll('.sv-video-label'))
                   .map(function (l) { return l.textContent })
                 return {
                   labels: labels,
                   times: videos.map(function (v) { return v.currentTime }),
                   durations: videos.map(function (v) { return v.duration })
                 }
               }

               const first = await seenAt(0)
               const late = await seenAt(total - 2)
               return {
                 total: total,
                 names: [nameOf(open), nameOf(other)],
                 first: first,
                 late: late
               }
             })()`
          )

          expect(!combined.error, `combine: ${combined.error}`)
          // Two logs of 39 and 40 frames, end to end.
          expect(
            combined.total === 79,
            `combined slider has ${combined.total} positions, expected 79`
          )
          // Each position shows the log that recorded it, and only that one.
          // Which log that is at position 0 follows the frame ids, not the
          // order the logs were loaded in -- the primary leads a shared
          // position, but it does not own the start of the slider.
          const stemOf = (labels: string[]) =>
            new Set(labels.map((label) => label.split(' · ')[0]))
          const atStart = stemOf(combined.first.labels)
          const atEnd = stemOf(combined.late.labels)

          expect(
            combined.first.labels.length > 0 && atStart.size === 1,
            `position 0 showed ${combined.first.labels.join(', ')}`
          )
          expect(
            combined.late.labels.length > 0 && atEnd.size === 1,
            `the last position showed ${combined.late.labels.join(', ')}`
          )
          // The two ends belong to different logs, which is the whole point
          // of combining them -- and what makes the seek below a real test.
          expect(
            [...atStart][0] !== [...atEnd][0],
            `both ends showed ${[...atStart][0]}, so the logs did not combine`
          )
          for (const stem of [...atStart, ...atEnd]) {
            expect(
              combined.names.includes(stem),
              `the camera showed ${stem}, which is not one of the combined logs`
            )
          }
          // And it is seeked by its own frame. Position 77 is the second
          // log's frame 38 of 40, so the clip sits near its end -- where
          // seeking by the slider position would put it past the end and
          // clamp it there, which looks the same for the last frame and
          // wrong for every other one. Checked near the end precisely
          // because that is where the two agree least.
          const where = combined.late.times[0] / combined.late.durations[0]
          expect(
            where > 0.9 && where <= 1,
            `the second log's clip sat at ${(where * 100).toFixed(0)}% of its duration`
          )
          multi =
            `combined ${combined.names.join(' + ')} into ${combined.total} frames, ` +
            `${[...atStart][0]} then ${[...atEnd][0]}, ` +
            `the second at ${(where * 100).toFixed(0)}% of its own clip`

          // The exports, through the real save path: the renderer builds the
          // bytes and main writes them, which is the half a renderer-side
          // mock would leave unchecked.
          const saveDir = process.env.SENSORVIEW_SMOKE_SAVE_DIR
          if (saveDir) {
            const exported = await probe.webContents.executeJavaScript(
              `(async () => {${DRIVE}
                 // Idempotent: the button toggles, so clicking it while the
                 // menu is already open closes it -- which is how the first
                 // version of this found nothing to click.
                 const openMenu = async () => {
                   const button = document.querySelector('.sv-export .sv-icon-btn')
                   if (!button) return null
                   if (!document.querySelector('[data-sv-menu="export"]')) {
                     press(button)
                     await new Promise(r => setTimeout(r, 200))
                   }
                   return Array.from(document.querySelectorAll('[data-sv-menu="export"] .sv-menu-item'))
                 }
                 const items = await openMenu()
                 if (!items || items.length === 0) return { error: 'no export menu' }
                 const labels = items.map(function (i) {
                   return i.querySelector('.sv-menu-label').textContent
                 })

                 const done = []
                 for (let at = 0; at < labels.length; at++) {
                   const fresh = await openMenu()
                   press(fresh[at])
                   // The animation walks every frame of every combined log,
                   // reading a cloud for each, so it is minutes rather than
                   // seconds. The others are near-instant; one budget covers
                   // both rather than a table of them.
                   const deadline = Date.now() + 420000
                   while (Date.now() < deadline) {
                     await new Promise(r => setTimeout(r, 250))
                     const note = document.querySelector('.sv-export-note')
                     const text = note ? note.textContent : ''
                     if (text && text.indexOf('Saved') === 0) {
                       done.push(labels[at] + ' -> ' + text.slice(6))
                       break
                     }
                     if (text && text.length > 0 && text.indexOf('…') === -1
                         && text.indexOf('Saved') !== 0) {
                       return { error: labels[at] + ': ' + text }
                     }
                   }
                   if (done.length !== at + 1) {
                     const note = document.querySelector('.sv-export-note')
                     return {
                       error: labels[at] + ' never finished, last said '
                         + JSON.stringify(note ? note.textContent : null)
                     }
                   }
                 }
                 return { done: done, labels: labels }
               })()`
            )

            expect(!exported.error, `export: ${exported.error}`)
            // Every entry the menu offers, whatever that count is -- the
            // check walks the menu rather than a list written here, so
            // adding an export does not need this number changed.
            expect(
              exported.done.length === exported.labels.length,
              `${exported.done.length} of ${exported.labels.length} exports finished`
            )

            // The dock's own menu: every figure it offers, in every format.
            // Its notes are beside its button, not in the top bar.
            const figures = await probe.webContents.executeJavaScript(
              `(async () => {${DRIVE}
                 const openMenu = async () => {
                   const button = document.querySelector('.sv-dock .sv-figure-export .sv-icon-btn')
                   if (!button) return null
                   if (!document.querySelector('[data-sv-menu="export-dock"]')) {
                     press(button)
                     await new Promise(r => setTimeout(r, 200))
                   }
                   return Array.from(document.querySelectorAll('[data-sv-menu="export-dock"] .sv-menu-item'))
                 }
                 const items = await openMenu()
                 if (!items || items.length === 0) return { error: 'no dock export menu' }
                 const count = items.length
                 const done = []
                 for (let at = 0; at < count; at++) {
                   const fresh = await openMenu()
                   press(fresh[at])
                   const deadline = Date.now() + 60000
                   while (Date.now() < deadline) {
                     await new Promise(r => setTimeout(r, 250))
                     const note = document.querySelector('.sv-dock .sv-figure-note')
                     const text = note ? note.textContent : ''
                     if (text && text.indexOf('Saved') === 0) {
                       done.push(text.slice(6))
                       break
                     }
                     if (text && text.indexOf('…') === -1) {
                       return { error: 'dock export ' + at + ': ' + text }
                     }
                   }
                   if (done.length !== at + 1) return { error: 'dock export ' + at + ' never finished' }
                 }
                 return { done: done }
               })()`
            )
            expect(!figures.error, `figure export: ${figures.error}`)

            const { readdir, stat: statOf } = await import('node:fs/promises')
            const written = await readdir(saveDir)
            const sizes: Record<string, number> = {}
            for (const name of written) {
              sizes[name] = (await statOf(joinPath(saveDir, name))).size
            }

            const find = (suffix: string) => written.find((name) => name.endsWith(suffix))
            const csv = find('_table.csv')
            expect(Boolean(csv), `no CSV was written: ${written.join(', ')}`)
            // 19,063 rows plus a header, so a file of a few bytes means an
            // empty mask rather than a working export.
            expect(sizes[csv!]! > 500_000, `the CSV is ${sizes[csv!]} bytes`)

            const parquet = find('_table.parquet')
            expect(Boolean(parquet), 'no Parquet file was written')
            expect(sizes[parquet!]! > 50_000, `the Parquet file is ${sizes[parquet!]} bytes`)

            const png = find('_scene.png')
            expect(Boolean(png), 'no PNG was written')
            expect(sizes[png!]! > 10_000, `the PNG is ${sizes[png!]} bytes -- a blank canvas?`)

            const figure = written.find((name) => /_figure(-left)?\.html$/.test(name))
            expect(Boolean(figure), 'no figure page was written')
            const figureImage = written.find((name) => /_figure(-left)?\.(png|svg)$/.test(name))
            expect(Boolean(figureImage), 'no figure image was written')
            // Self-contained means the library is in the file.
            expect(
              sizes[figure!]! > 3_000_000,
              `the figure page is ${sizes[figure!]} bytes -- is Plotly inlined?`
            )

            const video = written.find((name) => name.includes('_animation.'))
            expect(Boolean(video), 'no animation was written')
            expect(sizes[video!]! > 10_000, `the animation is ${sizes[video!]} bytes`)

            // And the self-contained page actually opens. A fresh window
            // with no preload, no protocol handler and nothing of this app
            // in it: if the file needs anything that is not inside it, this
            // is where that shows up rather than on someone else's machine.
            const reader = new BrowserWindow({
              show: false,
              webPreferences: { sandbox: true, nodeIntegration: false }
            })
            try {
              await reader.loadFile(joinPath(saveDir, figure!))
              const drew = await reader.webContents.executeJavaScript(
                `(async () => {
                   for (let i = 0; i < 40; i++) {
                     await new Promise(r => setTimeout(r, 250))
                     const plot = document.querySelector('.js-plotly-plot')
                     if (plot) {
                       // Whatever the dock happened to be showing when the
                       // export ran, which is not always a scatter.
                       const marks = plot.querySelectorAll(
                         '.scatterlayer .point, .scatterlayer .points path,'
                         + ' .heatmaplayer image, .contourlayer .contour,'
                         + ' .barlayer .point, .violinlayer .trace,'
                         + ' .parcats .paths path, .parcats .dimension'
                       ).length
                       if (marks > 0) return { marks: marks, plotly: typeof Plotly }
                     }
                   }
                   return { error: 'the exported page drew nothing'
                     + ' | Plotly=' + typeof Plotly }
                 })()`
              )
              expect(!drew.error, `exported page: ${drew.error}`)
              exports =
                `${written.length} exports, CSV ${(sizes[csv!]! / 1024).toFixed(0)} KB, ` +
                `video ${(sizes[video!]! / 1024).toFixed(0)} KB, ` +
                `page reopens with ${drew.marks} marks`
            } finally {
              reader.destroy()
            }
          }

          // Shot last, with the cloud on and the category put back, so the
          // picture is the view in full rather than mid-check.
          if (shotPath) {
            const { writeFile } = await import('node:fs/promises')
            await probe.webContents.executeJavaScript(
              `(async () => {${DRIVE}
                 const off = document.querySelector('.sv-filter .sv-chip:not(.sv-chip-on)')
                 if (off) press(off)
                 const pickers = Array.from(document.querySelectorAll('.sv-slot-picker .sv-select'))
                 // One pane is a legitimate state: the dock drops to it
                 // when the gap between the overlays is too narrow for two.
                 const choose = async (at, view) => {
                   if (!pickers[at]) return
                   await setSelectValue(pickers[at], view)
                 }
                 await choose(0, 'scatter')
                 await choose(1, 'heatmap')
                 // The column config open, since that is the new surface.
                 const config = document.querySelector('.sv-topbar-menu .sv-icon-btn')
                 if (config) press(config)
                 await new Promise(r => setTimeout(r, 2500))
               })()`
            )
            const image = await probe.webContents.capturePage()
            await writeFile(shotPath, image.toPNG())
          }

          // What a menu is expected to do once something else implements it.
          // `useMenu` used to be the answer and was honest in its header about
          // only doing a third of the job; nothing here ever checked the other
          // two thirds, so they went unverified either way. The browser
          // fixture cannot help -- it serves no case, so neither top-bar menu
          // renders -- which leaves this the only place the contract is
          // visible at all.
          const menus = await probe.webContents.executeJavaScript(
            `(async () => {${DRIVE}
               const wait = (ms) => new Promise(r => setTimeout(r, ms))
               const shown = () => !!document.querySelector('[data-sv-menu="logs"]')
               const key = (name) => {
                 const el = document.activeElement || document.body
                 el.dispatchEvent(new KeyboardEvent('keydown', {
                   key: name, bubbles: true, cancelable: true
                 }))
               }

               const buttons = Array.from(document.querySelectorAll('.sv-crumb-btn'))
               const trigger = buttons[buttons.length - 1]
               if (!trigger) return { error: 'no breadcrumb trigger' }
               if (shown()) { key('Escape'); await wait(250) }

               press(trigger)
               await wait(300)
               if (!shown()) return { error: 'the picker did not open' }

               // Walk the menu and report what the arrows actually land on.
               // Which roles are reachable is the question: the combine
               // checkbox is a native input rather than a Radix item, so it
               // is in the roving order only if the library tolerates it.
               const walked = []
               for (let i = 0; i < 6; i++) {
                 key('ArrowDown')
                 await wait(60)
                 const at = document.activeElement
                 walked.push(at ? (at.getAttribute('role') || at.tagName.toLowerCase()) : 'none')
               }

               key('Escape')
               await wait(300)
               // Read before anything below moves the focus itself.
               const closed = !shown()
               const focusBack = document.activeElement === trigger

               // A group of chips is one tab stop with the arrows moving
               // inside it, not one tab stop per chip. That is the thing a
               // toggle group buys over a row of buttons, and the thing most
               // easily lost without anything looking wrong.
               const group = document.querySelector('.sv-filter .sv-chips')
               const chips = group ? Array.from(group.querySelectorAll('.sv-chip')) : []
               let keys_ = null
               if (chips.length >= 2) {
                 chips[0].focus()
                 key('ArrowRight')
                 await wait(80)
                 keys_ = {
                   // Reachable from the keyboard at all, and the arrows
                   // move within it. Not a count of tab stops: Radix leaves
                   // the group itself focusable as a delegate that forwards
                   // to the current chip, so the attributes say two where
                   // the behaviour is one, and pinning that down would be
                   // asserting someone else's bookkeeping rather than
                   // anything this app promises.
                   reachable: group.getAttribute('tabindex') === '0'
                     || chips.some(c => c.getAttribute('tabindex') === '0'),
                   role: String(group.getAttribute('role')),
                   moved: document.activeElement === chips[1],
                   chips: chips.length
                 }
               }

               // Two thumbs on one value, and apart again. This is the
               // case the dual-thumb control was hand-written for -- "the
               // control dies exactly when the range is narrowest" -- so it
               // is the one thing a library taking that job over has to be
               // held to.
               //
               // Driven through the boxes rather than the keyboard: End and
               // Home move the last and first thumb whatever has focus, so
               // neither can walk one thumb onto the other. Typing the top
               // of the range into the bottom box is also the way a person
               // would actually land both on one value.
               const range = document.querySelector('.sv-range')
               const thumbs = range
                 ? Array.from(range.querySelectorAll('[role="slider"]'))
                 : []
               const boxes = range
                 ? Array.from(range.querySelectorAll('.sv-range-box'))
                 : []
               let pinch = null
               if (thumbs.length === 2 && boxes.length === 2) {
                 const read = () => thumbs.map(t => Number(t.getAttribute('aria-valuenow')))
                 const before = read()
                 setNativeValue(window.HTMLInputElement.prototype, boxes[0], boxes[1].value)
                 boxes[0].dispatchEvent(new Event('input', { bubbles: true }))
                 boxes[0].dispatchEvent(new KeyboardEvent('keydown', {
                   key: 'Enter', bubbles: true, cancelable: true
                 }))
                 await wait(200)
                 const met = read()

                 thumbs[0].focus()
                 key('ArrowLeft')
                 await wait(200)
                 const apart = read()
                 pinch = {
                   met: met[0] === met[1],
                   freed: apart[0] !== apart[1],
                   ordered: apart[0] <= apart[1],
                   before: before.join('..'),
                   met_: met.join('..'),
                   apart: apart.join('..')
                 }
               }

               // The scene, still reachable through the gap. Panels are
               // transparent boxes lying over the canvas, so one that
               // forgets to let the pointer through swallows every orbit
               // drag across a region that looks like empty scene -- which
               // nothing else here would catch, because everything else
               // clicks on controls.
               //
               // Asked of the middle of the gap between the top bar and the
               // transport, which is panel all the way down and canvas only
               // if each layer has stood aside.
               const centre = document.querySelector('.sv-center')
               let through = null
               if (centre) {
                 const box = centre.getBoundingClientRect()
                 const x = Math.round(box.left + box.width / 2)
                 const y = Math.round(box.top + box.height / 2)
                 const hit = document.elementFromPoint(x, y)
                 through = {
                   at: x + ',' + y,
                   id: hit ? (hit.id || hit.className || hit.tagName) : 'nothing'
                 }
               }

               // Folding the dock from its head, and back. The store says
               // whether it is folded and the panel is told; a drag past the
               // threshold folds the panel and the store is told. Two
               // writers keeping each other in step is the shape of the loop
               // that once took the window here, so this goes round the
               // circle twice and checks the window is still standing.
               const fold = Array.from(document.querySelectorAll('.sv-dock-head .sv-icon-btn'))
                 .find(b => /(Collapse|Expand) the dock/.test(b.getAttribute('aria-label') || ''))
               const dockEl = document.querySelector('.sv-dock')
               let folding = null
               if (fold && dockEl) {
                 const tall = Math.round(dockEl.getBoundingClientRect().height)
                 press(fold)
                 await wait(400)
                 const folded = Math.round(dockEl.getBoundingClientRect().height)
                 press(fold)
                 await wait(400)
                 const back = Math.round(dockEl.getBoundingClientRect().height)
                 // Each layer's height, for a failure to point at. A dock
                 // measuring zero once turned out to be its panel borrowing a
                 // class the stylesheet hides; this is what showed it.
                 const h = (el) => el ? Math.round(el.getBoundingClientRect().height) : -1
                 const region = dockEl.parentElement
                 const panel = region ? region.parentElement : null
                 folding = {
                   layers: 'gap ' + h(document.querySelector('.sv-center-gap'))
                     + ', panel ' + h(panel) + ', region ' + h(region)
                     + (region && getComputedStyle(region).display === 'none'
                       ? ' (display: none)' : ''),
                   tall: tall,
                   folded: folded,
                   back: back,
                   standing: !document.querySelector('.sv-crash')
                 }
               }

               // The centre column between the side ones, not under them.
               // Nothing else here would notice it straying: every other
               // check clicks or counts, and a dock half-hidden behind the
               // inspector still has all its chart marks. Asked of the dock
               // and the top bar, the two things that live in the gap.
               const side = (sel) => {
                 const el = document.querySelector(sel)
                 return el ? el.getBoundingClientRect() : null
               }
               const insp = side('.sv-inspector')
               const rail = side('.sv-rail .sv-stack')
               let fits = null
               const inGap = ['.sv-dock', '.sv-topbar', '.sv-transport']
               if (insp && rail) {
                 const strays = inGap.map(sel => {
                   const box = side(sel)
                   if (!box) return null
                   const over = Math.max(0, Math.round(box.right - insp.left))
                   const under = Math.max(0, Math.round(rail.right - box.left))
                   return over > 2 || under > 2
                     ? sel + ' overlaps by ' + Math.max(over, under) + 'px'
                     : null
                 }).filter(Boolean)
                 fits = { ok: strays.length === 0, strays: strays.join('; ') }
               }

               // The handle between the camera and the curves. Resized
               // with the keyboard rather than a synthetic drag: the
               // library takes pointer capture, which a dispatched
               // PointerEvent cannot give it, but it binds keydown on the
               // separator itself.
               //
               // The frame is read either side of the same key press. An
               // arrow belongs to whatever is focused, and useHotkeys stands
               // aside by honouring defaultPrevented -- so a handle that
               // resizes *and* scrubs would be that guard not working, which
               // nothing else here would notice.
               const handle = document.querySelector('.sv-inspector .sv-splitter')
               const card = document.querySelector('.sv-card-camera')
               const readFrame = () => {
                 const at = document.querySelector('.sv-frame-readout')
                 return at ? (at.textContent || '').trim() : null
               }
               let resize = null
               if (handle && card) {
                 const was = Math.round(card.getBoundingClientRect().height)
                 const frameWas = readFrame()
                 handle.focus()
                 for (let i = 0; i < 3; i++) {
                   handle.dispatchEvent(new KeyboardEvent('keydown', {
                     key: 'ArrowUp', bubbles: true, cancelable: true
                   }))
                   await wait(80)
                 }
                 await wait(200)
                 resize = {
                   was: was,
                   now: Math.round(card.getBoundingClientRect().height),
                   frameHeld: readFrame() === frameWas,
                   frame: frameWas
                 }
               }

               // The selected-chrome styling, which hangs off an attribute
               // the toggle groups set. It is the kind of thing that goes
               // dead quietly: the markup still renders, the state is still
               // right, and nothing looks selected any more. So compare the
               // two panes buttons rather than trusting the attribute.
               const layout = Array.from(
                 document.querySelectorAll('.sv-dock-layout .sv-icon-btn')
               )
               const on = layout.find(b => b.getAttribute('data-state') === 'on')
               const off = layout.find(b => b.getAttribute('data-state') !== 'on')
               const paint = (el) => el
                 ? getComputedStyle(el).backgroundColor + ' ' + getComputedStyle(el).color
                 : null

               // The rail's width: a key on its handle, the width that comes of
               // it, and the HUD following. The insets reflow() measures off the
               // rail frame the scene, so a rail that moved without them would
               // leave the data framed against a column that is not there any
               // more. Then what reached the settings, which is the only part of
               // a drag a relaunch can see, and a double-click clearing it.
               const railHandle = document.querySelector('[aria-label="Filter rail width"]')
               const stackOf = (side) => {
                 const el = document.querySelector(side + ' .sv-stack')
                 return el ? Math.round(el.getBoundingClientRect().width) : -1
               }
               const insetL = () => Math.round(parseFloat(getComputedStyle(
                 document.documentElement).getPropertyValue('--sv-inset-l')) || 0)
               const railWidthStored = async () => {
                 const read = await window.sensorview.settings.get()
                 return read.ok ? read.data.layout.railW : 'unread'
               }
               let railKeys = null
               if (railHandle) {
                 const was = stackOf('.sv-rail')
                 const insetWas = insetL()
                 railHandle.focus()
                 railHandle.dispatchEvent(new KeyboardEvent('keydown', {
                   key: 'ArrowRight', bubbles: true, cancelable: true
                 }))
                 // Past the 400ms the layout write waits for.
                 await wait(800)
                 const now = stackOf('.sv-rail')
                 // The inset follows on the scene's ResizeObserver, which
                 // runs only when this hidden window is given a frame -- and
                 // those come late and unevenly, so a fixed wait read the old
                 // inset about half the time. Wait for it to move instead,
                 // with a deadline that still fails a HUD that never follows.
                 const insetBy = Date.now() + 3000
                 while (insetL() === insetWas && Date.now() < insetBy) {
                   await wait(100)
                 }
                 const insetNow = insetL()
                 const kept = await railWidthStored()
                 railHandle.dispatchEvent(new MouseEvent('dblclick', {
                   bubbles: true, cancelable: true
                 }))
                 await wait(800)
                 railKeys = {
                   was: was,
                   now: now,
                   insetWas: insetWas,
                   insetNow: insetNow,
                   kept: kept,
                   reset: stackOf('.sv-rail'),
                   cleared: await railWidthStored(),
                   stats: (document.getElementById('gl-stats') || {}).textContent || ''
                 }
               }

               // Every overlay on a side put away, leaving the column its tray.
               // The panel has to be the tray's width -- not the column it was,
               // not nothing -- the dock beside it must clear it, and the tray's
               // button has to be what is under the pointer where it sits, or
               // the way back is covered. Then both brought back, and the column
               // has to return to the width it had.
               const trayRound = async (side, handleLabel, widen) => {
                 // Off the default width first. A column rebuilt from its
                 // default and a column put back where it was look the same
                 // from the default, which is how a restore that did nothing
                 // passed here once.
                 const handle = document.querySelector('[aria-label="' + handleLabel + '"]')
                 if (handle) {
                   handle.focus()
                   handle.dispatchEvent(new KeyboardEvent('keydown', {
                     key: widen, bubbles: true, cancelable: true
                   }))
                   await wait(800)
                 }
                 const before = stackOf(side)
                 // One at a time, found afresh each time: hiding the camera
                 // takes the inspector's split down and its curves card comes
                 // back as a different element, so a button found before the
                 // first press can be detached by the second.
                 let hidden = 0
                 for (let i = 0; i < 4; i++) {
                   const hide = document.querySelector(side + ' .sv-group-hide')
                   if (!hide) break
                   press(hide)
                   hidden++
                   await wait(250)
                 }
                 await wait(400)
                 await frames(2)
                 const aside = document.querySelector(side)
                 const tray = document.querySelector(side + ' .sv-tray')
                 const box = tray ? tray.getBoundingClientRect() : null
                 const button = tray ? tray.querySelector('.sv-icon-btn') : null
                 const at = button ? button.getBoundingClientRect() : null
                 const hit = at
                   ? document.elementFromPoint(
                     Math.round(at.left + at.width / 2), Math.round(at.top + at.height / 2))
                   : null
                 const dock = document.querySelector('.sv-dock')
                 const dockBox = dock ? dock.getBoundingClientRect() : null
                 const panel = aside ? aside.closest('[data-panel]') : null
                 const sideHandle = document.querySelector('[aria-label="' + handleLabel + '"]')
                 const out = {
                   // A column down to its tray has nothing to resize, so its
                   // handle should not be there to grab.
                   handleShown: sideHandle ? getComputedStyle(sideHandle).visibility !== 'hidden' : false,
                   presence: panel ? panel.getAttribute('data-presence') : 'no panel',
                   note: (document.querySelector(side + ' .sv-note') || {}).textContent || '',
                   share: panel ? (panel.style.flex || '').split(' ')[0] : '',
                   hidden: hidden,
                   asideW: aside ? Math.round(aside.getBoundingClientRect().width) : -1,
                   trayW: box ? Math.round(box.width) : -1,
                   onScreen: box ? box.left >= 0 && box.right <= window.innerWidth : false,
                   reachable: Boolean(hit && button && (hit === button || button.contains(hit))),
                   clear: box && dockBox
                     ? (side === '.sv-rail'
                       ? dockBox.left >= box.right - 1
                       : dockBox.right <= box.left + 1)
                     : false
                 }
                 for (let i = 0; i < 4; i++) {
                   const back = document.querySelector(side + ' .sv-tray .sv-icon-btn')
                   if (!back) break
                   press(back)
                   await wait(300)
                 }
                 await wait(500)
                 await frames(2)
                 out.before = before
                 out.after = stackOf(side)
                 return out
               }
               const railTray = await trayRound('.sv-rail', 'Filter rail width', 'ArrowRight')
               const inspectorTray = await trayRound('.sv-inspector', 'Inspector width', 'ArrowLeft')

               return {
                 closed: closed,
                 focusBack: focusBack,
                 railKeys: railKeys,
                 railTray: railTray,
                 inspectorTray: inspectorTray,
                 chipKeys: keys_,
                 resize: resize,
                 through: through,
                 folding: folding,
                 fits: fits,
                 pinch: pinch,
                 roles: walked.filter((r, at) => walked.indexOf(r) === at).sort(),
                 panes: layout.length,
                 paneMarked: Boolean(on) && paint(on) !== paint(off),
                 // The visibility filter is the single-select group: whatever
                 // the stylesheet calls on should be what the group calls
                 // checked, or the two have drifted apart.
                 visibilityAgrees: Array.from(
                   document.querySelectorAll('.sv-field .sv-chip')
                 ).every(c => (c.className.indexOf('sv-chip-on') !== -1)
                   === (c.getAttribute('aria-checked') === 'true'))
               }
             })()`
          )

          expect(!menus.error, `menu: ${menus.error}`)
          expect(menus.closed, 'Escape did not close the picker')
          expect(menus.focusBack, 'closing the picker did not give focus back to its trigger')
          expect(menus.panes === 2, `the dock offered ${menus.panes} pane layouts`)
          expect(menus.paneMarked, 'the chosen pane layout does not look chosen')
          expect(menus.visibilityAgrees, 'the visibility chips disagree about which one is on')
          expect(menus.chipKeys, 'no categorical filter with two chips to walk')
          expect(menus.chipKeys.reachable, 'a group of chips cannot be reached with Tab')
          expect(
            menus.chipKeys.role === 'group',
            `a column's values are marked up as a ${menus.chipKeys.role}, not a group`
          )
          expect(menus.chipKeys.moved, 'an arrow key does not move between chips in a group')
          expect(menus.pinch, 'no two-thumb filter to pinch')
          expect(
            menus.pinch.met,
            `the two thumbs would not meet on one value (${menus.pinch.met_})`
          )
          expect(
            menus.pinch.freed,
            `the thumbs met and would not come apart again (${menus.pinch.apart})`
          )
          expect(menus.pinch.ordered, `the thumbs came apart crossed (${menus.pinch.apart})`)
          expect(menus.through, 'no centre column to look through')
          expect(
            String(menus.through.id).indexOf('gl-canvas') !== -1,
            `the middle of the gap is ${menus.through.id}, not the scene -- ` +
              'something over the canvas is taking the pointer'
          )
          expect(menus.fits, 'no inspector or rail to measure the gap against')
          expect(
            menus.fits.ok,
            `the centre column strays under a side column: ${menus.fits.strays}`
          )
          expect(menus.railKeys, 'no handle on the rail')
          {
            const k = menus.railKeys
            expect(k.now > k.was, `a key on the rail's handle left it at ${k.now}px, from ${k.was}px`)
            // The HUD's left edge is the rail's right edge, so the two moves
            // are the same distance.
            expect(
              Math.abs(k.insetNow - k.insetWas - (k.now - k.was)) <= 3,
              `the rail grew ${k.now - k.was}px and the HUD's left inset ` +
                `${k.insetNow - k.insetWas}px -- the scene is framed against the old column`
            )
            expect(pointsIn(k.stats) > 0, `the scene stopped drawing after the rail moved: ${k.stats}`)
            expect(
              typeof k.kept === 'number' && Math.abs(k.kept - k.now) <= 2,
              `the rail is ${k.now}px but the settings hold ${k.kept}`
            )
            expect(
              Math.abs(k.reset - k.was) <= 2,
              `a double-click put the rail at ${k.reset}px, not back at ${k.was}px`
            )
            expect(k.cleared === null, `a double-click left ${k.cleared} in the settings`)
          }
          for (const [name, t] of [
            ['rail', menus.railTray],
            ['inspector', menus.inspectorTray]
          ] as const) {
            expect(t.hidden === 2, `the ${name} offered ${t.hidden} cards to put away`)
            expect(
              Math.abs(t.asideW - t.trayW) <= 2 && t.trayW >= 30,
              `the ${name} folded to ${t.asideW}px around a ${t.trayW}px tray ` +
                `(panel says ${t.presence}, share ${t.share}%${t.note ? ', note: ' + t.note : ''})`
            )
            expect(t.onScreen, `the ${name}'s tray is off the screen`)
            expect(!t.handleShown, `the ${name} is down to its tray and its handle is still showing`)
            expect(t.clear, `the dock lies over the ${name}'s tray`)
            expect(t.reachable, `something covers the ${name}'s tray button`)
            expect(
              Math.abs(t.after - t.before) <= 2,
              `the ${name} came back at ${t.after}px, not the ${t.before}px it was`
            )
            expect(
              t.before !== (name === 'rail' ? 288 : 480),
              `the ${name} was still at its default width going in, so a restore ` +
                'that did nothing would pass'
            )
          }
          expect(menus.folding, 'no fold control on the dock')
          expect(menus.folding.standing, 'folding the dock crashed the renderer')
          expect(
            menus.folding.folded < menus.folding.tall / 2,
            `folding the dock left it ${menus.folding.folded}px, from ${menus.folding.tall}px ` +
              `-- ${menus.folding.layers}`
          )
          expect(
            Math.abs(menus.folding.back - menus.folding.tall) <= 2,
            `unfolding the dock brought it back to ${menus.folding.back}px, not ${menus.folding.tall}px`
          )
          expect(menus.resize, 'no handle between the camera and the curves')
          expect(
            menus.resize.now < menus.resize.was,
            `the inspector handle took three arrows and left the camera at ` +
              `${menus.resize.now}px, from ${menus.resize.was}px`
          )
          expect(
            menus.resize.frameHeld,
            `resizing with the arrows also scrubbed the transport, from frame ${menus.resize.frame}`
          )
          // Both controls in a row, not just the name. The combine box is the
          // one that is easy to lose: it is a native input, and a menu
          // library walks its own items rather than whatever else is inside
          // it, so this is the assertion that caught it going missing.
          for (const role of ['menuitemradio', 'menuitemcheckbox']) {
            expect(
              menus.roles.includes(role),
              `the arrows reached ${menus.roles.join(', ')} -- no ${role} among them`
            )
          }

          expect(!summary.error, `renderer could not read the case: ${summary.error}`)
          expect(summary.rows === 19756, `renderer saw ${summary.rows} rows`)
          expect(summary.columns === 16, `renderer saw ${summary.columns} columns`)
          // Typed arrays have to survive the structured clone across the
          // boundary; a plain object would arrive as {"0": .., "1": ..} and
          // every coordinate would silently be undefined.
          expect(
            summary.firstValues.every((v: number) => Number.isFinite(v)),
            `X arrived as ${JSON.stringify(summary.firstValues)}`
          )
          return (
            `${summary.rows} rows -> ${drew.groups} groups, ${drew.ticks} ticks, ` +
            `${pointsIn(filtered.before)} pts -> ${pointsIn(filtered.after)} with one category off, ` +
            `${pointsIn(clouded.after)} with the cloud on; ` +
            `${switched.logs} logs, ${switched.was} -> ${switched.now}; ` +
            `${inspector.ready}/${inspector.videos} videos at ${inspector.size}, ` +
            `${inspector.traces} traces in ${inspector.plots} plots; ` +
            `dock ${dock.views.map((v: string) => `${v} ${dock.drawn[v].marks} marks`).join(', ')}; ` +
            `${selection}; ${multi}; ` +
            `menu keys reach ${menus.roles.join(' + ')}, Escape closes and hands focus back, ` +
            `the chosen pane and visibility chips still read as chosen, ` +
            `${menus.chipKeys.chips} chips make a group the arrows move within, ` +
            `two thumbs meet on one value and come apart to ${menus.pinch.apart}, ` +
            `the inspector handle resizes ${menus.resize.was} -> ${menus.resize.now}px ` +
            `without scrubbing, the gap's middle is still the scene and its ` +
            `contents stay inside it, ` +
            `the dock folds ${menus.folding.tall} -> ${menus.folding.folded} -> ` +
            `${menus.folding.back}px, ` +
            `the rail resizes ${menus.railKeys.was} -> ${menus.railKeys.now}px with the HUD ` +
            `following and the width kept, both sides fold to a ` +
            `${menus.railTray.trayW}px tray and come back; ` +
            `${exports}`
          )
        } finally {
          probe.destroy()
        }
      }
    })
  }

  // What the app comes back as.
  //
  // Every check above opens a case because the environment names one. This is
  // the other way in, and the one a user takes: the case the last session was
  // left on, found in the settings file, authorised for `sv://` by main, and
  // reopened with the view that was set up on it. Both halves fail quietly --
  // a window that comes up empty looks like a first run, and a view that comes
  // back half-applied looks like a preference nobody saved.
  if (caseDir) {
    checks.push({
      name: 'the last case and its view come back on a relaunch',
      run: async () => {
        const { dirname: dirOf, join: joinPath } = await import('node:path')
        const probe = new BrowserWindow({
          show: false,
          width: 1800,
          height: 1000,
          webPreferences: {
            preload: joinPath(dirOf(rendererHtml), '../preload/index.cjs'),
            contextIsolation: true,
            sandbox: true,
            backgroundThrottling: false
          }
        })
        const named = process.env.SENSORVIEW_OPEN_CASE
        let relaunched: BrowserWindow | null = null
        try {
          await probe.loadFile(rendererHtml)

          // A session to come back to: the case in the recent list, and a
          // view nobody would land on by accident.
          const left = await probe.webContents.executeJavaScript(
            `(async () => {
               const dir = ${JSON.stringify(caseDir)}
               await window.sensorview.settings.set({ recent: [dir] })
               // Two widths nobody would land on by accident, for the cold
               // start to come back to. Nested, so the whole layout is read
               // back and written whole: set merges only the top level.
               const was = await window.sensorview.settings.get()
               if (was.ok) {
                 await window.sensorview.settings.set({
                   layout: Object.assign({}, was.data.layout, { railW: 333, inspectorW: 444 })
                 })
               }
               await window.sensorview.settings.rememberView(dir, {
                 colormap: 'Jet',
                 decay: 4,
                 clickToHide: true,
                 slots: [{ view: 'violin' }, { view: 'parcats' }]
               })
               const stored = await window.sensorview.settings.get()
               return stored.ok ? stored.data.views[dir] : { error: stored.error }
             })()`
          )
          expect(!left.error, `could not store a view: ${left.error}`)
          expect(left.colormap === 'Jet', `the stored view reads back as ${JSON.stringify(left)}`)
          // Both halves of the entry survive each other. They are written by
          // two different components, and `set` merges only the top level.
          expect(Array.isArray(left.slots), 'the panes did not survive the second write')

          // The relaunch. A second window rather than a reload, because a
          // reload keeps the renderer process and this is about what a cold
          // start comes up as. Nothing names a case this time, so main has to
          // find one for itself.
          delete process.env.SENSORVIEW_OPEN_CASE
          // Opened before the old one goes, because `window-all-closed`
          // quits the app: letting the count reach zero between the two
          // fails the next load rather than the check.
          relaunched = new BrowserWindow({
            show: false,
            width: 1800,
            height: 1000,
            webPreferences: {
              preload: joinPath(dirOf(rendererHtml), '../preload/index.cjs'),
              contextIsolation: true,
              sandbox: true,
              backgroundThrottling: false
            }
          })
          probe.destroy()
          // The cold start says what it is doing too. Without this the one
          // window whose startup is the whole point of the check was the one
          // window verbose mode could not hear.
          if (process.env.SENSORVIEW_SMOKE_VERBOSE) {
            relaunched.webContents.on('console-message', (event) => {
              console.log(`      relaunched: ${event.message}`)
            })
          }
          await relaunched.loadFile(rendererHtml)

          const back = await relaunched.webContents.executeJavaScript(
            `(async () => {${DRIVE}
               const field = (label) => Array.from(document.querySelectorAll('.sv-field'))
                 .find(f => ((f.querySelector('.sv-section-label') || {}).textContent || '')
                   .trim() === label)
               const deadline = Date.now() + 30000
               let crumb = null
               while (Date.now() < deadline) {
                 const error = document.querySelector('.sv-topbar-error')
                 if (error) return { error: error.textContent }
                 crumb = document.querySelector('.sv-crumb-file')
                 const colormap = field('Colormap')
                 // The restore is a round trip of its own, after the case has
                 // loaded, so a crumb is not yet an answer.
                 if (crumb && crumb.textContent && colormap
                     && selectIn(colormap) && selectIn(colormap).dataset.value === 'Jet') {
                   break
                 }
                 await new Promise(r => setTimeout(r, 250))
               }
               const colormap = field('Colormap')
               const decay = field('Decay')
               const widthOf = (sel) => {
                 const el = document.querySelector(sel)
                 return el ? Math.round(el.getBoundingClientRect().width) : null
               }
               const click = switchRow(document.querySelector('.sv-rail'), 'Click a point')
               return {
                 crumb: crumb ? crumb.textContent : null,
                 colormap: colormap && selectIn(colormap) ? selectIn(colormap).dataset.value : null,
                 decay: decay ? decay.querySelector('input').value : null,
                 clickToHide: click ? isOn(click) : null,
                 slots: Array.from(document.querySelectorAll('.sv-slot-picker .sv-select'))
                   .map(s => s.dataset.value),
                 storedLayout: await (async () => {
                   const read = await window.sensorview.settings.get()
                   return read.ok ? JSON.stringify(read.data.layout) : read.error
                 })(),
                 // Read two frames on. The widths come back a frame after the
                 // case does: a column is pinned until it has something to show,
                 // and the stored width is put back on the frame after the panels
                 // are laid out for what is in them. Read on the frame the case
                 // lands and the answer is the default.
                 framesRun: await frames(2),
                 railW: widthOf('.sv-rail .sv-stack'),
                 inspectorW: widthOf('.sv-inspector .sv-stack'),
                 points: document.getElementById('gl-stats')
                   ? document.getElementById('gl-stats').textContent
                   : null
               }
             })()`
          )

          expect(!back.error, `relaunch: ${back.error}`)
          // The case itself: nothing named it, so this came out of the
          // settings file -- and the breadcrumb is only filled once a log
          // has been read through main's own allowlist.
          expect(Boolean(back.crumb), 'the app came up with no case open')
          expect(back.colormap === 'Jet', `the colormap came back as ${back.colormap}`)
          expect(back.decay === '4', `the decay came back as ${back.decay}`)
          expect(back.clickToHide === true, 'click-to-hide did not come back on')
          expect(back.framesRun, 'the relaunched window never ran an animation frame')
          expect(
            back.railW !== null && Math.abs(back.railW - 333) <= 2,
            `the rail came back at ${back.railW}px, not the 333px stored ` +
              `(settings now hold ${back.storedLayout})`
          )
          expect(
            back.inspectorW !== null && Math.abs(back.inspectorW - 444) <= 2,
            `the inspector came back at ${back.inspectorW}px, not the 444px stored`
          )
          // The panes are the dock's own state, written separately and
          // reconciled against whatever columns this log has.
          expect(
            back.slots.includes('violin') && back.slots.includes('parcats'),
            `the dock came back showing ${back.slots.join(', ') || 'nothing'}`
          )
          return (
            `reopened ${back.crumb} with ${back.colormap}, decay ${back.decay}, ` +
            `panes ${back.slots.join(' + ')}`
          )
        } finally {
          if (named) {
            process.env.SENSORVIEW_OPEN_CASE = named
          }
          if (!probe.isDestroyed()) {
            probe.destroy()
          }
          relaunched?.destroy()
        }
      }
    })
  }

  if (pageUrl) {
    checks.push({
      name: 'a window loads the views',
      run: async () => {
        const probe = new BrowserWindow({ show: false, webPreferences: { sandbox: true } })
        try {
          await probe.loadURL(pageUrl)
          const title = await probe.webContents.executeJavaScript('document.title')
          expect(typeof title === 'string' && title.length > 0, 'page has no title')
          return `${pageUrl} → "${title}"`
        } finally {
          probe.destroy()
        }
      }
    })
  }

  let failed = 0
  for (const check of checks) {
    try {
      const detail = await check.run()
      console.log(`  ok    ${check.name} — ${detail}`)
    } catch (error) {
      failed++
      console.error(`  FAIL  ${check.name}`)
      console.error(`        ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  console.log(failed === 0 ? `\n${checks.length} checks passed` : `\n${failed} failed`)
  return failed
}

/**
 * Open a case and photograph the scene, with no checks.
 *
 * For looking at what any case draws -- the checks above are written against
 * the NuScenes case and fail before their own shot on anything else. Each
 * entry of `SENSORVIEW_SMOKE_LOOK_STEPS` (comma-separated) is a camera preset
 * id, optionally followed by `+N` or `-N` wheel ticks over the scene centre;
 * one PNG is written per step, beside `out` with the step appended.
 * `SENSORVIEW_SMOKE_LOOK_JS` is run in the page first (as an async function
 * body) and its answer printed; `SENSORVIEW_SMOKE_LOOK_WIDTH` sets the window
 * width.
 *
 * @param caseDir The case to open.
 * @param out Where the first PNG goes; later ones get `-<step>` suffixes.
 * @returns 0 once the shots are written, 1 if the scene never drew.
 */
async function lookAt(caseDir: string, out: string, rendererHtml: string): Promise<number> {
  const { dirname: dirOf, join: joinPath } = await import('node:path')
  const { writeFile } = await import('node:fs/promises')
  const steps = (process.env.SENSORVIEW_SMOKE_LOOK_STEPS || 'iso').split(',')
  const probe = new BrowserWindow({
    show: true,
    width: Number(process.env.SENSORVIEW_SMOKE_LOOK_WIDTH) || 1800,
    height: 1000,
    webPreferences: {
      preload: joinPath(dirOf(rendererHtml), '../preload/index.cjs'),
      contextIsolation: true,
      sandbox: true,
      backgroundThrottling: false
    }
  })
  try {
    process.env.SENSORVIEW_OPEN_CASE = caseDir
    await probe.loadFile(rendererHtml)
    const drew = await probe.webContents.executeJavaScript(
      `(async () => {
         const deadline = Date.now() + 30000
         while (Date.now() < deadline) {
           const stats = (document.getElementById('gl-stats') || {}).textContent || ''
           const ticks = Number((document.getElementById('gl-stage') || {}).dataset?.tickLabels || 0)
           if (/[1-9][0-9.]*k? pts/.test(stats) && ticks > 0) return stats
           await new Promise(r => setTimeout(r, 200))
         }
         return null
       })()`
    )
    if (!drew) {
      console.error('  look: the scene never drew')
      return 1
    }
    // Anything to do to the page first -- hide a panel, open a menu -- and
    // what it answers, printed, for measuring what a shot shows.
    const before = process.env.SENSORVIEW_SMOKE_LOOK_JS
    if (before) {
      // Caught here, so a script that throws says so and the window still
      // closes -- uncaught, the rejection left Electron running until killed.
      try {
        const answer = await probe.webContents.executeJavaScript(`(async () => {${DRIVE}
 ${before} })()`)
        console.log(`  look: ${JSON.stringify(answer)}`)
      } catch (problem) {
        console.error(`  look: the page script threw: ${problem instanceof Error ? problem.message : String(problem)}`)
        return 1
      }
    }
    for (const [index, step] of steps.entries()) {
      if (step === 'now') {
        // A shot of the page as the script left it, with nothing clicked.
        await writeFile(out, (await probe.webContents.capturePage()).toPNG())
        console.log(`  look: now -> ${out}`)
        continue
      }
      const [, preset = 'iso', wheel = '0'] = /^([a-z]*)([+-]\d+)?$/.exec(step) ?? []
      await probe.webContents.executeJavaScript(
        `(async () => {
           const button = Array.from(document.querySelectorAll('.sv-gl-preset'))
             .find(b => (b.title || '').toLowerCase().includes(${JSON.stringify(preset)}))
           if (button) button.click()
           const canvas = document.getElementById('gl-canvas')
           const box = canvas.getBoundingClientRect()
           const ticks = ${Number(wheel)}
           for (let i = 0; i < Math.abs(ticks); i++) {
             canvas.dispatchEvent(new WheelEvent('wheel', {
               deltaY: ticks > 0 ? 100 : -100, bubbles: true, cancelable: true,
               clientX: box.left + box.width / 2, clientY: box.top + box.height / 2
             }))
           }
           await new Promise(r => setTimeout(r, 800))
         })()`
      )
      const path = index === 0 ? out : out.replace(/\.png$/i, '') + `-${step}.png`
      await writeFile(path, (await probe.webContents.capturePage()).toPNG())
      console.log(`  look: ${step} -> ${path}`)
    }
    return 0
  } finally {
    probe.destroy()
  }
}
