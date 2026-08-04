"""Camera Video Encoding

The camera panel is a browser ``<video>`` element seeked by ``currentTime``, so
the encoder settings matter for correctness, not just size: browsers can only
seek to a keyframe, and the frame slider jumps to arbitrary frames. Encoding
all-intra (``keyframe_interval=1``) keeps every seek frame-exact at the cost of
a larger file, which is the right trade for recordings of this length.

Recordings that arrive as something a browser cannot play -- a vendor ``.avi``
straight off a logger -- are transcoded to that same all-intra mp4 rather than
being rejected, so a log can be dropped in the case folder as it was recorded.

Uses the static ffmpeg binary bundled with ``imageio-ffmpeg`` when present, and
falls back to an ``ffmpeg`` on PATH.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import List, Optional, Sequence

import os
import shutil
import subprocess
import tempfile

# Containers a browser's <video> element can play directly. Anything else has
# to be transcoded before it reaches the client.
BROWSER_PLAYABLE_EXTENSIONS = (".mp4", ".m4v", ".webm", ".ogv")

# AVI stores a codec fourcc, and ffmpeg maps the ones it knows to a decoder.
# Vendor recorders sometimes stamp their own tag onto a stream that is really a
# standard codec -- ``DJLS`` frames are plain JPEG-LS (each one starts with the
# SOI + SOF55 marker pair) -- which ffmpeg refuses with "no decoder found for:
# none". Naming the decoder explicitly is all that is needed to read them.
FORCED_DECODERS = {
    "DJLS": "jpegls",
    "MJLS": "jpegls",
}

# How much of an AVI header to read when sniffing the stream's fourcc. The
# `hdrl` list is the first thing after the RIFF header, so this is generous.
_HEADER_PROBE_BYTES = 65536


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


def _fourcc(raw: bytes) -> Optional[str]:
    """
    Decode a four-byte codec tag.

    Args:
        raw: Four bytes from an AVI header.

    Returns:
        The tag as text, or None when it is empty or not ASCII (an all-zero
        handler is how AVI spells "unset").
    """
    try:
        return raw.decode("ascii").strip("\x00 ") or None
    except UnicodeDecodeError:
        return None


def avi_video_fourcc(path: str) -> Optional[str]:
    """
    Read the video codec fourcc out of an AVI header.

    Sniffs the header rather than walking the full RIFF tree: the goal is only
    to recognise a tag ffmpeg cannot map, and every stream header sits in the
    first few kilobytes.

    A stream header's ``fccHandler`` is frequently left zeroed, with the real
    tag carried in the following format chunk's ``biCompression``. Both are
    read, format chunk first, because that is the one recorders actually fill
    in.

    Args:
        path: Path to an AVI file.

    Returns:
        The four-character codec tag (e.g. ``"DJLS"``), or None when the file is
        unreadable or declares no video stream.
    """
    try:
        with open(path, "rb") as handle:
            header = handle.read(_HEADER_PROBE_BYTES)
    except OSError:
        return None

    # Each stream is described by a `strh` chunk whose payload opens with the
    # stream type; its `strf` companion follows within the same `strl` list.
    offset = header.find(b"strh")
    while offset != -1:
        payload = offset + 8
        if header[payload : payload + 4] == b"vids":
            strf = header.find(b"strf", payload)
            if strf != -1:
                # BITMAPINFOHEADER.biCompression sits 16 bytes into the payload.
                tag = _fourcc(header[strf + 24 : strf + 28])
                if tag:
                    return tag
            return _fourcc(header[payload + 4 : payload + 8])
        offset = header.find(b"strh", offset + 4)

    return None


def find_ffmpeg() -> Optional[str]:
    """
    Locate an ffmpeg executable.

    Returns:
        Path to ffmpeg, preferring the ``imageio-ffmpeg`` bundled static build,
        then any ``ffmpeg`` on PATH. None when neither is available.
    """
    try:
        import imageio_ffmpeg  # noqa: PLC0415  (optional, ingest-time only)

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    return shutil.which("ffmpeg")


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

    # First attempt lets ffmpeg pick the decoder. A vendor fourcc it cannot map
    # gets a second attempt with the decoder named explicitly, which is the
    # whole difference between "unplayable" and "plays fine".
    attempts: List[List[str]] = [[]]
    if source.lower().endswith(".avi"):
        forced = FORCED_DECODERS.get((avi_video_fourcc(source) or "").upper())
        if forced:
            attempts.insert(0, ["-vcodec", forced])

    handle, staging = tempfile.mkstemp(suffix=".mp4", dir=out_dir)
    os.close(handle)

    last_error = ""
    try:
        for decoder_args in attempts:
            command = (
                [ffmpeg, "-y", "-loglevel", "error"]
                + decoder_args
                + ["-i", source, "-map", "0:v:0", "-an", "-sn"]
                + _x264_all_intra_args(keyframe_interval, crf)
                + [staging]
            )
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and os.path.getsize(staging) > 0:
                os.replace(staging, out_path)
                return out_path
            last_error = result.stderr.strip()
    finally:
        if os.path.exists(staging):
            os.remove(staging)

    raise VideoEncodeError(f"ffmpeg could not transcode {source}: {last_error}")


def encode_images_to_mp4(
    image_paths: Sequence[str],
    out_path: str,
    fps: float = 10.0,
    keyframe_interval: int = 1,
    crf: int = 20,
) -> str:
    """
    Encode an ordered sequence of images into an mp4.

    Args:
        image_paths: Image paths in frame order. Arbitrary filenames are fine;
            they are staged as a zero-padded sequence for ffmpeg.
        out_path: Destination ``.mp4`` path; parent directories are created.
        fps: Output frame rate. Frame ``i`` lands at timestamp ``i / fps``.
        keyframe_interval: GOP length. 1 means all-intra, keeping every seek
            frame-exact in the browser.
        crf: x264 quality factor; lower is better quality and larger.

    Returns:
        The path written.

    Raises:
        VideoEncodeError: If ffmpeg is unavailable or returns a non-zero status.
        ValueError: If ``image_paths`` is empty.
    """
    if not image_paths:
        raise ValueError("encode_images_to_mp4 requires at least one image")

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise VideoEncodeError(
            "No ffmpeg available. Install 'imageio-ffmpeg' or put ffmpeg on PATH."
        )

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    extension = os.path.splitext(image_paths[0])[1] or ".jpg"

    with tempfile.TemporaryDirectory(prefix="sensorview_video_") as stage_dir:
        # ffmpeg's image2 demuxer wants a sequential zero-padded pattern; the
        # source frames are named by frame id and are neither padded nor
        # necessarily contiguous, so stage links in slider order.
        for index, source in enumerate(image_paths):
            staged = os.path.join(stage_dir, f"{index:06d}{extension}")
            try:
                os.symlink(os.path.abspath(source), staged)
            except (OSError, NotImplementedError):
                shutil.copyfile(source, staged)

        command = (
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                str(fps),
                "-i",
                os.path.join(stage_dir, f"%06d{extension}"),
            ]
            + _x264_all_intra_args(keyframe_interval, crf)
            + [out_path]
        )

        result = subprocess.run(
            command, capture_output=True, text=True, check=False
        )

    if result.returncode != 0:
        raise VideoEncodeError(
            f"ffmpeg failed ({result.returncode}): {result.stderr.strip()}"
        )

    return out_path


def sorted_image_frames(image_dir: str) -> List[tuple]:
    """
    List ``<frame_id>.<ext>`` images in numeric frame order.

    Args:
        image_dir: Directory of per-frame images named by frame id.

    Returns:
        List of ``(frame_id, path)`` tuples sorted by frame id. Frame ids are
        ints when the filename parses as one, else the raw stem string.
    """
    if not os.path.isdir(image_dir):
        return []

    entries = []
    for name in os.listdir(image_dir):
        stem, ext = os.path.splitext(name)
        if ext.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        try:
            frame_id = int(stem)
        except ValueError:
            frame_id = stem
        entries.append((frame_id, os.path.join(image_dir, name)))

    return sorted(entries, key=lambda item: (isinstance(item[0], str), item[0]))
