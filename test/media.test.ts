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
  it.each([
    // Inclusive: `bytes=0-99` is 100 bytes, and Content-Length comes from it.
    ['bytes=0-99', 0, 99],
    ['bytes=500-', 500, 999],
    // How a player finds the trailing moov atom of a non-faststart mp4.
    ['bytes=-64', 936, 999],
    ['bytes=-5000', 0, 999],
    ['bytes=900-5000', 900, 999],
    ['  bytes=10-20 ', 10, 20]
  ])('reads %j as %i-%i', (header, start, end) => {
    expect(parseByteRange(header, SIZE)).toEqual({ start, end })
  })

  it.each([
    'bytes=1000-',
    'bytes=1500-1600',
    'bytes=200-100',
    'bytes=-0',
    'bytes=-',
    'bytes=abc-def',
    'items=0-99',
    'bytes=0-99, 200-299',
    ''
  ])('refuses %j', (header) => {
    expect(parseByteRange(header, SIZE)).toBeNull()
  })

  it('refuses any range on an empty file', () => {
    expect(parseByteRange('bytes=0-', 0)).toBeNull()
  })
})

describe('mediaUrl', () => {
  it.each([
    resolve('data/NuScenes/scene_0061.mp4'),
    // A colon, a backslash and a space all mean something to a URL parser.
    'C:\\Users\\someone\\My Döcs\\case 01\\log.mp4',
    // A standard-scheme URL lowercases its host, so the path is not put there.
    '/Data/NuScenes/Scene_0061.MP4'
  ])('round-trips %s', (path) => {
    expect(decodeMediaUrl(mediaUrl(path))).toBe(path)
  })

  it.each(['https://example.com/x', 'sv://other/abc', 'sv://media/', 'not a url'])(
    'refuses %s',
    (url) => {
      expect(decodeMediaUrl(url)).toBeNull()
    }
  )
})

describe('withinRoots', () => {
  const root = resolve('/data/case')
  const other = resolve('/elsewhere/case')

  it.each([
    ['the root itself', root, [root], true],
    ['a file in a subdirectory', resolve(root, 'sub', 'log.mp4'), [root], true],
    ['a file under any of several roots', resolve(other, 'log.mp4'), [root, other], true],
    // The reason the separator is part of the test.
    ['a sibling whose name starts the same', resolve('/data/case-evil/log.mp4'), [root], false],
    ['a path that climbs out', resolve(root, '..', 'secrets.txt'), [root], false],
    ['an unnormalised path that climbs out', `${root}${sep}..${sep}secrets.txt`, [root], false],
    ['anything when nothing is open', resolve(root, 'log.mp4'), [], false]
  ])('%s -> %s', (_, path, roots, expected) => {
    expect(withinRoots(path, roots)).toBe(expected)
  })
})

describe('mimeFor', () => {
  it.each([
    ['CLIP.MP4', 'video/mp4'],
    ['still.png', 'image/png'],
    ['photo.jpeg', 'image/jpeg'],
    ['data.parquet', 'application/octet-stream'],
    ['noextension', 'application/octet-stream']
  ])('maps %s', (path, type) => {
    expect(mimeFor(path)).toBe(type)
  })
})
