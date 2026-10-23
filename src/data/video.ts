// Camera recordings: counting their frames, and making them playable.
//
// Ports `dataio/video.py`, minus `extract_frames`, which exists only for the
// standalone HTML export and arrives with it.
//
// The camera panel is a `<video>` element seeked by `currentTime`, so the
// encoder settings are a correctness concern rather than a size one: a browser
// can only seek to a keyframe, and the frame slider jumps to arbitrary frames.
// All-intra keeps every seek frame-exact, which is the right trade for
// recordings of this length.
//
// ffmpeg comes from `ffmpeg-static` rather than from PATH. The Dash app had to
// accept either, because a user's Python environment is theirs; a packaged
// Electron app ships its own, and a recording that plays on one machine and
// not another is not a failure worth keeping.

import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { createHash } from 'node:crypto'
import { promises as fs } from 'node:fs'
import { basename, dirname, extname, join, resolve } from 'node:path'
import { tmpdir } from 'node:os'

/** Containers a browser can play directly. Anything else is transcoded. */
export const BROWSER_PLAYABLE = ['.mp4', '.m4v', '.webm', '.ogv']

/** A framecrc header line. Every other non-empty line is one packet. */
const FRAMECRC_HEADER = '#'

/**
 * Counting only demuxes, so it is quick even for a long recording. The cap is
 * there so a damaged file cannot wedge the caller.
 */
const PROBE_TIMEOUT = 120_000

export class VideoEncodeError extends Error {}

/**
 * Whether a file can go to a browser untouched.
 *
 * Judged by extension rather than by probing: the check decides whether to
 * spend seconds transcoding, and the container a browser understands is
 * exactly what the extension names.
 */
export function isBrowserPlayable(path: string): boolean {
  return BROWSER_PLAYABLE.includes(extname(path).toLowerCase())
}

let ffmpegPath: string | null | undefined

/**
 * Locate the bundled ffmpeg.
 *
 * `ffmpeg-static` resolves to a path inside the app bundle, which in a
 * packaged build is inside `app.asar` -- where it is not a real file and
 * cannot be executed. electron-builder unpacks it beside the archive, so the
 * path has to be rewritten to match. This is the failure that works in `dev`
 * and only shows up once packaged, which is why it is done here rather than
 * trusted to be unnecessary.
 */
export function findFfmpeg(): string | null {
  if (ffmpegPath !== undefined) {
    return ffmpegPath
  }
  try {
    const required = createRequire(import.meta.url)('ffmpeg-static')
    const path: string | null = typeof required === 'string' ? required : required?.default
    ffmpegPath = path ? path.replace('app.asar', 'app.asar.unpacked') : null
  } catch {
    ffmpegPath = null
  }
  return ffmpegPath
}

interface Run {
  code: number | null
  stdout: string
  stderr: string
}

/**
 * Run ffmpeg and collect its output.
 *
 * @param args Arguments, without the executable.
 * @param timeout Milliseconds before the child is killed; 0 waits forever,
 *     which is what a transcode wants.
 */
async function run(args: string[], timeout = 0): Promise<Run> {
  const ffmpeg = findFfmpeg()
  if (!ffmpeg) {
    throw new VideoEncodeError('no ffmpeg available')
  }

  return new Promise((done, fail) => {
    const child = spawn(ffmpeg, args, { stdio: ['ignore', 'pipe', 'pipe'] })
    const out: Buffer[] = []
    const err: Buffer[] = []
    let timer: NodeJS.Timeout | null = null

    if (timeout > 0) {
      timer = setTimeout(() => child.kill(), timeout)
    }

    child.stdout.on('data', (chunk: Buffer) => out.push(chunk))
    child.stderr.on('data', (chunk: Buffer) => err.push(chunk))
    child.on('error', (problem) => {
      if (timer) clearTimeout(timer)
      fail(problem)
    })
    child.on('close', (code) => {
      if (timer) clearTimeout(timer)
      done({
        code,
        stdout: Buffer.concat(out).toString('utf8'),
        stderr: Buffer.concat(err).toString('utf8')
      })
    })
  })
}

/**
 * Count the packet lines in a `framecrc` dump.
 *
 * Split out from `probeFrameCount` so the parsing can be tested against
 * captured ffmpeg output without an ffmpeg to run.
 *
 * Counted by scanning rather than by splitting: a long recording is one line
 * per frame, and building an array of a few hundred thousand strings to
 * measure its length wastes the memory the caller is already holding the dump
 * in.
 *
 * @param output The muxer's stdout. Header lines start with `#`.
 * @returns Number of packet lines.
 */
export function countPacketLines(output: string): number {
  if (!output) {
    return 0
  }

  let total = 0
  let headers = 0
  for (let at = 0; at < output.length; at++) {
    if (output[at] === '\n') {
      total++
      if (output[at + 1] === FRAMECRC_HEADER) {
        headers++
      }
    }
  }
  if (output.startsWith(FRAMECRC_HEADER)) {
    headers++
  }
  // A final line the muxer did not terminate still counts as a packet.
  if (!output.endsWith('\n')) {
    total++
  }
  return Math.max(0, total - headers)
}

