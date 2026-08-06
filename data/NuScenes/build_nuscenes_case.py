"""Build a SensorView case folder from the nuScenes mini split.

One nuScenes *scene* becomes one SensorView *log*, keyed on its keyframes
(samples, 2 Hz). Everything is written in a world frame recentred on the scene's
first ego position, so the host vehicle moves through the data instead of the
data moving around a fixed host -- which is what makes the reference-pose
sidecar and the decay slider worth having.

    <scene>.parquet             radar detections from all five radars (the table)
    <scene>.cloud.h5            decimated LIDAR_TOP sweep per frame (the backdrop)
    <scene>.<radar>.h5          per-radar 1D curves, one file per sensor
    <scene>.lidar.h5            lidar 1D curves
    <scene>.mp4                 CAM_FRONT
    <scene>.back.mp4            CAM_BACK
    <scene>.reference.parquet   ego pose per frame (position + yaw/pitch/roll)

Usage:
    python build_nuscenes_case.py --root D:/tmp/nuscenes --out data/NuScenes \
        --scenes scene-0061 scene-0103
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

import h5py
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# nuScenes constants
# --------------------------------------------------------------------------

RADAR_CHANNELS = [
    "RADAR_FRONT",
    "RADAR_FRONT_LEFT",
    "RADAR_FRONT_RIGHT",
    "RADAR_BACK_LEFT",
    "RADAR_BACK_RIGHT",
]
LIDAR_CHANNEL = "LIDAR_TOP"
CAMERA_STREAMS = {"CAM_FRONT": "", "CAM_BACK": ".back"}

DYN_PROP = {
    0: "moving",
    1: "stationary",
    2: "oncoming",
    3: "stationary candidate",
    4: "unknown",
    5: "crossing stationary",
    6: "crossing moving",
    7: "stopped",
}
AMBIG_STATE = {
    0: "invalid",
    1: "ambiguous",
    2: "staggered ramp",
    3: "unambiguous",
    4: "stationary candidate",
}
PDH0 = {
    0: "invalid",
    1: "<25%",
    2: "<50%",
    3: "<75%",
    4: "<90%",
    5: "<99%",
    6: "<99.9%",
    7: "<=100%",
}

# Curve binning. Both radar plots share one range grid so they read against the
# same axis, but the grid itself is per sensor: a corner radar that never sees
# past 100 m has no business carrying the front radar's 250 m of empty bins.
RADAR_RANGE_BIN = 2.0
LIDAR_RANGE_BIN = 2.0
LIDAR_RANGE_MAX = 100.0
# The first two metres of a lidar sweep are the ego vehicle's own bodywork, and
# that one bin outweighs everything the scan is actually looking at.
LIDAR_RANGE_START = 2.0
LIDAR_HEIGHT_BIN = 0.25
LIDAR_HEIGHT_RANGE = (-2.0, 8.0)
GROUND_HEIGHT = 0.5

# Backdrop decimation. Voxel first (uniform in space), then a hard budget so a
# dense frame cannot blow the file up.
VOXEL_SIZE = 0.25
POINT_BUDGET = 12000

VIDEO_WIDTH = 960
VIDEO_CRF = 26

# nuScenes keyframes are 2 Hz. Used only to space consecutive logs on the
# running clock, so one log's last frame and the next one's first are one
# ordinary frame apart.
FRAME_INTERVAL = 0.5


# --------------------------------------------------------------------------
# nuScenes tables
# --------------------------------------------------------------------------


def load_tables(root, version):
    """Read every nuScenes JSON table, indexed by token."""
    meta_dir = os.path.join(root, version)
    tables = {}
    for name in (
        "scene",
        "sample",
        "sample_data",
        "ego_pose",
        "calibrated_sensor",
        "sensor",
        "log",
    ):
        with open(os.path.join(meta_dir, f"{name}.json"), encoding="utf-8") as handle:
            tables[name] = json.load(handle)
    indexed = {name: {r["token"]: r for r in rows} for name, rows in tables.items()}
    return tables, indexed


def scene_samples(tables, indexed, scene):
    """Samples of one scene, in capture order."""
    samples = []
    token = scene["first_sample_token"]
    while token:
        record = indexed["sample"][token]
        samples.append(record)
        token = record["next"]
    return samples


def sample_data_by_sample(tables, indexed):
    """Keyframe sample_data records, grouped sample token -> channel -> record."""
    grouped = defaultdict(dict)
    for record in tables["sample_data"]:
        if not record["is_key_frame"]:
            continue
        sensor = indexed["sensor"][
            indexed["calibrated_sensor"][record["calibrated_sensor_token"]][
                "sensor_token"
            ]
        ]
        grouped[record["sample_token"]][sensor["channel"]] = record
    return grouped


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def quat_to_matrix(quaternion):
    """Rotation matrix from a nuScenes [w, x, y, z] quaternion."""
    w, x, y, z = quaternion
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def rotate(points, matrix):
    """Apply a 3x3 rotation to (N, 3) points.

    Written out as element-wise products rather than ``points @ matrix.T``
    because numpy's BLAS is broken in this environment (a 3x3 matmul faults on
    a delay-loaded DLL). Same arithmetic, no gemm call.
    """
    return np.column_stack(
        [
            points[:, 0] * matrix[axis, 0]
            + points[:, 1] * matrix[axis, 1]
            + points[:, 2] * matrix[axis, 2]
            for axis in range(3)
        ]
    )


def matrix_to_rpy(matrix):
    """ZYX intrinsic roll/pitch/yaw, matching dataio.calibration.rotation_matrix."""
    pitch = np.arcsin(np.clip(-matrix[2, 0], -1.0, 1.0))
    yaw = np.arctan2(matrix[1, 0], matrix[0, 0])
    roll = np.arctan2(matrix[2, 1], matrix[2, 2])
    return float(roll), float(pitch), float(yaw)


# --------------------------------------------------------------------------
# Point cloud readers
# --------------------------------------------------------------------------


def read_radar_pcd(path):
    """Read a nuScenes radar .pcd as a structured array, fields as declared."""
    header = {}
    with open(path, "rb") as handle:
        while True:
            line = handle.readline().decode("utf-8").strip()
            if not line:
                raise ValueError(f"Unexpected end of header in {path}")
            key, _, rest = line.partition(" ")
            header[key] = rest.split()
            if key == "DATA":
                break
        if header["DATA"][0] != "binary":
            raise ValueError(f"Unsupported PCD payload {header['DATA'][0]!r}")

        kinds = {"F": "f", "I": "i", "U": "u"}
        dtype = np.dtype(
            [
                (name, f"{kinds[kind]}{size}")
                for name, kind, size in zip(
                    header["FIELDS"], header["TYPE"], [int(s) for s in header["SIZE"]]
                )
            ]
        )
        count = int(header["POINTS"][0])
        return np.frombuffer(handle.read(dtype.itemsize * count), dtype=dtype)


def read_lidar_bin(path):
    """Read a LIDAR_TOP .pcd.bin as (N, 5): x, y, z, intensity, ring."""
    return np.fromfile(path, dtype=np.float32).reshape(-1, 5)


def decimate(points, voxel_size=VOXEL_SIZE, budget=POINT_BUDGET, seed=0):
    """Voxel-downsample to one point per cell, then cap at a point budget."""
    if len(points) == 0:
        return points

    keys = np.floor(points[:, :3] / voxel_size).astype(np.int64)
    _, first = np.unique(keys, axis=0, return_index=True)
    kept = points[np.sort(first)]

    if len(kept) > budget:
        rng = np.random.default_rng(seed)
        kept = kept[np.sort(rng.choice(len(kept), budget, replace=False))]
    return kept


# --------------------------------------------------------------------------
# Curve derivation
# --------------------------------------------------------------------------


def bin_centers(width, maximum, start=0.0):
    """Centres of a uniform bin grid."""
    edges = np.arange(start, maximum + width, width)
    return (edges[:-1] + edges[1:]) / 2.0


def binned(values, weights, width, maximum, start, reducer):
    """Reduce `weights` into bins of `values`; empty bins come back as NaN."""
    centres = bin_centers(width, maximum, start)
    out = np.full(len(centres), np.nan)

    usable = np.isfinite(values) & np.isfinite(weights)
    values, weights = values[usable], weights[usable]
    if len(values) == 0:
        return centres, out

    index = np.floor((values - start) / width).astype(int)
    valid = (index >= 0) & (index < len(centres))
    for slot in np.unique(index[valid]):
        out[slot] = reducer(weights[valid & (index == slot)])
    return centres, out


def pair(x_values, y_values):
    """(N, 2) float32 curve, x in column 0."""
    return np.column_stack([x_values, y_values]).astype(np.float32)


# --------------------------------------------------------------------------
# Video
# --------------------------------------------------------------------------


def find_ffmpeg():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def encode_video(jpeg_paths, out_path, fps):
    """Encode a JPEG sequence as the all-intra mp4 the camera panel seeks."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("no ffmpeg available")

    staging = tempfile.mkdtemp(prefix="nusc_frames_")
    try:
        for index, source in enumerate(jpeg_paths):
            shutil.copyfile(source, os.path.join(staging, f"{index:05d}.jpg"))

        command = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            f"{fps}",
            "-start_number",
            "0",
            "-i",
            os.path.join(staging, "%05d.jpg"),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "1",
            "-keyint_min",
            "1",
            "-sc_threshold",
            "0",
            "-crf",
            str(VIDEO_CRF),
            "-vf",
            f"scale={VIDEO_WIDTH}:-2",
            "-movflags",
            "+faststart",
            out_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# --------------------------------------------------------------------------
