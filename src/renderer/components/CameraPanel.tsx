// The camera panel: a recording, seeked to the frame on the slider.
//
// There is no HTTP server any more, so the `<video>` element's source is the
// custom `sv://` protocol, which serves a file with Range support -- the one
// behaviour Flask's `send_file(conditional=True)` was there for. A browser
// will not scrub a video it cannot range-request.
//
// React does not own `currentTime`. Setting it through a prop would make every
// seek a render, and a render mid-seek resets the element; the effect writes
// to the element directly and the component re-renders only when the log or
// the stream list changes.

import { useEffect, useRef } from 'react'

import { seekSeconds, videoFrameFor } from '@shared/videoFrame'
import type { ImageStream } from '@shared/types'

export interface CameraPanelProps {
  streams: ImageStream[]
  /** Slider position within the log. */
  frame: number
  /** How many frames the log has. */
  frameCount: number
  /** Seconds to shift the clip by, from the manifest. */
  offset?: number
}

export function CameraPanel({ streams, frame, frameCount, offset = 0 }: CameraPanelProps) {
  return (
    <div className="sv-video-grid">
      {streams.map((stream) => (
        <Clip
          key={stream.id}
          stream={stream}
          frame={frame}
          frameCount={frameCount}
          offset={offset}
        />
      ))}
    </div>
  )
}

function Clip({
  stream,
  frame,
  frameCount,
  offset
}: {
  stream: ImageStream
  frame: number
  frameCount: number
  offset: number
}) {
  const video = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const element = video.current
    if (!element) {
      return
    }

    // Both counts are measured, never declared: the log's from the table and
    // the recording's by demuxing, so no manifest can drift against either.
    // `duration` is the element's own, for the same reason.
    const total = stream.frames ?? 0
    if (total <= 0 || !Number.isFinite(element.duration)) {
      return
    }

    const videoFrame = videoFrameFor(frame, frameCount, total)
    const seconds = seekSeconds(videoFrame, element.duration, total, offset)
    // A seek to where it already is still costs a decode, and scrubbing a
    // slider lands on the same video frame for several positions when a log
    // has more frames than its recording.
    if (Math.abs(element.currentTime - seconds) > 1e-4) {
      element.currentTime = seconds
    }
  }, [stream.frames, frame, frameCount, offset])

  return (
    <div className="sv-video-cell">
      <video
        ref={video}
        className="sv-video"
        // Muted and without controls: it is a frame viewer driven by the
        // transport, not a player. `preload` has to be more than metadata or
        // the first seek has nothing to seek within.
        src={window.sensorview.mediaUrl(stream.file)}
        muted
        playsInline
        preload="auto"
        onLoadedMetadata={(event) => {
          // The first frame, before anything has moved the slider.
          const element = event.currentTarget
          const total = stream.frames ?? 0
          if (total > 0 && Number.isFinite(element.duration)) {
            element.currentTime = seekSeconds(
              videoFrameFor(frame, frameCount, total),
              element.duration,
              total,
              offset
            )
          }
        }}
      />
      <span className="sv-video-label">{stream.label}</span>
    </div>
  )
}
