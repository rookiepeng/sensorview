// Counting a recording's frames without trusting ffmpeg's progress line.
//
// The probe used to
// scrape `frame=` out of stderr. That counter belongs to the *encoder*, so
// from ffmpeg 7 a stream copy stopped reporting one and the probe returned
// nothing for every file on every modern build -- silently, because nothing is
// also what "no ffmpeg" looks like, and every caller treats it as "leave the
// video where it is". The camera panel sat on frame 0.
//
// These run the parser against captured muxer output rather than a live
// ffmpeg, so they say the same thing whatever version the host happens to
// have -- which is the property that was missing when the regression landed.

import { describe, expect, it } from 'vitest'

import { countPacketLines, isBrowserPlayable } from '../src/data/video'

// What `-f framecrc` writes for a three-packet h264 stream. The header block
// is the part that must not be counted.
const FRAMECRC_THREE = `#extradata 0:       46, 0x443c0f73
#software: Lavf61.1.100
#tb 0: 1/15872
#media_type 0: video
#codec_id 0: h264
#dimensions 0: 960x540
#sar 0: 1/1
0,          0,          0,     8000,    43531, 0x203ca0d4
0,       8000,       8000,     8000,    44425, 0x84e0a708
0,      16000,      16000,     8000,    45289, 0x07ac296e
`

describe('countPacketLines', () => {
  it.each([
    ['packets after the header', FRAMECRC_THREE, 3],
    ['an unterminated final line', FRAMECRC_THREE.trimEnd(), 3],
    ['nothing in empty output', '', 0],
    ['nothing in a header alone', FRAMECRC_THREE.split('\n').slice(0, 7).join('\n') + '\n', 0],
    // The rule is "a line starting with #", wherever it sits.
    ['around a header line that is not first', '0,0,0,1,2, 0x1\n#tb 0: 1/90000\n0,1,1,1,2, 0x2\n', 2]
  ])('counts %s', (_, dump, expected) => {
    expect(countPacketLines(dump)).toBe(expected)
  })
})

describe('isBrowserPlayable', () => {
  it.each([
    ['clip.MP4', true],
    ['clip.m4v', true],
    ['clip.webm', true],
    ['clip.ogv', true],
    ['clip.avi', false],
    ['clip.mkv', false],
    ['clip', false]
  ])('%s -> %s', (name, playable) => {
    // By extension, not by probing: the check decides whether to spend seconds
    // transcoding, and the container is exactly what the extension names.
    expect(isBrowserPlayable(name)).toBe(playable)
  })
})