# Per-scene build
# --------------------------------------------------------------------------


def build_scene(
    root,
    version,
    out_dir,
    scene,
    tables,
    indexed,
    keyframes,
    frame_offset=0,
    time_offset=0.0,
):
    """
    Write one scene out as one log.

    Args:
        frame_offset: Frame id the log's first keyframe carries. Logs in a case
            folder are numbered end to end rather than each restarting at zero,
            so a frame id identifies a log as well as a moment in it.
        time_offset: Seconds the log's first keyframe sits at, on the same
            running clock.
    """
    stem = scene["name"].replace("-", "_")
    samples = scene_samples(tables, indexed, scene)
    print(f"  {scene['name']}: {len(samples)} keyframes, frames {frame_offset}-"
          f"{frame_offset + len(samples) - 1}")

    origin = None
    rows = defaultdict(list)
    poses = defaultdict(list)
    cloud_frames = {}
    # Curves are derived after the sweep loop: each sensor's range grid is fixed
    # to the furthest it saw across the whole log, which cannot be known yet.
    radar_detections = {channel: {} for channel in RADAR_CHANNELS}
    lidar_curves = {}
    camera_frames = {channel: [] for channel in CAMERA_STREAMS}

    t_zero = samples[0]["timestamp"]

    for index, sample in enumerate(samples):
        frame_id = frame_offset + index
        channels = keyframes[sample["token"]]

        lidar_sd = channels[LIDAR_CHANNEL]
        ego = indexed["ego_pose"][lidar_sd["ego_pose_token"]]
        ego_t = np.array(ego["translation"])
        ego_r = quat_to_matrix(ego["rotation"])
        if origin is None:
            origin = ego_t.copy()

        roll, pitch, yaw = matrix_to_rpy(ego_r)
        ego_local = ego_t - origin
        poses["frame"].append(frame_id)
        poses["x"].append(ego_local[0])
        poses["y"].append(ego_local[1])
        poses["z"].append(ego_local[2])
        poses["yaw"].append(yaw)
        poses["pitch"].append(pitch)
        poses["roll"].append(roll)

        time_s = time_offset + (sample["timestamp"] - t_zero) / 1e6

        # ---------------- radar ----------------
        for channel in RADAR_CHANNELS:
            record = channels.get(channel)
            if record is None:
                continue
            calibration = indexed["calibrated_sensor"][record["calibrated_sensor_token"]]
            cal_r = quat_to_matrix(calibration["rotation"])
            cal_t = np.array(calibration["translation"])

            # Each sensor fires on its own clock -- the radars land 10-30 ms
            # either side of the lidar -- and nuScenes records an ego pose per
            # sample_data. Placing a sweep with the pose captured at *its*
            # timestamp rather than the lidar's is worth up to 0.3 m at speed.
            sweep_ego = indexed["ego_pose"][record["ego_pose_token"]]
            sweep_t = np.array(sweep_ego["translation"])
            sweep_r = quat_to_matrix(sweep_ego["rotation"])

            points = read_radar_pcd(os.path.join(root, record["filename"]))
            # A handful of detections per log arrive with no position at all.
            # They cannot be placed, binned, or filtered on, so they are dropped
            # here rather than becoming NaN rows the whole pipeline works around.
            points = points[np.isfinite(points["x"]) & np.isfinite(points["y"])]
            xyz = np.column_stack(
                [points["x"], points["y"], np.zeros(len(points))]
            ).astype(float)

            # Range and range rate are properties of the sensor's own frame, so
            # they are computed before anything is rotated away from it.
            radial = np.linalg.norm(xyz[:, :2], axis=1)
            unit = np.divide(
                xyz[:, :2],
                np.where(radial[:, None] == 0, 1.0, radial[:, None]),
            )
            rate_raw = unit[:, 0] * points["vx"] + unit[:, 1] * points["vy"]
            rate_comp = (
                unit[:, 0] * points["vx_comp"] + unit[:, 1] * points["vy_comp"]
            )

            in_ego = rotate(xyz, cal_r) + cal_t
            in_world = rotate(in_ego, sweep_r) + sweep_t - origin
            azimuth = np.degrees(np.arctan2(in_ego[:, 1], in_ego[:, 0]))
            distance = np.linalg.norm(in_ego[:, :2], axis=1)

            count = len(points)
            rows["Frame"].append(np.full(count, frame_id, dtype=np.int32))
            rows["Time"].append(np.full(count, time_s))
            rows["X"].append(in_world[:, 0])
            rows["Y"].append(in_world[:, 1])
            rows["Z"].append(in_world[:, 2])
            rows["Range"].append(distance)
            rows["Azimuth"].append(azimuth)
            rows["RCS"].append(points["rcs"].astype(float))
            rows["Range_Rate"].append(rate_raw)
            rows["Range_Rate_Comp"].append(rate_comp)
            rows["Speed"].append(
                np.hypot(points["vx_comp"], points["vy_comp"]).astype(float)
            )
            rows["Sensor"].append(np.full(count, channel, dtype=object))
            rows["Dyn_Prop"].append(
                np.array([DYN_PROP.get(int(v), "unknown") for v in points["dyn_prop"]], dtype=object)
            )
            rows["Ambig_State"].append(
                np.array([AMBIG_STATE.get(int(v), "unknown") for v in points["ambig_state"]], dtype=object)
            )
            rows["False_Alarm_Prob"].append(
                np.array([PDH0.get(int(v), "unknown") for v in points["pdh0"]], dtype=object)
            )
            rows["Valid"].append(
                np.array(
                    ["valid" if int(v) == 0 else f"invalid ({int(v)})" for v in points["invalid_state"]],
                    dtype=object,
                )
            )

            radar_detections[channel][frame_id] = (
                distance,
                points["rcs"].astype(float),
                rate_raw,
                rate_comp,
            )

        # ---------------- lidar ----------------
        calibration = indexed["calibrated_sensor"][lidar_sd["calibrated_sensor_token"]]
        cal_r = quat_to_matrix(calibration["rotation"])
        cal_t = np.array(calibration["translation"])

        raw = read_lidar_bin(os.path.join(root, lidar_sd["filename"]))
        in_ego = rotate(raw[:, :3].astype(float), cal_r) + cal_t
        in_world = rotate(in_ego, ego_r) + ego_t - origin

        cloud_frames[frame_id] = np.round(decimate(in_world, seed=frame_id), 2).astype(
            np.float32
        )

        distance = np.linalg.norm(in_ego[:, :2], axis=1)
        height = in_ego[:, 2]
        range_edges = np.arange(
            LIDAR_RANGE_START, LIDAR_RANGE_MAX + LIDAR_RANGE_BIN, LIDAR_RANGE_BIN
        )
        centres = (range_edges[:-1] + range_edges[1:]) / 2
        counts, _ = np.histogram(distance, bins=range_edges)
        above, _ = np.histogram(distance[height > GROUND_HEIGHT], bins=range_edges)
        height_edges = np.arange(
            LIDAR_HEIGHT_RANGE[0], LIDAR_HEIGHT_RANGE[1] + LIDAR_HEIGHT_BIN, LIDAR_HEIGHT_BIN
        )
        height_counts, _ = np.histogram(height, bins=height_edges)
        lidar_curves[frame_id] = {
            "returns_all": pair(centres, counts),
            "returns_above_ground": pair(centres, above),
            "height_all": pair((height_edges[:-1] + height_edges[1:]) / 2, height_counts),
        }

        # ---------------- cameras ----------------
        for channel in CAMERA_STREAMS:
            record = channels.get(channel)
            if record is not None:
                camera_frames[channel].append(os.path.join(root, record["filename"]))

    # ---------------- curves ----------------
    # One grid per sensor, sized to the furthest that sensor saw in this log --
    # which is what the multi-source curve panel exists for: a corner radar's
    # range bins are not the front radar's.
    radar_curves = {}
    for channel, frames in radar_detections.items():
        if not frames:
            continue
        furthest = max(
            (float(distance.max()) for distance, *_ in frames.values() if len(distance)),
            default=RADAR_RANGE_BIN,
        )
        maximum = np.ceil(furthest / RADAR_RANGE_BIN) * RADAR_RANGE_BIN
        series = {}
        for frame_id, (distance, rcs, rate_raw, rate_comp) in frames.items():
            centres, peak = binned(distance, rcs, RADAR_RANGE_BIN, maximum, 0.0, np.max)
            _, mean = binned(distance, rcs, RADAR_RANGE_BIN, maximum, 0.0, np.mean)
            _, measured = binned(
                distance, rate_raw, RADAR_RANGE_BIN, maximum, 0.0, np.mean
            )
            _, compensated = binned(
                distance, rate_comp, RADAR_RANGE_BIN, maximum, 0.0, np.mean
            )
            series[frame_id] = {
                "rcs_peak": pair(centres, peak),
                "rcs_mean": pair(centres, mean),
                "rate_measured": pair(centres, measured),
                "rate_compensated": pair(centres, compensated),
                "rate_zero": pair(centres, np.zeros_like(centres)),
            }
        radar_curves[channel] = series
        print(f"    curves: {channel} 0-{maximum:.0f} m in {RADAR_RANGE_BIN:.0f} m bins")

    # ---------------- write ----------------
    table = pd.DataFrame({key: np.concatenate(value) for key, value in rows.items()})
    for column in ("X", "Y", "Z", "Range", "Azimuth", "RCS", "Range_Rate", "Range_Rate_Comp", "Speed", "Time"):
        table[column] = table[column].astype(np.float32).round(3)
    table.to_parquet(os.path.join(out_dir, f"{stem}.parquet"), index=False)
    print(f"    table: {len(table)} detections, {table['Sensor'].nunique()} radars")

    pd.DataFrame(poses).to_parquet(
        os.path.join(out_dir, f"{stem}.reference.parquet"), index=False
    )

    with h5py.File(os.path.join(out_dir, f"{stem}.cloud.h5"), "w") as handle:
        handle.attrs["columns"] = ["x", "y", "z"]
        for frame_id, points in cloud_frames.items():
            handle.create_dataset(
                f"/frame_{frame_id}", data=points, compression="gzip", compression_opts=4
            )
    print(
        f"    cloud: {sum(len(p) for p in cloud_frames.values()) // len(cloud_frames)}"
        " points/frame (mean)"
    )

    # A curve is a kilobyte, where a chunked+compressed HDF5 dataset costs
    # several in bookkeeping alone. These stay contiguous and uncompressed.
    for channel, frames in radar_curves.items():
        path = os.path.join(out_dir, f"{stem}.{channel.lower()}.h5")
        with h5py.File(path, "w") as handle:
            for frame_id, series in frames.items():
                group = handle.create_group(f"/frame_{frame_id}")
                for name, values in series.items():
                    group.create_dataset(name, data=values)

    with h5py.File(os.path.join(out_dir, f"{stem}.lidar.h5"), "w") as handle:
        for frame_id, series in lidar_curves.items():
            group = handle.create_group(f"/frame_{frame_id}")
            for name, values in series.items():
                group.create_dataset(name, data=values)

    # Encoded at the capture rate, so the clip's duration matches the log's and
    # the frame-count seek lands one video frame per slider step. Measured
    # against the log's own span, not the running clock it is offset onto.
    duration = time_s - time_offset
    fps = round((len(samples) - 1) / duration, 3) if duration > 0 else 2.0
    for channel, suffix in CAMERA_STREAMS.items():
        paths = camera_frames[channel]
        if not paths:
            continue
        out_path = os.path.join(out_dir, f"{stem}{suffix}.mp4")
        encode_video(paths, out_path, fps)
        print(
            f"    video: {os.path.basename(out_path)} "
            f"{len(paths)} frames, {os.path.getsize(out_path) // 1024} KiB"
        )

    return {
        "stem": stem,
        "name": scene["name"],
        "description": scene["description"],
        "location": indexed["log"][scene["log_token"]]["location"],
        "frames": len(samples),
        "first_frame": frame_offset,
        "last_frame": frame_offset + len(samples) - 1,
        "first_time": round(time_offset, 2),
        "last_time": round(time_s, 2),
        "detections": len(table),
        "duration": round(duration, 2),
    }


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------


