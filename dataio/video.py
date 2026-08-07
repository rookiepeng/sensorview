"""Camera Video Transcoding and Frame Extraction

Recordings that arrive as something a browser cannot play -- a vendor ``.avi``
straight off a logger -- are transcoded on demand rather than being rejected, so
a log can be dropped in the case folder as it was recorded.

Individual frames are also pulled out of a recording here, for the standalone
HTML export: that file has to carry its pictures inside it, so there is nothing
left for a ``<video>`` element to seek (see :func:`extract_frames`).

The camera panel is a browser ``<video>`` element seeked by ``currentTime``, so
the encoder settings matter for correctness, not just size: browsers can only
seek to a keyframe, and the frame slider jumps to arbitrary frames. Encoding
all-intra (``keyframe_interval=1``) keeps every seek frame-exact at the cost of
a larger file, which is the right trade for recordings of this length.

Uses the static ffmpeg binary bundled with ``imageio-ffmpeg`` when present, and
falls back to an ``ffmpeg`` on PATH.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Dict, Iterable, List, Optional

import glob
import os
import re
import shutil
import subprocess
import tempfile

# Containers a browser's <video> element can play directly. Anything else has
# to be transcoded before it reaches the client.
BROWSER_PLAYABLE_EXTENSIONS = (".mp4", ".m4v", ".webm", ".ogv")

# ffmpeg's progress line, e.g. "frame=  246 fps=0.0 q=-1.0 Lsize=N/A ...".
_FRAME_STAT = re.compile(r"frame=\s*(\d+)")

# Counting frames only demuxes, so it is quick even for a long recording. The
# cap is there so a damaged file cannot wedge the callback that asks for it.
_PROBE_TIMEOUT = 120.0

# Extraction decodes, so it is slower than a probe, but it still runs once per
# export rather than per frame.
_EXTRACT_TIMEOUT = 900.0

# Most frames one extraction will ask for. The whole point is to inline the
# pictures in a single HTML file, and a few hundred already makes that file
# large; the cap also keeps the select expression inside the command-line
# length limit.
MAX_EXTRACT_FRAMES = 2000

# A windowed build (PyInstaller ``console=False``) has no console attached, so
# it hands the child an invalid stdin handle and Windows opens a console window
# for it. Absent on other platforms, where the flag is simply zero.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run_ffmpeg(
    command: List[str], timeout: Optional[float] = None
) -> subprocess.CompletedProcess:
    """
    Run an ffmpeg command and capture its output.

    Args:
        command: Full argument list, ffmpeg executable first.
        timeout: Seconds to wait before killing the child. None waits forever,
            which is what a transcode wants; a caller on a request path should
            set one.

    Returns:
        The completed process; callers check ``returncode`` themselves.

    Raises:
        subprocess.TimeoutExpired: If ``timeout`` elapses first.
    """
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
        timeout=timeout,
    )


class VideoEncodeError(Exception):
    """Raised when no ffmpeg is available or the encode fails."""


def is_browser_playable(path: str) -> bool:
    """
    Whether a video file can be handed to a browser as-is.

    Judged by extension rather than by probing: the check gates whether to spend
    seconds transcoding, and a container a browser understands is exactly what
    the extension names.

    Args:
        path: Video file path.

    Returns:
        True when the file needs no transcode.
    """
    return os.path.splitext(path)[1].lower() in BROWSER_PLAYABLE_EXTENSIONS


def find_ffmpeg() -> Optional[str]:
    """
    Locate an ffmpeg executable.

    Returns:
        Path to ffmpeg, preferring the ``imageio-ffmpeg`` bundled static build,
        then any ``ffmpeg`` on PATH. None when neither is available.
    """
    try:
        import imageio_ffmpeg  # noqa: PLC0415  (optional, transcode-time only)

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    return shutil.which("ffmpeg")


def probe_frame_count(path: str) -> Optional[int]:
    """
    Count the video frames in a recording.

    Counted by demuxing with ``-c copy`` rather than decoding: one packet per
    frame is all that is needed, so this costs milliseconds on a clip that would
    take seconds to decode, and works for a codec no decoder is available for.
    Container metadata is not trusted instead -- AVI and Matroska routinely
    declare no frame count at all.

    Args:
        path: Path to any video file.

    Returns:
        Frame count of the file's first video stream, or None when ffmpeg is
        unavailable, the file has no video stream, or the count cannot be read.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg or not os.path.exists(path):
        return None

    try:
        result = _run_ffmpeg(
            [ffmpeg, "-hide_banner", "-i", path]
            + ["-map", "0:v:0", "-c", "copy", "-f", "null", "-"],
            timeout=_PROBE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None

    if result.returncode != 0:
        return None

    # The progress report is written repeatedly as it goes; the final one holds
    # the total. It goes to stderr alongside the stream info.
    matches = _FRAME_STAT.findall(result.stderr or "")
    if not matches:
        return None

    count = int(matches[-1])
    return count or None


def extract_frames(
    source: str,
    frame_indices: Iterable[int],
    out_dir: str,
    max_width: int = 640,
    quality: int = 4,
) -> Dict[int, str]:
    """
    Pull individual frames out of a recording as JPEG files.

    Every requested frame comes out of **one** ffmpeg run: a ``select``
    expression naming each index, rather than one seek-and-grab per frame. A
    hundred-frame export is one decode pass instead of a hundred process
    spawns, which is the difference between seconds and minutes.

    Frames are downscaled by default. The export draws them as a thumbnail in
    the corner of the plot and every one is base64-inlined into a single HTML
    file, so full-resolution stills would multiply that file's size for detail
    nothing renders.

    Args:
        source: Any video ffmpeg can read -- the recording as it sits in the
            case folder, not a browser-playable transcode of it.
        frame_indices: 0-based video frame numbers to extract. Order does not
            matter and duplicates are collapsed.
        out_dir: Directory to write the JPEGs into; created if absent.
        max_width: Width to fit within, preserving aspect. Frames narrower than
            this are left alone rather than upscaled. 0 keeps full resolution.
        quality: ffmpeg ``-q:v`` factor; lower is better quality and larger.

    Returns:
        Mapping of frame index -> written JPEG path, covering as many of the
        requested frames as ffmpeg actually produced. Empty when ffmpeg is
        unavailable, the source is missing, or the run fails -- callers treat
        images as optional decoration, so a failure costs the pictures and not
        the export.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg or not source or not os.path.exists(source):
        return {}

    wanted = sorted({int(index) for index in frame_indices if index is not None})
    wanted = [index for index in wanted if index >= 0][:MAX_EXTRACT_FRAMES]
    if not wanted:
        return {}

    os.makedirs(out_dir, exist_ok=True)

    # Commas inside the expression have to be escaped or the filtergraph parser
    # reads them as the end of the `select` filter.
    selection = "+".join(f"eq(n\\,{index})" for index in wanted)
    filters = f"select={selection}"
    if max_width > 0:
        # -2 keeps the aspect ratio and rounds to an even height; min() means a
        # source narrower than the cap is passed through rather than blown up.
        filters += f",scale='min({max_width},iw)':-2"

    pattern = os.path.join(out_dir, "%06d.jpg")
    try:
        result = _run_ffmpeg(
            [ffmpeg, "-y", "-loglevel", "error", "-i", source]
            + ["-map", "0:v:0", "-an", "-sn", "-vf", filters]
            # Without this ffmpeg re-times the surviving frames to a constant
            # rate, duplicating and dropping to fill the gaps the select left.
            + ["-vsync", "0", "-q:v", str(quality), pattern],
            timeout=_EXTRACT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {}

    if result.returncode != 0:
        return {}

    # Output is numbered over the frames that survived the filter, in ascending
    # source order -- so the n-th file is the n-th requested index. A short run
    # (a requested index past the end of the stream) truncates the tail rather
    # than shifting the mapping.
    produced = sorted(glob.glob(os.path.join(out_dir, "*.jpg")))
    return dict(zip(wanted, produced))


def _x264_all_intra_args(keyframe_interval: int, crf: int) -> List[str]:
    """
    Encoder arguments shared by every mp4 this module writes.

    Args:
        keyframe_interval: GOP length; 1 is all-intra.
        crf: x264 quality factor.

    Returns:
        ffmpeg argument list.
    """
    return [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        # Short GOP + no scene-cut keyframe insertion keeps keyframe placement
        # deterministic, which is what makes currentTime seeks land on the
        # intended frame.
        "-g",
        str(max(1, keyframe_interval)),
        "-keyint_min",
        str(max(1, keyframe_interval)),
        "-sc_threshold",
        "0",
        "-crf",
        str(crf),
        # Even dimensions are required by yuv420p; scale up by at most a pixel
        # rather than failing on odd-sized source frames.
        "-vf",
        "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-movflags",
        "+faststart",
    ]


def transcode_to_mp4(
    source: str,
    out_path: str,
    keyframe_interval: int = 1,
    crf: int = 20,
) -> str:
    """
    Transcode a recording into the all-intra mp4 the camera panel plays.

    Written to a temporary file in the destination directory and moved into
    place, so a reader either sees no file or sees a complete one -- two
    requests racing to warm the same cache entry cannot serve a half-written
    clip.

    Args:
        source: Any video ffmpeg can read.
        out_path: Destination ``.mp4`` path; parent directories are created.
        keyframe_interval: GOP length. 1 means all-intra, keeping every seek
            frame-exact in the browser.
        crf: x264 quality factor; lower is better quality and larger.

    Returns:
        The path written.

    Raises:
        VideoEncodeError: If ffmpeg is unavailable or the transcode fails.
        FileNotFoundError: If ``source`` does not exist.
    """
    if not os.path.exists(source):
        raise FileNotFoundError(source)

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise VideoEncodeError(
            "No ffmpeg available. Install 'imageio-ffmpeg' or put ffmpeg on PATH."
        )

    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)

    handle, staging = tempfile.mkstemp(suffix=".mp4", dir=out_dir)
    os.close(handle)

    try:
        command = (
            [ffmpeg, "-y", "-loglevel", "error", "-i", source]
            + ["-map", "0:v:0", "-an", "-sn"]
            + _x264_all_intra_args(keyframe_interval, crf)
            + [staging]
        )
        result = _run_ffmpeg(command)
        if result.returncode == 0 and os.path.getsize(staging) > 0:
            os.replace(staging, out_path)
            return out_path
    finally:
        if os.path.exists(staging):
            os.remove(staging)

    raise VideoEncodeError(
        f"ffmpeg could not transcode {source}: {result.stderr.strip()}"
    )
