"""Camera Video Encoding

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

from typing import List, Optional, Sequence

import os
import shutil
import subprocess
import tempfile


class VideoEncodeError(Exception):
    """Raised when no ffmpeg is available or the encode fails."""


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

        command = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            os.path.join(stage_dir, f"%06d{extension}"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            # Short GOP + no scene-cut keyframe insertion keeps keyframe
            # placement deterministic, which is what makes currentTime seeks
            # land on the intended frame.
            "-g",
            str(max(1, keyframe_interval)),
            "-keyint_min",
            str(max(1, keyframe_interval)),
            "-sc_threshold",
            "0",
            "-crf",
            str(crf),
            # Even dimensions are required by yuv420p; scale up by at most a
            # pixel rather than failing on odd-sized source frames.
            "-vf",
            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-movflags",
            "+faststart",
            out_path,
        ]

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
