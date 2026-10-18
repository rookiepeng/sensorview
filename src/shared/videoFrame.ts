// Mapping a data frame onto a frame of its recording.
//
// This formula used to exist twice, in two languages: once in Python for the
// export and once as a JavaScript string inside a Dash clientside callback for
// the camera panel, with nothing mechanical keeping the pair in step. The
// Python version carried a comment explaining that it rounds halves *up*,
// the way `Math.round` does, rather than to even the way Python's `round`
// does -- because an exported still has to be the picture the panel was
// showing at that slider position, not its neighbour.
//
// There is one language now, so that hazard is gone. The tests came across
// anyway: the half-up rule is still load-bearing, and it is still the thing a
// well-meaning rewrite would quietly change.
//
// Neither count is declared. The data frame count comes from the table and the
// video frame count is measured by demuxing, so a manifest cannot drift
// against either.

/**
 * Map one of a log's frames onto a frame of its recording.
 *
 * @param local 0-based ordinal of the frame within the log's own frames.
 * @param localTotal How many frames that log owns.
 * @param videoFrames Frame count of its recording.
 * @returns 0-based video frame index.
 */
export function videoFrameFor(local: number, localTotal: number, videoFrames: number): number {
  // A single-frame log would divide by zero; substituting 1 makes it map to
  // the first video frame rather than raising.
  const span = localTotal > 1 ? localTotal - 1 : 1
  const ratio = Math.min(1, Math.max(0, local / span))
  // `Math.floor(x + 0.5)`, not `Math.round`: they agree for positive values,
  // and the intent -- halves up -- is then on the page rather than in a
  // reader's memory of which way each language breaks a tie.
  return Math.floor(ratio * (videoFrames - 1) + 0.5)
}

/**
 * Where to seek, in seconds, to land in the middle of a video frame.
 *
 * The middle rather than the boundary: seeking exactly to a frame's start is
 * ambiguous between it and its predecessor once a container's timestamps have
 * any rounding in them, and half a frame of slack costs nothing.
 *
 * @param videoFrame 0-based video frame index.
 * @param duration Clip duration in seconds.
 * @param videoFrames Total frames in the clip.
 * @param offset Seconds to shift the whole clip by, from the manifest.
 */
export function seekSeconds(
  videoFrame: number,
  duration: number,
  videoFrames: number,
  offset = 0
): number {
  if (!Number.isFinite(duration) || videoFrames <= 0) {
    return Math.max(0, offset)
  }
  const seconds = ((videoFrame + 0.5) * duration) / videoFrames
  return Math.max(0, seconds + offset)
}