def numerical(description, decimal=2):
    return {"description": description, "decimal": decimal, "type": "numerical"}


def categorical(description):
    return {"description": description, "type": "categorical"}


def build_manifest():
    curve_suffixes = [f".{channel.lower()}.h5" for channel in RADAR_CHANNELS]
    curve_suffixes.append(".lidar.h5")

    return {
        "manifest_version": 2,
        "name": "nuScenes mini",
        "table": {
            "slider": "Frame",
            "x_3d": "X",
            "y_3d": "Y",
            "z_3d": "Z",
            "x_ref": "None",
            "y_ref": "None",
            "z_ref": "None",
            "time_unit": "s",
            "suffix": ".parquet",
            "keys": {
                "X": numerical("East (m)"),
                "Y": numerical("North (m)"),
                "Z": numerical("Up (m)"),
                "Range": numerical("Range (m)", 1),
                "Azimuth": numerical("Azimuth (deg)", 1),
                "RCS": numerical("RCS (dBsm)", 1),
                "Range_Rate": numerical("Range rate (m/s)"),
                "Range_Rate_Comp": numerical("Range rate, compensated (m/s)"),
                "Speed": numerical("Speed (m/s)"),
                "Time": numerical("Time (s)"),
                "Frame": numerical("Frame", 0),
                "Sensor": categorical("Radar"),
                "Dyn_Prop": categorical("Dynamic property"),
                "Ambig_State": categorical("Ambiguity state"),
                "False_Alarm_Prob": categorical("False alarm probability"),
                "Valid": categorical("Validity"),
            },
        },
        "cloud": {
            "format": "hdf5",
            "suffix": ".cloud.h5",
            "columns": ["x", "y", "z"],
            "decimation": {
                "method": "voxel+budget",
                "voxel_size": VOXEL_SIZE,
                "max_points": POINT_BUDGET,
                "coord_decimals": 2,
            },
            "display": {"color": "#8d99ae", "size": 1.0, "opacity": 0.25, "name": "LIDAR_TOP"},
        },
        "curve": {
            "format": "hdf5",
            "suffix": curve_suffixes,
            "plots": [
                {
                    "id": "range_profile",
                    "label": "Range Profile",
                    "x": {"label": "Range (m)"},
                    "y_label": "RCS (dBsm)",
                    "traces": [
                        {"name": "rcs_peak", "label": "Peak RCS", "color": "#4c9be8", "width": 2},
                        {"name": "rcs_mean", "label": "Mean RCS", "color": "#e8734c", "dash": "dash"},
                    ],
                },
                {
                    "id": "range_rate",
                    "label": "Range Rate",
                    "x": {"label": "Range (m)"},
                    "y_label": "Range rate (m/s)",
                    "traces": [
                        {"name": "rate_measured", "label": "Measured", "color": "#5cb85c", "width": 2},
                        {"name": "rate_compensated", "label": "Ego-motion compensated", "color": "#e8c34c", "dash": "dash"},
                        {"name": "rate_zero", "label": "Stationary", "color": "#8d99ae", "dash": "dot", "width": 1},
                    ],
                },
                {
                    "id": "lidar_range",
                    "label": "Lidar Range Density",
                    "x": {"label": "Range (m)"},
                    "y_label": "Returns per 2 m bin",
                    "traces": [
                        {"name": "returns_all", "label": "All returns", "color": "#4c9be8", "width": 2},
                        {"name": "returns_above_ground", "label": "Above 0.5 m", "color": "#c678dd", "dash": "dash"},
                    ],
                },
                {
                    "id": "lidar_height",
                    "label": "Lidar Height Profile",
                    "x": {"label": "Height above ego ground (m)"},
                    "y_label": "Returns per 0.25 m bin",
                    "traces": [
                        {"name": "height_all", "label": "Returns", "color": "#4cd4e8", "width": 2}
                    ],
                },
            ],
        },
        "image": {"format": "mp4", "suffix": [".mp4"]},
        "reference": {
            "suffix": ".reference.parquet",
            "shape": "mesh",
            "name": "Ego Vehicle",
            "color": "#4c9ffe",
            "opacity": 0.3,
            "edge_color": "#7fc4ff",
            "edge_width": 2,
            "columns": {
                "frame": "frame",
                "x": "x",
                "y": "y",
                "z": "z",
                "yaw": "yaw",
                "pitch": "pitch",
                "roll": "roll",
            },
            # Renault Zoe footprint, in meters relative to the rear-axle origin
            # nuScenes poses are given at: 4.084 long, 1.730 wide, 1.562 tall.
            # Nose toward +x, which is where yaw=0 points.
            "vertices": [
                [-1.09, -0.865, 0.0], [2.99, -0.865, 0.0], [2.99, 0.865, 0.0], [-1.09, 0.865, 0.0],
                [-1.09, -0.865, 1.05], [1.60, -0.865, 1.05], [1.60, 0.865, 1.05], [-1.09, 0.865, 1.05],
                [-0.75, -0.75, 1.56], [1.05, -0.75, 1.56], [1.05, 0.75, 1.56], [-0.75, 0.75, 1.56],
            ],
            "faces": [
                [0, 1, 2], [0, 2, 3],
                [0, 1, 5], [0, 5, 4],
                [1, 2, 6], [1, 6, 5],
                [2, 3, 7], [2, 7, 6],
                [3, 0, 4], [3, 4, 7],
                [4, 5, 9], [4, 9, 8],
                [5, 6, 10], [5, 10, 9],
                [6, 7, 11], [6, 11, 10],
                [7, 4, 8], [7, 8, 11],
                [8, 9, 10], [8, 10, 11],
            ],
            "edges": [
                [0, 1], [1, 2], [2, 3], [3, 0],
                [4, 5], [5, 6], [6, 7], [7, 4],
                [8, 9], [9, 10], [10, 11], [11, 8],
                [0, 4], [1, 5], [2, 6], [3, 7],
                [4, 8], [5, 9], [6, 10], [7, 11],
            ],
        },
    }


