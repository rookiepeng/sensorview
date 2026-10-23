// Combining logs: who owns a slider position, and what frame that is.
//
// Transliterated from `tests/test_frame_owners.py` and
// `tests/test_stem_runs.py`. Both exist because the failure is silent: the
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
    it('keeps both logs on a shared frame', () => {
      const { ownerSets } = buildFrameOwners([0, 1, 2], SHARED, 'main')
      expect(ownerSets).toEqual([
        ['main', 'other'],
        ['main', 'other'],
        ['main', 'other']
      ])
    })

    it('still names the primary in frameStems', () => {
      // The head of each set is what everything keyed on a single owner
      // reads, so this is the guarantee that nothing outside the two panels
      // changed behaviour when a frame gained a second owner.
      const { frameStems } = buildFrameOwners([0, 1, 2], SHARED, 'main')
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
  describe('contiguous', () => {
    it('is one run for an unbroken stretch', () => {
      expect(stemRuns([0, 1, 2, 3])).toEqual([{ start: 0, count: 4, localStart: 0 }])
    })

    it('keeps the offset of a stretch starting partway', () => {
      expect(stemRuns([5, 6, 7])).toEqual([{ start: 5, count: 3, localStart: 0 }])
    })

    it('has no runs for an empty log', () => {
      expect(stemRuns([])).toEqual([])
    })

    it('handles a single position', () => {
      expect(stemRuns([9])).toEqual([{ start: 9, count: 1, localStart: 0 }])
    })
  })

  describe('gaps', () => {
    it('starts a new run at a gap', () => {
      expect(stemRuns([0, 1, 4, 5])).toEqual([
        { start: 0, count: 2, localStart: 0 },
        { start: 4, count: 2, localStart: 2 }
      ])
    })

    it('yields one run per frame for an interleaved log', () => {
      // Every other position: the log's own frames are still 0, 1, 2.
      expect(stemRuns([0, 2, 4])).toEqual([
        { start: 0, count: 1, localStart: 0 },
        { start: 2, count: 1, localStart: 1 },
        { start: 4, count: 1, localStart: 2 }
      ])
    })

    it('numbers local frames end to end across gaps', () => {
      const positions = [0, 1, 5, 6, 7, 20]
      const runs = stemRuns(positions)
      // The whole point of localStart: the log is measured against its own
      // recording, so its frames are 0..n-1 whatever the gaps.
      expect(positions.map((p) => localFrameFor(runs, p))).toEqual([0, 1, 2, 3, 4, 5])
    })

    it('resolves a position the log does not own to nothing', () => {
      expect(localFrameFor(stemRuns([0, 1, 5]), 3)).toBeNull()
    })
  })

  it('spans an interleaved log’s whole recording', () => {
    // Two logs alternating over ten positions; this one owns five, and those
    // five must cover its 30-frame clip from first to last.
    const positions = [0, 2, 4, 6, 8]
    const runs = stemRuns(positions)
    const mapped = positions.map((p) => videoFrameFor(localFrameFor(runs, p)!, 5, 30))
    expect(mapped[0]).toBe(0)
    expect(mapped[mapped.length - 1]).toBe(29)
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
