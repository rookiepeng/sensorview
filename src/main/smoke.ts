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
          width: 1280,
          height: 800,
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
                 const ticks = document.querySelectorAll('.sv-gl-tick').length
                 if (drawn > 0 && ticks > 0) {
                   console.log('scene settled: ' + text)
                   const legend = document.getElementById('gl-legend')
                   return {
                     stats: text,
                     legend: legend ? legend.children.length : 0,
                     ticks: document.querySelectorAll('.sv-gl-tick').length,
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
                   + ' | ticks=' + document.querySelectorAll('.sv-gl-tick').length
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
            `(async () => {
               const chips = Array.from(document.querySelectorAll('.sv-chip-on'))
               if (chips.length < 2) return { error: 'no categorical filter to flip' }
               const before = document.getElementById('gl-stats').textContent
               chips[0].click()
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
            `(async () => {
               const rows = Array.from(document.querySelectorAll('.sv-switch-row'))
               const row = rows.find(r => (r.textContent || '').indexOf('LIDAR') !== -1)
               if (!row) return { error: 'no cloud switch -- the case declares none?' }
               const before = document.getElementById('gl-stats').textContent
               row.querySelector('input').click()
               const deadline = Date.now() + 15000
               while (Date.now() < deadline) {
                 const after = document.getElementById('gl-stats').textContent
                 if (after !== before) return { before: before, after: after }
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
            `(async () => {
               const crumb = document.querySelector('.sv-crumb-file')
               const was = crumb ? crumb.textContent : null
               const buttons = Array.from(document.querySelectorAll('.sv-crumb-btn'))
               const picker = buttons[buttons.length - 1]
               if (!picker) return { error: 'no breadcrumb' }
               picker.click()
               await new Promise(r => setTimeout(r, 200))
               // The name is a button inside the row now: the row also
               // carries the combine checkbox, and clicking it must not be
               // the same thing as opening the log alone.
               const items = Array.from(document.querySelectorAll('.sv-breadcrumb .sv-menu-open'))
               if (items.length < 2) return { error: 'the picker listed ' + items.length + ' logs' }
               const other = items.find(i => i.textContent.indexOf(was) === -1)
               if (!other) return { error: 'every entry is the open log' }
               const before = document.getElementById('gl-stats').textContent
               other.click()
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
            `(async () => {
               const settle = async () => {
                 for (let i = 0; i < 60; i++) {
                   await new Promise(r => setTimeout(r, 250))
                   const pane = document.querySelector('.sv-pane-graph.js-plotly-plot')
                   if (pane && pane.data && pane.data.length) return pane
                 }
                 return null
               }
               const picker = document.querySelector('.sv-slot-picker select')
               if (!picker) return { error: 'no dock' }
               const views = Array.from(picker.options)
                 .map(o => o.value)
                 .filter(v => v.length > 0)

               const drawn = {}
               for (const view of views) {
                 const started = performance.now()
                 picker.value = view
                 picker.dispatchEvent(new Event('change', { bubbles: true }))
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
            `(async () => {
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
               const setSelect = (field, value) => {
                 const el = field.querySelector('select')
                 const setter = Object.getOwnPropertyDescriptor(
                   window.HTMLSelectElement.prototype, 'value').set
                 setter.call(el, value)
                 el.dispatchEvent(new Event('change', { bubbles: true }))
               }

               const out = {}

               // Both slots on a scatter, so the agreement below has two
               // views to agree between.
               const slots = Array.from(document.querySelectorAll('.sv-slot-picker select'))
               for (const slot of slots) {
                 const setter = Object.getOwnPropertyDescriptor(
                   window.HTMLSelectElement.prototype, 'value').set
                 setter.call(slot, 'scatter')
                 slot.dispatchEvent(new Event('change', { bubbles: true }))
               }
               await settle(1200)

               // Scope: the default is this frame, and "all" is the whole
               // filtered table.
               const scope = pick('FRAMES') || pick('Frames')
               if (!scope) return { error: 'no frame-scope picker on the scatter' }
               out.scopeCurrent = marks()
               setSelect(scope, 'all')
               await settle(1500)
               out.scopeAll = marks()
               setSelect(scope, 'current')
               await settle(1200)

               // A lasso, as the handler sees one. Plotly's own drag is not
               // dispatchable; what is checked here is that a selection of
               // rows reaches the store and leaves every view together.
               const pane = document.querySelector('.sv-pane-graph.js-plotly-plot')
               const rows = Array.from(pane.data[0].customdata || []).slice(0, 25)
               if (rows.length === 0) return { error: 'the scatter carries no row ids' }
               out.before = { scene: pts(), dock: marks() }
               pane.emit('plotly_selected', { points: rows.map(r => ({ customdata: r })) })
               await settle(400)

               const hide = Array.from(document.querySelectorAll('.sv-dock-selection button'))
                 .find(b => b.textContent.trim() === 'Hide')
               if (!hide) return { error: 'no Hide control appeared for the selection' }
               hide.click()
               await settle(1500)
               out.after = { scene: pts(), dock: marks() }
               out.rows = rows.length

               // The rail offers them back.
               const both = Array.from(document.querySelectorAll('.sv-rail .sv-chip'))
                 .find(c => c.textContent.trim() === 'Both')
               if (!both) return { error: 'no visibility picker in the rail' }
               both.click()
               await settle(1500)
               out.shown = { scene: pts(), dock: marks() }

               const showAll = Array.from(document.querySelectorAll('.sv-rail-action'))
                 .find(b => b.textContent.indexOf('Show all') !== -1)
               if (showAll) showAll.click()
               await settle(1200)

               // Overlay: every filtered frame at once, and no reference,
               // because no single frame owns the pose.
               out.oneFrame = { pts: pts(), draws: draws() }
               const overlay = Array.from(document.querySelectorAll('.sv-rail .sv-switch-row'))
                 .find(r => (r.textContent || '').indexOf('Overlay') !== -1)
               if (!overlay) return { error: 'no overlay switch in the rail' }
               overlay.querySelector('input').click()
               await settle(2500)
               out.overlaid = { pts: pts(), draws: draws() }
               overlay.querySelector('input').click()
               await settle(1500)

               return out
             })()`
          )

          expect(!views.error, `views: ${views.error}`)

          // The scatter draws one frame by default, as the Dash view did.
          expect(
            views.scopeAll > views.scopeCurrent * 5,
            `scope: ${views.scopeCurrent} current vs ${views.scopeAll} all`
          )

          // One selection, and every view agrees -- the scene and the dock
          // both lose points. That they disagreed is what this is for.
          expect(
            views.after.scene < views.before.scene,
            `hiding left the scene at ${views.after.scene}`
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
            `(async () => {
               const openMenu = async () => {
                 const buttons = Array.from(document.querySelectorAll('.sv-crumb-btn'))
                 const picker = buttons[buttons.length - 1]
                 if (!document.querySelector('.sv-breadcrumb .sv-menu')) {
                   picker.click()
                   await new Promise(r => setTimeout(r, 200))
                 }
                 return Array.from(document.querySelectorAll('.sv-menu-combine'))
               }

               const rows = await openMenu()
               if (rows.length < 2) return { error: 'fewer than two logs' }
               const nameOf = function (row) {
                 return row.querySelector('.sv-menu-label').textContent
               }
               const open = rows.find(function (r) { return r.querySelector('input').checked })
               const other = rows.find(function (r) { return !r.querySelector('input').checked })
               if (!open || !other) return { error: 'nothing to combine' }

               other.querySelector('input').click()

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
                 const setter = Object.getOwnPropertyDescriptor(
                   window.HTMLInputElement.prototype, 'value').set
                 setter.call(slider, String(at))
                 slider.dispatchEvent(new Event('input', { bubbles: true }))
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
              `(async () => {
                 // Idempotent: the button toggles, so clicking it while the
                 // menu is already open closes it -- which is how the first
                 // version of this found nothing to click.
                 const openMenu = async () => {
                   const button = document.querySelector('.sv-export .sv-icon-btn')
                   if (!button) return null
                   if (!document.querySelector('.sv-export .sv-menu')) {
                     button.click()
                     await new Promise(r => setTimeout(r, 200))
                   }
                   return Array.from(document.querySelectorAll('.sv-export .sv-menu-item'))
                 }
                 const items = await openMenu()
                 if (!items || items.length === 0) return { error: 'no export menu' }
                 const labels = items.map(function (i) {
                   return i.querySelector('.sv-menu-label').textContent
                 })

                 const done = []
                 for (let at = 0; at < labels.length; at++) {
                   const fresh = await openMenu()
                   fresh[at].click()
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
                 return { done: done }
               })()`
            )

            expect(!exported.error, `export: ${exported.error}`)
            expect(
              exported.done.length === 5,
              `expected five exports, got ${exported.done.length}`
            )

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

            const png = find('_scene.png')
            expect(Boolean(png), 'no PNG was written')
            expect(sizes[png!]! > 10_000, `the PNG is ${sizes[png!]} bytes -- a blank canvas?`)

            const figure = find('_figure.html')
            expect(Boolean(figure), 'no figure page was written')
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
              `(async () => {
                 const off = document.querySelector('.sv-chip:not(.sv-chip-on)')
                 if (off) off.click()
                 const pickers = Array.from(document.querySelectorAll('.sv-slot-picker select'))
                 const choose = (at, view) => {
                   pickers[at].value = view
                   pickers[at].dispatchEvent(new Event('change', { bubbles: true }))
                 }
                 choose(0, 'scatter')
                 choose(1, 'heatmap')
                 // The column config open, since that is the new surface.
                 const config = document.querySelector('.sv-topbar-menu .sv-icon-btn')
                 if (config) config.click()
                 await new Promise(r => setTimeout(r, 2500))
               })()`
            )
            const image = await probe.webContents.capturePage()
            await writeFile(shotPath, image.toPNG())
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
            `${selection}; ${multi}; ${exports}`
          )
        } finally {
          probe.destroy()
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
