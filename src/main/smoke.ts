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
 * @param pageUrl Optional page to load in a hidden window -- the Dash dev server
 *     while the views still live there. Checks that the window can actually
 *     reach and render it, which is the one thing the transitional setup
 *     depends on and the one thing a unit test cannot see.
 */
export async function runSmoke(
  media: string,
  data: DataClient,
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
