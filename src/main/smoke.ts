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
          stem: 'scene_0061'
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
                 if (drawn > 0) {
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
               const items = Array.from(document.querySelectorAll('.sv-menu-item'))
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

          // Shot last, with the cloud on and the category put back, so the
          // picture is the view in full rather than mid-check.
          if (shotPath) {
            const { writeFile } = await import('node:fs/promises')
            await probe.webContents.executeJavaScript(
              `(async () => {
                 const off = document.querySelector('.sv-chip:not(.sv-chip-on)')
                 if (off) off.click()
                 const buttons = Array.from(document.querySelectorAll('.sv-crumb-btn'))
                 buttons[buttons.length - 1].click()
                 await new Promise(r => setTimeout(r, 600))
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
            `${switched.logs} logs, ${switched.was} -> ${switched.now}`
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
