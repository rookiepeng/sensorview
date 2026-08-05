"""Dataset Ingestion Pipeline

Converts raw recordings into the layout the app reads. Logs live side by side in
one case folder and are associated by basename -- no subfolders, no per-file
manifest entries::

    <out_dir>/
        info.json               manifest v2 (conventions only)
        drive_01.parquet        filterable radar point cloud
        drive_01.cloud.h5       decimated point-cloud backdrop
        drive_01.curve.h5       per-(frame, series) 1D curves
        drive_01.mp4            camera, all-intra for frame-exact seeking
        drive_01.rear.mp4       additional named camera stream
        drive_02.parquet        the next log, same conventions

Everything expensive -- Parquet encoding, cloud decimation, video encoding --
happens here once, so the read path stays a per-frame blob fetch. The frame
index is *not* written to the manifest: it is derived from the Parquet data at
load time so the two can never drift apart.

CLI:
    python -m dataio.ingest ./data/Example --out ./data/Example_v2

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional, Sequence

import argparse
import json
import os

import numpy as np

from dataio.dense_store import (
    DEFAULT_CLOUD_PATTERN,
    DEFAULT_CURVE_PATTERN,
    write_cloud_frames,
    write_curve_frames,
)
from dataio.decimate import decimate
from dataio.frames import build_frame_index
from dataio.manifest import (
    DEFAULT_IMAGE_SUFFIX,
    DEFAULT_CLOUD_SUFFIX,
    DEFAULT_REFERENCE_SUFFIX,
    DEFAULT_TABLE_SUFFIX,
    DEFAULT_CURVE_SUFFIX,
    MANIFEST_NAME,
    MANIFEST_VERSION,
    upgrade_to_v2,
)
from dataio.radar_store import load_radar, write_radar
from dataio.video import VideoEncodeError, encode_images_to_mp4, sorted_image_frames

DEFAULT_VOXEL_SIZE = 0.15
# Budget for a *backdrop*, not for analysis: the cloud is never filtered
# or hovered, and every point costs both WebGL fill rate and JSON payload on the
# per-frame fetch. 25k keeps scene structure readable at a fraction of the cost.
DEFAULT_MAX_POINTS = 25000
# Centimetre precision. Range accuracy is coarser than this anyway, and
# trimming the mantissa materially shrinks both the HDF5 chunk and the JSON the
# browser pulls each frame.
DEFAULT_COORD_DECIMALS = 2
DEFAULT_FPS = 10.0

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
_RADAR_INPUT_EXTENSIONS = (".csv", ".pkl", ".parquet")


def _discover_table_files(case_dir: str) -> List[str]:
    """
    Find radar tables in a source case directory.

    Args:
        case_dir: Source case directory.

    Returns:
        Sorted list of ``.csv``/``.pkl``/``.parquet`` paths at the top level.
        A reference-pose sidecar is Parquet too but is not a log, so it is not
        listed as one -- which matters when the source is a folder this pipeline
        already produced.
    """
    if not os.path.isdir(case_dir):
        return []
    return [
        os.path.join(case_dir, name)
        for name in sorted(os.listdir(case_dir))
        if name.lower().endswith(_RADAR_INPUT_EXTENSIONS)
        and not name.lower().endswith(DEFAULT_REFERENCE_SUFFIX)
    ]


def _discover_image_dirs(case_dir: str, stem: str) -> Dict[str, str]:
    """
    Find per-frame image folders belonging to one log.

    The legacy convention is a folder named after the data file stem holding
    ``<frame_id>.jpg`` images; ``<stem>.<id>`` folders add named streams.

    Args:
        case_dir: Source case directory.
        stem: Log stem to match.

    Returns:
        Mapping of stream id to image directory. The default stream uses the id
        ``camera``.
    """
    streams: Dict[str, str] = {}
    if not os.path.isdir(case_dir):
        return streams

    for name in sorted(os.listdir(case_dir)):
        sub = os.path.join(case_dir, name)
        if not os.path.isdir(sub) or not name.startswith(stem):
            continue
        try:
            has_images = any(
                entry.lower().endswith(_IMAGE_EXTENSIONS) for entry in os.listdir(sub)
            )
        except OSError:
            continue
        if not has_images:
            continue

        middle = name[len(stem) :]
        if middle == "":
            streams["image"] = sub
        elif middle.startswith("."):
            streams[middle[1:]] = sub
        elif middle.startswith("_"):
            streams[middle[1:]] = sub

    return streams


def _discover_sidecar_dir(case_dir: str, stem: str, kind: str) -> Optional[str]:
    """
    Find a log's raw cloud or curve input folder by basename.

    Mirrors the output convention on the input side, so a case folder holding
    several logs can be ingested in one pass with each log picking up its own
    sidecars::

        drive_01.csv  drive_01.cloud/  drive_01.curve/
        drive_02.csv  drive_02.cloud/  drive_02.curve/

    Args:
        case_dir: Source case directory.
        stem: Log stem to match.
        kind: Either ``cloud`` or ``curve``.

    Returns:
        Path to the matching directory, or None when the log has none.
    """
    for separator in (".", "_"):
        candidate = os.path.join(case_dir, f"{stem}{separator}{kind}")
        if os.path.isdir(candidate):
            return candidate
    return None


def ingest_table(source: str, out_dir: str, stem: str) -> Any:
    """
    Convert one radar table to Parquet.

    Args:
        source: Input ``.csv``/``.pkl``/``.parquet`` path.
        out_dir: Destination dataset root.
        stem: Log stem to write under.

    Returns:
        The loaded DataFrame, so callers can derive the frame index from it.
    """
    data = load_radar([source])
    write_radar(data, os.path.join(out_dir, f"{stem}{DEFAULT_TABLE_SUFFIX}"))
    return data


def _read_cloud_frames(
    source: str,
    frame_key: str,
    xyz_keys: Sequence[str],
    intensity_key: Optional[str],
) -> Dict[Any, np.ndarray]:
    """
    Read raw cloud frames from a tabular file or a directory of arrays.

    Args:
        source: Either a tabular file with a frame column, or a directory of
            ``<frame_id>.npy`` arrays.
        frame_key: Frame column name (tabular input only).
        xyz_keys: Column names for x, y, z (tabular input only).
        intensity_key: Optional intensity column name (tabular input only).

    Returns:
        Mapping of frame id to an (N, C) array.

    Raises:
        ValueError: If a tabular source is missing required columns.
    """
    frames: Dict[Any, np.ndarray] = {}

    if os.path.isdir(source):
        for name in sorted(os.listdir(source)):
            base, ext = os.path.splitext(name)
            if ext.lower() != ".npy":
                continue
            try:
                frame_id: Any = int(base)
            except ValueError:
                frame_id = base
            frames[frame_id] = np.load(os.path.join(source, name))
        return frames

    data = load_radar([source])
    columns = list(xyz_keys)
    if intensity_key and intensity_key in data.columns:
        columns.append(intensity_key)

    missing = [c for c in columns if c not in data.columns]
    if missing:
        raise ValueError(f"Cloud source {source} is missing columns: {missing}")
    if frame_key not in data.columns:
        raise ValueError(f"Cloud source {source} has no frame column {frame_key!r}")

    for frame_id, group in data.groupby(frame_key):
        frames[frame_id] = group[columns].to_numpy()

    return frames


def ingest_cloud(
    source: str,
    out_dir: str,
    stem: str,
    frame_key: str = "Frame",
    xyz_keys: Sequence[str] = ("x", "y", "z"),
    intensity_key: Optional[str] = None,
    voxel_size: float = DEFAULT_VOXEL_SIZE,
    max_points: int = DEFAULT_MAX_POINTS,
    coord_decimals: int = DEFAULT_COORD_DECIMALS,
) -> Dict[str, Any]:
    """
    Decimate cloud frames and write one log's HDF5 backdrop sidecar.

    Decimation happens here, once. The app never sees full-resolution cloud
    because no runtime control could ever ask for it.

    Args:
        source: Tabular file or directory of per-frame ``.npy`` arrays.
        out_dir: Destination dataset root.
        stem: Log stem to write under.
        frame_key: Frame column name for tabular input.
        xyz_keys: xyz column names for tabular input.
        intensity_key: Optional intensity column for tabular input.
        voxel_size: Voxel edge length in meters for downsampling.
        max_points: Hard per-frame point budget.
        coord_decimals: Decimal places to round coordinates to; negative
            disables rounding.

    Returns:
        Per-log decimation statistics.
    """
    raw_frames = _read_cloud_frames(source, frame_key, xyz_keys, intensity_key)

    decimated = {}
    for frame_id, points in raw_frames.items():
        reduced = decimate(points, voxel_size=voxel_size, max_points=max_points)
        if coord_decimals >= 0:
            reduced = np.round(reduced, coord_decimals)
        decimated[frame_id] = reduced

    columns = list(xyz_keys)
    if intensity_key:
        sample = next(iter(decimated.values()), None)
        if sample is not None and sample.shape[1] > 3:
            columns.append(intensity_key)

    write_cloud_frames(
        os.path.join(out_dir, f"{stem}{DEFAULT_CLOUD_SUFFIX}"),
        decimated,
        columns=columns,
    )

    return {
        "columns": columns,
        "points_in": int(sum(p.shape[0] for p in raw_frames.values())),
        "points_out": int(sum(p.shape[0] for p in decimated.values())),
    }


def ingest_curve(source: str, out_dir: str, stem: str) -> List[str]:
    """
    Write one log's per-frame threshold curves.

    The source directory holds one folder per named series::

        drive_01.curve/
        ├── signal/<frame_id>.npy       (N, 2): x column, then value
        ├── threshold/<frame_id>.npy
        └── noise_floor/<frame_id>.npy

    Each frame's array carries its own x column, because a shared axis cannot
    describe real data -- bin spacing varies between sensors and between frames.
    A plain 1D array is still accepted and is paired with its sample index.

    Args:
        source: Directory laid out as above.
        out_dir: Destination dataset root.
        stem: Log stem to write under.

    Returns:
        Series names written, in sorted order.

    Raises:
        ValueError: If ``source`` is not a directory.
    """
    if not os.path.isdir(source):
        raise ValueError(f"Threshold source must be a directory: {source}")

    frames: Dict[Any, Dict[str, np.ndarray]] = {}
    signals: List[str] = []

    for entry in sorted(os.listdir(source)):
        entry_dir = os.path.join(source, entry)
        if not os.path.isdir(entry_dir):
            continue

        signals.append(entry)
        for name in sorted(os.listdir(entry_dir)):
            base, ext = os.path.splitext(name)
            if ext.lower() != ".npy":
                continue
            try:
                frame_id: Any = int(base)
            except ValueError:
                frame_id = base
            frames.setdefault(frame_id, {})[entry] = np.load(
                os.path.join(entry_dir, name)
            )

    write_curve_frames(
        os.path.join(out_dir, f"{stem}{DEFAULT_CURVE_SUFFIX}"),
        frames,
    )
    return sorted(signals)


def _starter_curve_plots(signals: Sequence[str]) -> List[Dict[str, Any]]:
    """
    Build a starting ``threshold.plots`` config from what was ingested.

    Every series lands on one plot. That is only a starting point -- which
    curves belong together, and how they are styled, is an authoring decision
    made by editing ``info.json``.

    Args:
        signals: Series names written.

    Returns:
        A single plot definition, or empty when there are no series.
    """
    if not signals:
        return []

    return [
        {
            "id": "curve",
            "label": "Threshold",
            "x": {"label": "Sample"},
            "y_label": "Magnitude (dB)",
            "traces": [
                {"name": name, "label": name.replace("_", " ").title()}
                for name in signals
            ],
        }
    ]


def ingest_image(
    streams: Dict[str, str],
    out_dir: str,
    stem: str,
    frame_ids: Sequence[Any],
    fps: float = DEFAULT_FPS,
    keyframe_interval: int = 1,
) -> List[Dict[str, Any]]:
    """
    Encode one log's per-frame image folders into mp4 streams.

    Images are ordered by the log's frame ids, so video frame ``i`` is slider
    index ``i`` and the player seeks to ``(i + 0.5) / fps``. Seeking is
    deliberately index-based rather than keyed off dataset timestamps: the two
    only coincide when capture is perfectly uniform, and an index mapping stays
    correct when it is not.

    Args:
        streams: Mapping of stream id to image directory.
        out_dir: Destination dataset root.
        stem: Log stem to write under.
        frame_ids: The log's frame ids, used to order and align frames.
        fps: Output frame rate.
        keyframe_interval: GOP length; 1 keeps every seek frame-exact.

    Returns:
        Summaries of the streams written. Streams that fail to encode are
        skipped with a warning rather than aborting the ingest.
    """
    written = []
    frame_order = {frame_id: index for index, frame_id in enumerate(frame_ids)}

    for stream_id, image_dir in streams.items():
        available = sorted_image_frames(image_dir)
        if not available:
            continue

        ordered = [
            path
            for _, path in sorted(
                (
                    (frame_order[frame_id], path)
                    for frame_id, path in available
                    if frame_id in frame_order
                ),
                key=lambda item: item[0],
            )
        ]
        if not ordered:
            ordered = [path for _, path in available]

        # The default stream is "<stem>.mp4"; named streams are "<stem>.<id>.mp4".
        name = (
            f"{stem}{DEFAULT_IMAGE_SUFFIX}"
            if stream_id == "image"
            else f"{stem}.{stream_id}{DEFAULT_IMAGE_SUFFIX}"
        )

        try:
            encode_images_to_mp4(
                ordered,
                os.path.join(out_dir, name),
                fps=fps,
                keyframe_interval=keyframe_interval,
            )
        except (VideoEncodeError, ValueError) as exc:
            print(f"    ! camera stream {stream_id!r} skipped: {exc}")
            continue

        written.append({"id": stream_id, "file": name, "frame_count": len(ordered)})

    return written


def ingest_case(
    case_dir: str,
    out_dir: str,
    table_sources: Optional[Sequence[str]] = None,
    cloud_source: Optional[str] = None,
    curve_source: Optional[str] = None,
    image_dirs: Optional[Dict[str, str]] = None,
    fps: Optional[float] = None,
    voxel_size: float = DEFAULT_VOXEL_SIZE,
    max_points: int = DEFAULT_MAX_POINTS,
    coord_decimals: int = DEFAULT_COORD_DECIMALS,
    cloud_frame_key: Optional[str] = None,
    cloud_xyz_keys: Sequence[str] = ("x", "y", "z"),
    cloud_intensity_key: Optional[str] = None,
    keyframe_interval: int = 1,
) -> str:
    """
    Ingest a case directory, converting every log it contains.

    Each radar table becomes one log. Sidecars given explicitly
    (``cloud_source``, ``curve_source``, ``image_dirs``) apply to the first
    log only; otherwise each log's camera folders are discovered by basename.

    Args:
        case_dir: Source case directory (may hold a v1 ``info.json``).
        out_dir: Destination dataset root; created if missing.
        table_sources: Radar tables; auto-discovered from ``case_dir`` if None.
        cloud_source: Cloud table or ``.npy`` directory; skipped if None.
        curve_source: ``<sensor_id>/<frame_id>.npy`` directory; skipped if None.
        image_dirs: Stream id to image directory; auto-discovered if None.
        fps: Camera frame rate. When None, inferred per log from its timestamps
            so video duration matches real elapsed time.
        voxel_size: Cloud voxel downsample size in meters.
        max_points: Cloud per-frame point budget.
        coord_decimals: Decimal places to round cloud coordinates to.
        cloud_frame_key: Frame column in a tabular cloud source; defaults to the
            radar frame key.
        cloud_xyz_keys: xyz columns in a tabular cloud source.
        cloud_intensity_key: Optional intensity column in a tabular cloud source.
        keyframe_interval: Camera GOP length.

    Returns:
        Path to the written manifest.

    Raises:
        ValueError: If no radar source can be found.
    """
    os.makedirs(out_dir, exist_ok=True)

    source_manifest: Dict[str, Any] = {}
    source_info = os.path.join(case_dir, MANIFEST_NAME)
    if os.path.exists(source_info):
        with open(source_info, "r", encoding="utf-8") as read_file:
            source_manifest = upgrade_to_v2(json.load(read_file))

    table_block = dict(source_manifest.get("table", {}))
    frame_key = table_block.get("slider", "Frame")

    sources = list(table_sources or _discover_table_files(case_dir))
    if not sources:
        raise ValueError(f"No radar source files found in {case_dir}")

    table_block["format"] = "parquet"
    table_block["suffix"] = DEFAULT_TABLE_SUFFIX
    table_block.setdefault(
        "calibration", {"translation": [0, 0, 0], "rotation_rpy_deg": [0, 0, 0]}
    )

    manifest: Dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "name": source_manifest.get("name")
        or os.path.basename(os.path.normpath(case_dir)),
        "table": table_block,
    }

    cloud_stats: Optional[Dict[str, Any]] = None
    threshold_signals: List[str] = []
    wrote_camera = False

    for index, source in enumerate(sources):
        stem = os.path.splitext(os.path.basename(source))[0]
        print(f"* log {stem!r}")

        data = ingest_table(source, out_dir, stem)
        frame_ids, timestamps, effective_fps = build_frame_index(
            data, frame_key, fps=fps
        )
        print(
            f"    radar: {len(data)} points, {len(frame_ids)} frames, "
            f"{effective_fps} fps"
        )

        # An explicitly passed sidecar describes one recording, so it attaches to
        # the first log; every other log discovers its own by basename.
        log_cloud = (
            cloud_source
            if cloud_source and index == 0
            else _discover_sidecar_dir(case_dir, stem, "cloud")
        )
        if log_cloud:
            stats = ingest_cloud(
                log_cloud,
                out_dir,
                stem,
                frame_key=cloud_frame_key or frame_key,
                xyz_keys=cloud_xyz_keys,
                intensity_key=cloud_intensity_key,
                voxel_size=voxel_size,
                max_points=max_points,
                coord_decimals=coord_decimals,
            )
            cloud_stats = cloud_stats or stats
            print(f"    cloud: {stats['points_in']} -> {stats['points_out']} points")

        log_threshold = (
            curve_source
            if curve_source and index == 0
            else _discover_sidecar_dir(case_dir, stem, "curve")
        )
        if log_threshold:
            signals = ingest_curve(log_threshold, out_dir, stem)
            if not threshold_signals:
                threshold_signals = signals
            print(f"    threshold: {len(signals)} series {signals}")

        streams = (
            image_dirs
            if image_dirs is not None and index == 0
            else _discover_image_dirs(case_dir, stem)
        )
        if streams:
            written = ingest_image(
                streams,
                out_dir,
                stem,
                frame_ids,
                fps=effective_fps,
                keyframe_interval=keyframe_interval,
            )
            for entry in written:
                wrote_camera = True
                print(
                    f"    camera[{entry['id']}]: {entry['frame_count']} frames "
                    f"@ {effective_fps} fps -> {entry['file']}"
                )

    if cloud_stats is not None:
        manifest["cloud"] = {
            "format": "hdf5",
            "suffix": DEFAULT_CLOUD_SUFFIX,
            "dataset_pattern": DEFAULT_CLOUD_PATTERN,
            "columns": cloud_stats["columns"],
            "decimation": {
                "method": "voxel+budget",
                "voxel_size": voxel_size,
                "max_points": max_points,
                "coord_decimals": coord_decimals,
            },
            "calibration": {"translation": [0, 0, 0], "rotation_rpy_deg": [0, 0, 0]},
        }

    if threshold_signals:
        # A starter config grouping every series onto one plot. Splitting and
        # styling them is an authoring decision, made by editing info.json.
        manifest["curve"] = {
            "format": "hdf5",
            "suffix": DEFAULT_CURVE_SUFFIX,
            "dataset_pattern": DEFAULT_CURVE_PATTERN,
            "plots": _starter_curve_plots(threshold_signals),
        }

    if wrote_camera:
        manifest["image"] = {
            "format": "mp4",
            "suffix": DEFAULT_IMAGE_SUFFIX,
            # Players seek by slider index, not dataset timestamp; see
            # ingest_image for why.
            "seek": "index",
        }

    manifest_path = os.path.join(out_dir, MANIFEST_NAME)
    with open(manifest_path, "w", encoding="utf-8") as write_file:
        json.dump(manifest, write_file, indent=4)

    print(f"* manifest: {manifest_path}")
    return manifest_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Command-line entry point.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit status.
    """
    parser = argparse.ArgumentParser(
        prog="python -m dataio.ingest",
        description="Convert a recording into the SensorView v2 dataset layout.",
    )
    parser.add_argument("case_dir", help="Source case directory")
    parser.add_argument("--out", required=True, help="Destination dataset directory")
    parser.add_argument(
        "--table", nargs="*", default=None, help="Table file(s); default: auto-discover"
    )
    parser.add_argument(
        "--cloud", default=None, help="Cloud table or directory of <frame>.npy"
    )
    parser.add_argument(
        "--curve", default=None, help="Directory of <series>/<frame_id>.npy"
    )
    parser.add_argument(
        "--image",
        nargs="*",
        default=None,
        metavar="ID=DIR",
        help="Image streams as id=image_dir; default: auto-discover",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Image frame rate; default: inferred from the data's timestamps",
    )
    parser.add_argument("--voxel-size", type=float, default=DEFAULT_VOXEL_SIZE)
    parser.add_argument("--max-points", type=int, default=DEFAULT_MAX_POINTS)
    parser.add_argument(
        "--coord-decimals",
        type=int,
        default=DEFAULT_COORD_DECIMALS,
        help="Round cloud coordinates to N decimals (-1 to disable)",
    )
    parser.add_argument("--cloud-frame-key", default=None)
    parser.add_argument("--cloud-xyz-keys", nargs=3, default=("x", "y", "z"))
    parser.add_argument("--cloud-intensity-key", default=None)
    parser.add_argument(
        "--keyframe-interval",
        type=int,
        default=1,
        help="Image GOP length; 1 (default) keeps seeks frame-exact",
    )

    args = parser.parse_args(argv)

    image_dirs = None
    if args.image is not None:
        image_dirs = {}
        for item in args.image:
            if "=" not in item:
                parser.error(f"--image expects id=dir, got {item!r}")
            stream_id, image_dir = item.split("=", 1)
            image_dirs[stream_id] = image_dir

    ingest_case(
        args.case_dir,
        args.out,
        table_sources=args.table,
        cloud_source=args.cloud,
        curve_source=args.curve,
        image_dirs=image_dirs,
        fps=args.fps,
        voxel_size=args.voxel_size,
        max_points=args.max_points,
        coord_decimals=args.coord_decimals,
        cloud_frame_key=args.cloud_frame_key,
        cloud_xyz_keys=tuple(args.cloud_xyz_keys),
        cloud_intensity_key=args.cloud_intensity_key,
        keyframe_interval=args.keyframe_interval,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