# --------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="nuScenes dataroot")
    parser.add_argument("--version", default="v1.0-mini")
    parser.add_argument("--out", required=True, help="case folder to write")
    parser.add_argument("--scenes", nargs="+", required=True)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    tables, indexed = load_tables(args.root, args.version)
    keyframes = sample_data_by_sample(tables, indexed)

    by_name = {scene["name"]: scene for scene in tables["scene"]}
    missing = [name for name in args.scenes if name not in by_name]
    if missing:
        sys.exit(f"unknown scenes: {missing}; available: {sorted(by_name)}")

    # Numbered end to end, in the order the file picker lists them, so scrubbing
    # from the last frame of one log into the first of the next is a continuous
    # count rather than a jump back to zero. It also means a frame id belongs to
    # exactly one log in the case folder -- which is what keeps a cache keyed on
    # frame id from quietly serving one log's data while another is selected.
    frame_offset = 0
    time_offset = 0.0
    summaries = []
    for name in sorted(args.scenes):
        summary = build_scene(
            args.root,
            args.version,
            args.out,
            by_name[name],
            tables,
            indexed,
            keyframes,
            frame_offset=frame_offset,
            time_offset=time_offset,
        )
        summaries.append(summary)
        frame_offset = summary["last_frame"] + 1
        # One frame interval of gap, so the logs abut rather than overlap.
        time_offset = summary["last_time"] + FRAME_INTERVAL

    manifest_path = os.path.join(args.out, "info.json")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(build_manifest(), handle, indent=4)

    print("\nsummary:")
    for summary in summaries:
        print(
            f"  {summary['stem']:12s} frames {summary['first_frame']:3d}-"
            f"{summary['last_frame']:3d}  t {summary['first_time']:7.2f}-"
            f"{summary['last_time']:7.2f}s  {summary['detections']:6d} detections"
            f"  {summary['location']}"
        )


if __name__ == "__main__":
    main()
