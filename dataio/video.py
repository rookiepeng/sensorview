"""Camera Video Transcoding

Recordings that arrive as something a browser cannot play -- a vendor ``.avi``
straight off a logger -- are transcoded on demand rather than being rejected, so
a log can be dropped in the case folder as it was recorded.

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

from typing import List, Optional

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

