// `sv://` — reading a file off disk from the renderer, with Range.
//
// The camera panel seeks an mp4 by setting `video.currentTime`. A browser can
// only do that if the response honours HTTP Range; without it the element must
// download the whole clip before it can seek at all. The Dash app got this from
// Flask's `send_file(conditional=True)`, and there is no HTTP server any more,
// so this scheme replaces it.
//
// `file://` is not an option: the renderer runs with `sandbox: true` and a CSP,
// and Chromium will not serve ranged media over it.
//
// The security property of the Python routes is kept deliberately: a path is
// readable only if it sits under a directory the user has opened this session.
// The renderer can ask for any URL it likes; it cannot widen that set.
//
// The logic this file is thin over lives in `src/shared/media.ts`, so range
// parsing and path containment can be tested without Electron.

import { createReadStream, promises as fs } from 'node:fs'
import { Readable } from 'node:stream'
import { resolve } from 'node:path'

import { protocol } from 'electron'

import { SCHEME, decodeMediaUrl, mimeFor, parseByteRange, withinRoots } from '../shared/media'

export { mediaUrl } from '../shared/media'

/** Directories the user has opened. Nothing outside these is readable. */
const roots = new Set<string>()

/**
 * Authorise a directory and everything under it.
 *
 * Called when a case is opened. There is no matching revoke: a session that
 * has shown a file once may show it again, and forgetting a root mid-session
 * would break a panel still on screen.
 */
export function allowRoot(dir: string): void {
  roots.add(resolve(dir))
}

/** Whether a path is inside an authorised root. */
export function isAllowed(path: string): boolean {
  return withinRoots(path, roots)
}

/**
 * Declare the scheme's privileges.
 *
 * Must run before `app.whenReady()`. `stream: true` is the one that matters --
 * without it Chromium buffers the whole response and ranged playback silently
 * stops working.
 */
export function registerScheme(): void {
  protocol.registerSchemesAsPrivileged([
    {
      scheme: SCHEME,
      privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true }
    }
  ])
}

/** Install the handler. Must run after `app.whenReady()`. */
export function registerHandler(): void {
  protocol.handle(SCHEME, async (request) => {
    const path = decodeMediaUrl(request.url)
    if (!path) {
      return new Response('Bad sv:// URL', { status: 400 })
    }
    if (!isAllowed(path)) {
      // Deliberately indistinguishable from a missing file: whether a path
      // exists outside the opened roots is not the renderer's business.
      return new Response('Not found', { status: 404 })
    }

    let size: number
    try {
      const stat = await fs.stat(path)
      if (!stat.isFile()) {
        return new Response('Not found', { status: 404 })
      }
      size = stat.size
    } catch {
      return new Response('Not found', { status: 404 })
    }

    const common = { 'Accept-Ranges': 'bytes', 'Content-Type': mimeFor(path) }

    if (request.method === 'HEAD') {
      return new Response(null, {
        status: 200,
        headers: { ...common, 'Content-Length': String(size) }
      })
    }

    const header = request.headers.get('range')
    if (!header) {
      return new Response(Readable.toWeb(createReadStream(path)) as ReadableStream, {
        status: 200,
        headers: { ...common, 'Content-Length': String(size) }
      })
    }

    const range = parseByteRange(header, size)
    if (!range) {
      return new Response(null, {
        status: 416,
        headers: { ...common, 'Content-Range': `bytes */${size}` }
      })
    }

    const stream = createReadStream(path, { start: range.start, end: range.end })
    return new Response(Readable.toWeb(stream) as ReadableStream, {
      status: 206,
      headers: {
        ...common,
        'Content-Length': String(range.end - range.start + 1),
        'Content-Range': `bytes ${range.start}-${range.end}/${size}`
      }
    })
  })
}
