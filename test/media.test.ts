// Range parsing and path containment for the `sv://` scheme.
//
// Two reasons these are worth unit tests rather than leaving to the Electron
// smoke check: an off-by-one in a byte range shows up as a video that stutters
// on seek rather than one that fails, and a missing separator check in the
// path test is a directory traversal that nothing visible would reveal.

import { resolve, sep } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  decodeMediaUrl,
  mediaUrl,
  mimeFor,
  parseByteRange,
  withinRoots
} from '../src/shared/media'

const SIZE = 1000

describe('parseByteRange', () => {
  it('reads an explicit range inclusively', () => {
    // `bytes=0-99` is 100 bytes, not 99. Content-Length is computed from this.
    expect(parseByteRange('bytes=0-99', SIZE)).toEqual({ start: 0, end: 99 })
  })

  it('reads an open-ended range to the last byte', () => {
    expect(parseByteRange('bytes=500-', SIZE)).toEqual({ start: 500, end: 999 })
  })

  it('reads a suffix range from the end', () => {
    // What a player sends to find the trailing moov atom of an mp4 written
    // without +faststart.
    expect(parseByteRange('bytes=-64', SIZE)).toEqual({ start: 936, end: 999 })
  })

  it('clamps a suffix longer than the file to the whole file', () => {
    expect(parseByteRange('bytes=-5000', SIZE)).toEqual({ start: 0, end: 999 })
  })

  it('clamps an end past the last byte', () => {
    expect(parseByteRange('bytes=900-5000', SIZE)).toEqual({ start: 900, end: 999 })
  })

  it('tolerates surrounding whitespace', () => {
    expect(parseByteRange('  bytes=10-20 ', SIZE)).toEqual({ start: 10, end: 20 })
  })

  it.each([
    ['bytes=1000-', 'starts at the length'],
    ['bytes=1500-1600', 'starts past the end'],
    ['bytes=200-100', 'end before start'],
    ['bytes=-0', 'zero-length suffix'],
    ['bytes=-', 'no bounds at all'],
    ['bytes=abc-def', 'not numbers'],
    ['items=0-99', 'wrong unit'],
    ['bytes=0-99, 200-299', 'multipart'],
    ['', 'empty']
  ])('refuses %s (%s)', (header) => {
    expect(parseByteRange(header, SIZE)).toBeNull()
  })

  it('refuses any range on an empty file', () => {
    expect(parseByteRange('bytes=0-', 0)).toBeNull()
  })
})

describe('mediaUrl', () => {
  it('round-trips a path', () => {
    const path = resolve('data/NuScenes/scene_0061.mp4')
    expect(decodeMediaUrl(mediaUrl(path))).toBe(path)
  })

  it('round-trips a path with a drive letter, spaces and non-ASCII', () => {
    // The reason the path is encoded rather than written into the URL: a
    // colon, a backslash and a space all mean something to a URL parser.
    const path = 'C:\\Users\\someone\\My Döcs\\case 01\\log.mp4'
    expect(decodeMediaUrl(mediaUrl(path))).toBe(path)
  })

  it('preserves case', () => {
    // A standard-scheme URL lowercases its host, which is why the path is not
    // put there.
    const path = '/Data/NuScenes/Scene_0061.MP4'
    expect(decodeMediaUrl(mediaUrl(path))).toBe(path)
  })

  it.each([
    ['https://example.com/x', 'another scheme'],
    ['sv://other/abc', 'another host'],
    ['sv://media/', 'no payload'],
    ['not a url', 'not a URL at all']
  ])('refuses %s (%s)', (url) => {
    expect(decodeMediaUrl(url)).toBeNull()
  })
})

describe('withinRoots', () => {
  const root = resolve('/data/case')

  it('accepts the root itself', () => {
    expect(withinRoots(root, [root])).toBe(true)
  })

  it('accepts a file inside it', () => {
    expect(withinRoots(resolve(root, 'log.mp4'), [root])).toBe(true)
  })

  it('accepts a file in a subdirectory', () => {
    expect(withinRoots(resolve(root, 'sub', 'log.mp4'), [root])).toBe(true)
  })

  it('rejects a sibling whose name starts the same way', () => {
    // The whole reason the separator is part of the test.
    expect(withinRoots(resolve('/data/case-evil/log.mp4'), [root])).toBe(false)
  })

  it('rejects a path that climbs out', () => {
    expect(withinRoots(resolve(root, '..', 'secrets.txt'), [root])).toBe(false)
  })

  it('rejects an unnormalised path that climbs out', () => {
    expect(withinRoots(`${root}${sep}..${sep}secrets.txt`, [root])).toBe(false)
  })

  it('rejects everything when nothing has been opened', () => {
    expect(withinRoots(resolve(root, 'log.mp4'), [])).toBe(false)
  })

  it('accepts a file under any of several roots', () => {
    const other = resolve('/elsewhere/case')
    expect(withinRoots(resolve(other, 'log.mp4'), [root, other])).toBe(true)
  })
})

describe('mimeFor', () => {
  it.each([
    ['clip.mp4', 'video/mp4'],
    ['CLIP.MP4', 'video/mp4'],
    ['still.png', 'image/png'],
    ['photo.jpeg', 'image/jpeg']
  ])('maps %s', (path, type) => {
    expect(mimeFor(path)).toBe(type)
  })

  it.each([['data.parquet'], ['noextension']])('falls back for %s', (path) => {
    expect(mimeFor(path)).toBe('application/octet-stream')
  })
})
