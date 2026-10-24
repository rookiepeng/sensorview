// Combining logs: who owns a slider position, and what frame that is.
//
// The failure is silent: the
// wrong owner shows the wrong log's camera, and the wrong `localStart` seeks
// every frame after the first gap to the wrong moment, with a picture that
// still looks plausible either way.

import { describe, expect, it } from 'vitest'

import { buildFrameOwners, localFrameFor, positionsOf, stemRuns } from '../src/shared/logs'
import { videoFrameFor } from '../src/shared/videoFrame'

/** Two logs numbering frames 0-2, both claiming every id. */
const SHARED = { '0': ['other', 'main'], '1': ['other', 'main'], '2': ['other', 'main'] }

describe('buildFrameOwners', () => {
  describe('the primary leads', () => {
    it('on a shared frame, keeping both logs', () => {
      // The head of each set is what everything keyed on one owner reads.
      const { ownerSets, frameStems } = buildFrameOwners([0, 1, 2], SHARED, 'main')
      expect(ownerSets).toEqual([
        ['main', 'other'],
        ['main', 'other'],
        ['main', 'other']
      ])
      expect(frameStems).toEqual(['main', 'main', 'main'])
    })

    it('leads wherever the scan put it', () => {
      const owners = { '0': ['main', 'b', 'c'], '1': ['b', 'main', 'c'] }
      const { ownerSets } = buildFrameOwners([0, 1], owners, 'main')
      expect(ownerSets).toEqual([
        ['main', 'b', 'c'],
        ['main', 'b', 'c']
      ])
    })
  })

  describe('frames the primary does not own', () => {
    it('leaves another log’s own order alone', () => {
      const owners = { '0': ['main'], '1': ['other'], '2': ['other', 'third'] }
      const { ownerSets, frameStems } = buildFrameOwners([0, 1, 2], owners, 'main')
      expect(ownerSets).toEqual([['main'], ['other'], ['other', 'third']])
      expect(frameStems).toEqual(['main', 'other', 'other'])
    })

    it('falls back to the primary for a frame nothing claims', () => {
      // A frame in the loaded table that no scanned file claims: better the
      // primary's sidecars than none at all.
      const { ownerSets, frameStems } = buildFrameOwners([7], {}, 'main')
      expect(ownerSets).toEqual([['main']])
      expect(frameStems).toEqual(['main'])
    })
  })

  it('names the primary throughout for a single log', () => {
    const { ownerSets, frameStems } = buildFrameOwners([0, 1, 2], null, 'main')
    expect(ownerSets).toEqual([['main'], ['main'], ['main']])
    expect(frameStems).toEqual(['main', 'main', 'main'])
  })

  it('matches a typed array of ids against the string-keyed map', () => {
    // Ids reach this as numbers from the table and as strings from the scan.
    const { ownerSets } = buildFrameOwners(
      Float64Array.from([0, 1]),
      { '0': ['other', 'main'], '1': ['main'] },
      'main'
    )
    expect(ownerSets).toEqual([['main', 'other'], ['main']])
  })
})

describe('stemRuns', () => {
  const run = (start: number, count: number, localStart: number) => ({ start, count, localStart })

  it.each([
    ['nothing for an empty log', [], []],
    ['one run for an unbroken stretch', [0, 1, 2, 3], [run(0, 4, 0)]],
    ['the offset of a stretch starting partway', [5, 6, 7], [run(5, 3, 0)]],
    ['a new run at a gap', [0, 1, 4, 5], [run(0, 2, 0), run(4, 2, 2)]],
    // Every other position: the log's own frames are still 0, 1, 2.
    ['one run per frame when interleaved', [0, 2, 4], [run(0, 1, 0), run(2, 1, 1), run(4, 1, 2)]]
  ])('has %s', (_, positions, expected) => {
    expect(stemRuns(positions)).toEqual(expected)
  })

  it('numbers local frames end to end across gaps, and nothing between', () => {
    const positions = [0, 1, 5, 6, 7, 20]
    const runs = stemRuns(positions)
    expect(positions.map((p) => localFrameFor(runs, p))).toEqual([0, 1, 2, 3, 4, 5])
    expect(localFrameFor(runs, 3)).toBeNull()
  })

  it('spans an interleaved log’s whole recording', () => {
    // This log owns five of ten positions; they must cover its 30-frame clip.
    const positions = [0, 2, 4, 6, 8]
    const runs = stemRuns(positions)
    const mapped = positions.map((p) => videoFrameFor(localFrameFor(runs, p)!, 5, 30))
    expect([mapped[0], mapped.at(-1)]).toEqual([0, 29])
    expect(mapped).toEqual([...mapped].sort((a, b) => a - b))
  })
})

describe('positionsOf', () => {
  it('finds every position a log recorded, not only the ones it leads', () => {
    // A log sharing every id with the primary still has a video of its own.
    const { ownerSets } = buildFrameOwners([0, 1, 2], SHARED, 'main')
    expect(positionsOf(ownerSets, 'other')).toEqual([0, 1, 2])
    expect(positionsOf(ownerSets, 'main')).toEqual([0, 1, 2])
  })

  it('finds nothing for a log that is not loaded', () => {
    const { ownerSets } = buildFrameOwners([0, 1], null, 'main')
    expect(positionsOf(ownerSets, 'absent')).toEqual([])
  })
})
