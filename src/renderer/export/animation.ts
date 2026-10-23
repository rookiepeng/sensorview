// Recording the scene across a log's frames.
//
// The Dash export built a Plotly 3D animated figure with every frame's points
// baked into it -- a file that got very large and that only Plotly could
// open. The scene is three.js now and the Plotly 3D path is gone, so the
// honest export is a recording of the view itself: what was on screen, in a
// container anything can play.
//
// `MediaRecorder` over `canvas.captureStream(0)` with an explicit
// `requestFrame()` per step. Zero fps means the stream captures nothing on
// its own, so the recording advances exactly one frame per data frame however
// long the frame took to build -- a rate-driven capture would duplicate slow
// frames and drop fast ones.

export interface RecordOptions {
  /** The scene's canvas. */
  canvas: HTMLCanvasElement
  /** How many frames the log has. */
  frameCount: number
  /** Move the view to a frame and resolve once it has been drawn. */
  show: (frame: number) => Promise<void>
  /** Frames per second in the written file. */
  fps?: number
  /** Called after each frame, for a progress readout. */
  onProgress?: (done: number, total: number) => void
  /** Checked each frame; true stops the recording early. */
  cancelled?: () => boolean
}

export interface Recording {
  /** The encoded video. */
  blob: Blob
  /** The extension matching what the browser actually produced. */
  extension: string
  frames: number
}

/**
 * Pick a container this renderer can actually encode.
 *
 * Chromium gives WebM everywhere and mp4 only sometimes, so the type is asked
 * for rather than assumed -- an unsupported one makes `MediaRecorder` throw at
 * construction, after the user has already chosen where to save.
 */
export function pickMimeType(): { mimeType: string; extension: string } {
  const candidates = [
    { mimeType: 'video/webm;codecs=vp9', extension: 'webm' },
    { mimeType: 'video/webm;codecs=vp8', extension: 'webm' },
    { mimeType: 'video/webm', extension: 'webm' }
  ]
  for (const candidate of candidates) {
    if (MediaRecorder.isTypeSupported(candidate.mimeType)) {
      return candidate
    }
  }
  // Let the browser choose, and call the file what it most likely is.
  return { mimeType: '', extension: 'webm' }
}

/**
 * Walk the log and record the scene.
 *
 * @returns The encoded video, or null when there was nothing to record.
 */
export async function recordScene(options: RecordOptions): Promise<Recording | null> {
  const { canvas, frameCount, show } = options
  if (frameCount <= 0) {
    return null
  }

  const { mimeType, extension } = pickMimeType()
  // Zero fps: nothing is captured until `requestFrame` is called, which is
  // what pins one recorded frame to one data frame.
  const stream = canvas.captureStream(0)
  const track = stream.getVideoTracks()[0] as
    | (MediaStreamTrack & { requestFrame?: () => void })
    | undefined

  const chunks: Blob[] = []
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) {
      chunks.push(event.data)
    }
  }

  const finished = new Promise<void>((resolve) => {
    recorder.onstop = () => resolve()
  })

  // The timeslice is what makes the recorder emit anything at all for a
  // stream that produces frames on demand.
  recorder.start(100)

  const interval = 1000 / (options.fps ?? 10)
  let recorded = 0
  try {
    for (let frame = 0; frame < frameCount; frame++) {
      if (options.cancelled?.()) {
        break
      }
      await show(frame)
      track?.requestFrame?.()
      recorded++
      options.onProgress?.(recorded, frameCount)
      // Hold each frame on screen for its share of the timeline. Without
      // this the recorder writes every frame at the same timestamp and the
      // result plays as a single flash.
      await new Promise((resolve) => setTimeout(resolve, interval))
    }
  } finally {
    recorder.stop()
    stream.getTracks().forEach((item) => item.stop())
  }

  await finished
  if (chunks.length === 0) {
    return null
  }
  return {
    blob: new Blob(chunks, { type: mimeType || 'video/webm' }),
    extension,
    frames: recorded
  }
}

/** A Blob as base64, which is how bytes cross to main. */
export async function toBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  // Chunked: `String.fromCharCode(...bytes)` on a multi-megabyte array blows
  // the argument limit, which it does only once the recording gets long.
  let binary = ''
  const chunk = 0x8000
  for (let at = 0; at < bytes.length; at += chunk) {
    binary += String.fromCharCode(...bytes.subarray(at, at + chunk))
  }
  return btoa(binary)
}
