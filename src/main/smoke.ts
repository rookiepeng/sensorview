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
        const probe = new BrowserWindow({
          show: false,
          width: 1280,
          height: 800,
          webPreferences: {
            preload: joinPath(dirOf(rendererHtml), '../preload/index.cjs'),
            contextIsolation: true,
            sandbox: true
          }
        })
        try {
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
               return { error: 'the scene never reported drawing anything' }
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
          return `${summary.rows} rows -> ${drew.stats}, ${drew.groups} groups, ${drew.ticks} ticks`
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
