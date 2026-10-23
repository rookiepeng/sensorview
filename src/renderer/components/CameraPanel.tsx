// The camera panel: each log's recording, seeked to this frame.
//
// There is no HTTP server any more, so the `<video>` element's source is the
// custom `sv://` protocol, which serves a file with Range support -- the one
// behaviour Flask's `send_file(conditional=True)` was there for. A browser
// will not scrub a video it cannot range-request.
//
// React does not own `currentTime`. Setting it through a prop would make every
// seek a render, and a render mid-seek resets the element; the effect writes
// to the element directly and the component re-renders only when the clip list
// changes.
//
// The frame a clip is seeked to is the log's **own** frame number, not the
// slider position. With logs combined those differ, and a log whose frames are
// interleaved with another's would otherwise be seeked by a position it does
// not own -- silently, with a picture that still looks plausible.

import { useEffect, useRef } from 'react'

import { seekSeconds, videoFrameFor } from '@shared/videoFrame'
import type { ImageStream } from '@shared/types'

/** One picture to draw: a recording, and where in it this frame is. */
export interface ClipSource {
  key: string
  label: string
  stream: ImageStream
  /** This frame as the log's own frame number. */
  local: number
  /** How many frames that log owns. */
  localTotal: number
}

export interface CameraPanelProps {
  clips: ClipSource[]
  /** Seconds to shift every clip by, from the manifest. */
  offset?: number
}

export function CameraPanel({ clips, offset = 0 }: CameraPanelProps) {
  return (
    <div className="sv-video-grid">
      {clips.map((clip) => (
        <Clip key={clip.key} clip={clip} offset={offset} />
      ))}
    </div>
  )
}

function Clip({ clip, offset }: { clip: ClipSource; offset: number }) {
  const video = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const element = video.current
    if (!element) {
      return
    }

    // Every count is measured, never declared: the log's from the table, the
    // recording's by demuxing, the duration from the element itself. No
    // manifest can drift against any of them.
    const total = clip.stream.frames ?? 0
    if (total <= 0 || !Number.isFinite(element.duration)) {
      return
    }

    const videoFrame = videoFrameFor(clip.local, clip.localTotal, total)
    const seconds = seekSeconds(videoFrame, element.duration, total, offset)
    // A seek to where it already is still costs a decode, and scrubbing
    // lands on the same video frame for several positions when a log has
    // more frames than its recording.
    if (Math.abs(element.currentTime - seconds) > 1e-4) {
      element.currentTime = seconds
    }
  }, [clip.stream.frames, clip.local, clip.localTotal, offset])

  return (
    <div className="sv-video-cell">
      <video
        ref={video}
        className="sv-video"
        data-stem={clip.key}
        // Muted and without controls: it is a frame viewer driven by the
        // transport, not a player. `preload` has to be more than metadata or
        // the first seek has nothing to seek within.
        src={window.sensorview.mediaUrl(clip.stream.file)}
        muted
        playsInline
        preload="auto"
        onLoadedMetadata={(event) => {
          // The first frame, before anything has moved the slider.
          const element = event.currentTarget
          const total = clip.stream.frames ?? 0
          if (total > 0 && Number.isFinite(element.duration)) {
            element.currentTime = seekSeconds(
              videoFrameFor(clip.local, clip.localTotal, total),
              element.duration,
              total,
              offset
            )
          }
        }}
      />
      <span className="sv-video-label">{clip.label}</span>
    </div>
  )
}