/**
 * Count the video frames in a recording.
 *
 * Counted by demuxing with `-c copy` rather than decoding: one packet per
 * frame is all that is needed, so this costs milliseconds on a clip that would
 * take seconds to decode. Container metadata is not trusted instead -- AVI and
 * Matroska routinely declare no frame count at all.
 *
 * The packets go through the `framecrc` muxer rather than being read off
 * ffmpeg's own `frame=` progress counter. That counter is kept by the
 * *encoder*, so from ffmpeg 7 a stream copy reports nothing at all, and the
 * probe silently returned null for every file -- leaving the camera panel
 * stuck on frame 0.
 *
 * @returns Frame count, or null when it cannot be read.
 */
export async function probeFrameCount(path: string): Promise<number | null> {
  if (!findFfmpeg() || !(await exists(path))) {
    return null
  }

  let result: Run
  try {
    result = await run(
      // Nothing parses stderr, so the chatter is turned off rather than
      // captured: a per-packet dump is quite enough output already.
      ['-hide_banner', '-nostats', '-loglevel', 'error']
        .concat(['-i', path, '-map', '0:v:0', '-c', 'copy', '-f', 'framecrc', '-']),
      PROBE_TIMEOUT
    )
  } catch {
    return null
  }

  if (result.code !== 0) {
    return null
  }
  return countPacketLines(result.stdout) || null
}

/** Encoder arguments shared by every mp4 this module writes. */
function allIntraArgs(keyframeInterval: number, crf: number): string[] {
  const gap = String(Math.max(1, keyframeInterval))
  return [
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    // Short GOP plus no scene-cut insertion keeps keyframe placement
    // deterministic, which is what makes a currentTime seek land on the
    // intended frame.
    '-g', gap,
    '-keyint_min', gap,
    '-sc_threshold', '0',
    '-crf', String(crf),
    // yuv420p requires even dimensions; pad by at most a pixel rather than
    // failing on an odd-sized source.
    '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
    '-movflags', '+faststart'
  ]
}

/**
 * Transcode a recording into the all-intra mp4 the camera panel plays.
 *
 * Written to a temporary file beside the destination and moved into place, so
 * a reader sees either no file or a complete one -- two readers racing to warm
 * the same cache entry cannot serve a half-written clip.
 *
 * @throws VideoEncodeError when ffmpeg is unavailable or the encode fails.
 */
export async function transcodeToMp4(
  source: string,
  outPath: string,
  keyframeInterval = 1,
  crf = 20
): Promise<string> {
  if (!(await exists(source))) {
    throw new VideoEncodeError(`no such file: ${source}`)
  }
  if (!findFfmpeg()) {
    throw new VideoEncodeError('no ffmpeg available')
  }

  const outDir = dirname(resolve(outPath))
  await fs.mkdir(outDir, { recursive: true })
  const staging = join(outDir, `.${createHash('sha1').update(outPath).digest('hex').slice(0, 12)}.part.mp4`)

  try {
    const result = await run(
      ['-y', '-loglevel', 'error', '-i', source, '-map', '0:v:0', '-an', '-sn']
        .concat(allIntraArgs(keyframeInterval, crf))
        .concat([staging])
    )
    if (result.code === 0 && (await size(staging)) > 0) {
      await fs.rename(staging, outPath)
      return outPath
    }
    throw new VideoEncodeError(`ffmpeg could not transcode ${source}: ${result.stderr.trim()}`)
  } finally {
    await fs.rm(staging, { force: true })
  }
}

/** Where transcodes are kept. Never the case folder, which is input only. */
export function videoCacheDir(): string {
  return join(tmpdir(), 'sensorview-video')
}

/**
 * Resolve a recording to a file the browser can actually play.
 *
 * A recorder's own container is served untouched when browsers understand it;
 * anything else is transcoded once into the cache and served from there. The
 * case folder is read-only input, so nothing is written back beside the user's
 * data.
 *
 * The cache name carries the source's size and mtime, so replacing a log's
 * recording invalidates its transcode without anyone clearing anything.
 *
 * @returns An absolute path, or null when the source is missing or cannot be
 *     made playable.
 */
export async function playableFile(source: string): Promise<string | null> {
  if (!source || !(await exists(source))) {
    return null
  }
  if (isBrowserPlayable(source)) {
    return resolve(source)
  }

  let stat
  try {
    stat = await fs.stat(source)
  } catch {
    return null
  }

  const fingerprint = createHash('sha1')
    .update(`${resolve(source)}|${stat.size}|${Math.floor(stat.mtimeMs / 1000)}`)
    .digest('hex')
    .slice(0, 16)
  const stem = basename(source, extname(source))
  const cached = join(videoCacheDir(), `${stem}.${fingerprint}.mp4`)

  if ((await size(cached)) > 0) {
    return cached
  }

  try {
    return await transcodeToMp4(source, cached)
  } catch {
    return null
  }
}

const counts = new Map<string, number | null>()

/**
 * Frame count of a recording, memoized per file revision.
 *
 * Read off the *source* rather than a transcoded copy: the transcode is
 * frame-for-frame, and probing the source avoids forcing one to happen just to
 * answer this.
 */
export async function streamFrameCount(source: string): Promise<number | null> {
  let stat
  try {
    stat = await fs.stat(source)
  } catch {
    return null
  }

  const key = `${resolve(source)}|${stat.size}|${Math.floor(stat.mtimeMs / 1000)}`
  if (!counts.has(key)) {
    counts.set(key, await probeFrameCount(source))
  }
  return counts.get(key) ?? null
}

async function exists(path: string): Promise<boolean> {
  try {
    await fs.access(path)
    return true
  } catch {
    return false
  }
}

async function size(path: string): Promise<number> {
  try {
    return (await fs.stat(path)).size
  } catch {
    return 0
  }
}
