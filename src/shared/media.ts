// The parts of the `sv://` scheme that are just logic.
//
// Split out of `src/main/protocol.ts` so they can be tested without Electron:
// range parsing and path containment are exactly the code where an off-by-one
// or a missing separator check is both easy to write and expensive to find.

import { resolve, sep } from 'node:path'

export const SCHEME = 'sv'

const MIME: Record<string, string> = {
  '.mp4': 'video/mp4',
  '.m4v': 'video/mp4',
  '.webm': 'video/webm',
  '.ogg': 'video/ogg',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg'
}

/** Content type for a path, by extension. */
export function mimeFor(path: string): string {
  const dot = path.lastIndexOf('.')
  const ext = dot === -1 ? '' : path.slice(dot).toLowerCase()
  return MIME[ext] ?? 'application/octet-stream'
}

/**
 * Build a URL the renderer can hand to a `<video>` or `<img>`.
 *
 * The path is base64url-encoded rather than placed in the URL directly: a
 * Windows path carries a colon and backslashes, and a standard-scheme URL
 * lowercases its host, which would corrupt a case-sensitive path elsewhere.
 */
export function mediaUrl(path: string): string {
  return `${SCHEME}://media/${Buffer.from(path, 'utf8').toString('base64url')}`
}

/** Recover the path from an `sv://` URL, or null if it is not one. */
export function decodeMediaUrl(url: string): string | null {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== `${SCHEME}:` || parsed.hostname !== 'media') {
      return null
    }
    const encoded = parsed.pathname.replace(/^\/+/, '')
    if (!encoded) {
      return null
    }
    const decoded = Buffer.from(encoded, 'base64url').toString('utf8')
    return decoded.length > 0 ? decoded : null
  } catch {
    return null
  }
}

/**
 * Whether `path` lies inside one of `roots`.
 *
 * The separator test is the point: a prefix comparison alone lets
 * `/data/case-evil` pass as inside `/data/case`.
 */
export function withinRoots(path: string, roots: Iterable<string>): boolean {
  const full = resolve(path)
  for (const root of roots) {
    const base = resolve(root)
    if (full === base || full.startsWith(base + sep)) {
      return true
    }
  }
  return false
}

export interface ByteRange {
  start: number
  end: number
}

/**
 * Parse one byte range against a known length.
 *
 * Only the single-range form is handled, which is all a media element sends.
 * A multipart range, a malformed one, or one that starts past the end returns
 * null, and the caller answers 416.
 *
 * @param header The raw `Range` header value.
 * @param size The file's length in bytes.
 * @returns Inclusive start and end, or null.
 */
export function parseByteRange(header: string, size: number): ByteRange | null {
  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim())
  if (!match) {
    return null
  }

  const [, rawStart, rawEnd] = match
  let start: number
  let end: number

  if (rawStart === '') {
    // `bytes=-500` is the *last* 500 bytes -- what a player sends to find the
    // trailing moov atom of an mp4 written without +faststart.
    const suffix = Number(rawEnd)
    if (!Number.isFinite(suffix) || suffix <= 0) {
      return null
    }
    start = Math.max(0, size - suffix)
    end = size - 1
  } else {
    start = Number(rawStart)
    end = rawEnd === '' ? size - 1 : Number(rawEnd)
  }

  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end || start >= size) {
    return null
  }
  return { start, end: Math.min(end, size - 1) }
}
