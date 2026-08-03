"""Dataset Manifest (info.json v2)

The manifest describes a *case* -- a folder that may hold many logs -- and
nothing about any individual log. It declares:

- the radar column metadata (description / decimal / type) driving the filter UI
- the filename suffixes that associate a log's sidecars with it
- per-sensor calibration, so overlaid point clouds share a reference frame
- fixed lidar backdrop styling and the 1D threshold plot definitions

Two things it deliberately does **not** declare:

- **The frame index.** Frame ids and timestamps are derived from the Parquet
  data (see :mod:`dataio.frames`), so a manifest cannot drift out of sync with
  the log it describes.
- **Per-log file lists.** Logs live side by side in the case folder and are
  associated by basename::

      MyCase/
      ├── info.json
      ├── drive_01.parquet          radar point cloud
      ├── drive_01.lidar.h5         lidar backdrop
      ├── drive_01.threshold.h5     threshold maps
      ├── drive_01.mp4              camera
      ├── drive_01.rear.mp4         second camera stream
      └── drive_02.parquet          another log, same conventions

  Adding a log is dropping files in the folder; no manifest edit is needed.

A v1 ``info.json`` (no ``manifest_version``) is still accepted and upgraded in
memory to a radar-only v2 manifest, so existing datasets keep working untouched.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional

import json
import os

from dataio.calibration import Calibration

MANIFEST_VERSION = 2
MANIFEST_NAME = "info.json"

# Keys a v1 info.json carries at the top level; these move under "radar" in v2.
_V1_RADAR_KEYS = (
    "slider",
    "x_3d",
    "y_3d",
    "z_3d",
    "x_ref",
    "y_ref",
    "z_ref",
    "keys",
)

# Default filename suffixes associating a log's sidecars with its radar table.
DEFAULT_RADAR_SUFFIX = ".parquet"
DEFAULT_LIDAR_SUFFIX = ".lidar.h5"
DEFAULT_THRESHOLD_SUFFIX = ".threshold.h5"
DEFAULT_CAMERA_SUFFIX = ".mp4"

DEFAULT_LIDAR_PATTERN = "/frames/{frame_id}"
DEFAULT_THRESHOLD_PATTERN = "/frames/{frame_id}/{name}"

# Fallback trace colors, used in order for traces that declare none.
DEFAULT_TRACE_COLORS = (
    "#4c9be8",
    "#e8734c",
    "#5cb85c",
    "#c678dd",
    "#e8c34c",
    "#4cd4e8",
)

# Fixed lidar backdrop styling. Lidar has no runtime UI controls by design, so
# these live in the manifest (or fall back to these defaults) rather than
# being wired to dropdowns.
DEFAULT_LIDAR_DISPLAY = {
    "color": "#8d99ae",
    "size": 1.2,
    "opacity": 0.35,
    "name": "Lidar",
}


class ManifestError(Exception):
    """Raised when a manifest is missing, malformed, or internally inconsistent."""


def log_stem(file_name: str, radar_suffix: str = DEFAULT_RADAR_SUFFIX) -> str:
    """
    Reduce a radar filename to the stem its sidecars are keyed on.

    Args:
        file_name: Radar file name or path.
        radar_suffix: Radar file suffix to strip.

    Returns:
        Basename with the radar suffix removed. Legacy ``.csv``/``.pkl`` names
        also reduce correctly so v1 datasets share this code path.
    """
    base = os.path.basename(file_name)
    for suffix in (radar_suffix, ".parquet", ".csv", ".pkl"):
        if suffix and base.lower().endswith(suffix.lower()):
            return base[: -len(suffix)]
    return os.path.splitext(base)[0]


class Manifest:
    """Parsed dataset manifest. Sidecar paths resolve per log, from its stem."""

    def __init__(
        self, raw: Dict[str, Any], case_dir: str, source_version: int = MANIFEST_VERSION
    ) -> None:
        """
        Args:
            raw: Decoded manifest dictionary (already upgraded to v2 shape).
            case_dir: Directory the manifest was loaded from; all relative paths
                inside the manifest resolve against it.
            source_version: Schema version of the file on disk. Tracked so
                :meth:`save` writes back in the shape the dataset already uses
                instead of silently upgrading a v1 file.
        """
        self.raw = raw
        self.case_dir = case_dir
        self.source_version = source_version

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, case_dir: str) -> "Manifest":
        """
        Load ``info.json`` from a case directory.

        Args:
            case_dir: Directory containing ``info.json``.

        Returns:
            Manifest instance, upgraded to v2 shape if the file was v1.

        Raises:
            ManifestError: If the file is missing or cannot be decoded.
        """
        path = os.path.join(case_dir, MANIFEST_NAME)
        if not os.path.exists(path):
            raise ManifestError(f"No {MANIFEST_NAME} found in {case_dir}")

        try:
            with open(path, "r", encoding="utf-8") as read_file:
                raw = json.load(read_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError(f"Could not read {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ManifestError(f"{path} must contain a JSON object")

        source_version = MANIFEST_VERSION if raw.get("manifest_version") else 1
        return cls(upgrade_to_v2(raw), case_dir, source_version=source_version)

    # ------------------------------------------------------------------
    # Top-level blocks
    # ------------------------------------------------------------------

    @property
    def version(self) -> int:
        """Manifest schema version."""
        return int(self.raw.get("manifest_version", MANIFEST_VERSION))

    @property
    def name(self) -> str:
        """Human-readable dataset name; defaults to the case directory name."""
        return self.raw.get("name") or os.path.basename(os.path.normpath(self.case_dir))

    @property
    def radar(self) -> Dict[str, Any]:
        """The ``radar`` block (always present after upgrade)."""
        return self.raw.get("radar", {})

    @property
    def lidar(self) -> Optional[Dict[str, Any]]:
        """The ``lidar`` block, or None when the dataset declares no lidar."""
        return self.raw.get("lidar")

    @property
    def threshold(self) -> Optional[Dict[str, Any]]:
        """The ``threshold`` block, or None when the dataset declares no maps."""
        return self.raw.get("threshold")

    @property
    def camera(self) -> Optional[Dict[str, Any]]:
        """The ``camera`` block, or None when the dataset declares no camera."""
        return self.raw.get("camera")

    @property
    def frame_key(self) -> str:
        """Column in the radar table used as the frame/slider key."""
        return self.radar.get("slider", "Frame")

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    @property
    def radar_suffix(self) -> str:
        """Filename suffix identifying a radar table."""
        return self.radar.get("suffix", DEFAULT_RADAR_SUFFIX)

    def stem_of(self, file_name: str) -> str:
        """
        Reduce a radar filename to this dataset's log stem.

        Args:
            file_name: Radar file name or path.

        Returns:
            Stem used to locate that log's sidecars.
        """
        return log_stem(file_name, self.radar_suffix)

    def logs(self) -> List[str]:
        """
        List the log stems present in the case directory.

        Returns:
            Sorted stems of every radar table found. Empty when the directory is
            unreadable.
        """
        try:
            entries = os.listdir(self.case_dir)
        except OSError:
            return []

        suffix = self.radar_suffix.lower()
        return sorted(
            self.stem_of(name) for name in entries if name.lower().endswith(suffix)
        )

    def _sidecar_path(self, stem: str, suffix: str) -> str:
        """
        Build a sidecar path for one log.

        Args:
            stem: Log stem.
            suffix: Sidecar filename suffix.

        Returns:
            Absolute path to the sidecar (which may not exist).
        """
        return os.path.normpath(os.path.join(self.case_dir, f"{stem}{suffix}"))

    # ------------------------------------------------------------------
    # Radar
    # ------------------------------------------------------------------

    @property
    def keys(self) -> Dict[str, Dict[str, Any]]:
        """Radar column metadata driving the filter UI and hover text."""
        return self.radar.get("keys", {})

    def radar_path(self, stem: str) -> str:
        """
        Path to one log's radar table.

        Args:
            stem: Log stem.

        Returns:
            Absolute path to the Parquet file.
        """
        return self._sidecar_path(stem, self.radar_suffix)

    def radar_calibration(self) -> Calibration:
        """Extrinsics for the radar point cloud."""
        return Calibration.from_dict(self.radar.get("calibration"))

    # ------------------------------------------------------------------
    # Lidar
    # ------------------------------------------------------------------

    @property
    def lidar_suffix(self) -> str:
        """Filename suffix identifying a lidar sidecar."""
        return (self.lidar or {}).get("suffix", DEFAULT_LIDAR_SUFFIX)

    def lidar_path(self, stem: str) -> Optional[str]:
        """
        Path to one log's lidar sidecar.

        Args:
            stem: Log stem.

        Returns:
            Absolute path, or None when the dataset declares no lidar.
        """
        if not self.lidar:
            return None
        return self._sidecar_path(stem, self.lidar_suffix)

    def has_lidar(self, stem: str) -> bool:
        """
        Whether a given log has a lidar backdrop on disk.

        Args:
            stem: Log stem.

        Returns:
            True when the sidecar is declared and present.
        """
        path = self.lidar_path(stem)
        return bool(path and os.path.exists(path))

    def lidar_dataset_pattern(self) -> str:
        """HDF5 dataset path pattern for a lidar frame."""
        return (self.lidar or {}).get("dataset_pattern", DEFAULT_LIDAR_PATTERN)

    def lidar_calibration(self) -> Calibration:
        """Extrinsics for the lidar point cloud."""
        return Calibration.from_dict((self.lidar or {}).get("calibration"))

    def lidar_display(self) -> Dict[str, Any]:
        """
        Fixed styling for the lidar backdrop trace.

        Returns:
            Dict with ``color``, ``size``, ``opacity`` and ``name``, merging
            manifest overrides over the module defaults.
        """
        display = dict(DEFAULT_LIDAR_DISPLAY)
        display.update((self.lidar or {}).get("display") or {})
        return display

    # ------------------------------------------------------------------
    # Threshold maps
    # ------------------------------------------------------------------

    @property
    def threshold_suffix(self) -> str:
        """Filename suffix identifying a threshold sidecar."""
        return (self.threshold or {}).get("suffix", DEFAULT_THRESHOLD_SUFFIX)

    def threshold_path(self, stem: str) -> Optional[str]:
        """
        Path to one log's threshold sidecar.

        Args:
            stem: Log stem.

        Returns:
            Absolute path, or None when the dataset declares no threshold maps.
        """
        if not self.threshold:
            return None
        return self._sidecar_path(stem, self.threshold_suffix)

    def has_threshold(self, stem: str) -> bool:
        """
        Whether a given log has threshold maps on disk.

        Args:
            stem: Log stem.

        Returns:
            True when the sidecar is declared and present.
        """
        path = self.threshold_path(stem)
        return bool(path and os.path.exists(path))

    def threshold_plots(self) -> List[Dict[str, Any]]:
        """
        Normalized threshold plot definitions from the manifest.

        Threshold series are 1D and a single file holds many of them, so what
        goes on which plot -- and how each curve is drawn -- is declared rather
        than guessed. Each plot definition looks like::

            {
              "id": "range_profile",
              "label": "Range Profile",
              "x": {"dataset": "/axes/range", "label": "Range (m)"},
              "y_label": "Magnitude (dB)",
              "y_range": [-120, -20],
              "traces": [
                {"name": "signal",    "label": "Signal"},
                {"name": "threshold", "label": "CFAR Threshold",
                 "color": "#e8734c", "dash": "dash"}
              ]
            }

        A trace's ``name`` fills the ``{name}`` placeholder in the plot's
        dataset pattern; an explicit ``dataset`` overrides that entirely.

        Returns:
            List of plot definitions with defaults filled in. Empty when the
            dataset declares no threshold plots.
        """
        block = self.threshold or {}
        default_pattern = block.get("dataset_pattern", DEFAULT_THRESHOLD_PATTERN)

        plots = []
        for index, plot in enumerate(block.get("plots") or []):
            if not isinstance(plot, dict):
                continue

            plot_id = plot.get("id") or f"plot_{index}"
            pattern = plot.get("dataset_pattern", default_pattern)

            traces = []
            for position, trace in enumerate(plot.get("traces") or []):
                if isinstance(trace, str):
                    trace = {"name": trace}
                if not isinstance(trace, dict) or not (
                    trace.get("name") or trace.get("dataset")
                ):
                    continue

                name = trace.get("name", "")
                traces.append(
                    {
                        "name": name,
                        "label": trace.get("label", name),
                        "dataset": trace.get("dataset")
                        or pattern.replace("{name}", name),
                        "color": trace.get(
                            "color",
                            DEFAULT_TRACE_COLORS[position % len(DEFAULT_TRACE_COLORS)],
                        ),
                        "dash": trace.get("dash", "solid"),
                        "width": trace.get("width", 2),
                        "mode": trace.get("mode", "lines"),
                    }
                )

            x_axis = plot.get("x") or {}
            plots.append(
                {
                    "id": plot_id,
                    "label": plot.get("label", plot_id),
                    "x_dataset": x_axis.get("dataset", ""),
                    "x_label": x_axis.get("label", ""),
                    "x_range": x_axis.get("range"),
                    "y_label": plot.get("y_label", ""),
                    "y_range": plot.get("y_range"),
                    "log_y": bool(plot.get("log_y", False)),
                    "traces": traces,
                }
            )

        return plots

    def threshold_plot(self, plot_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up one normalized threshold plot definition.

        Args:
            plot_id: Plot identifier.

        Returns:
            The plot definition, or None when no plot has that id.
        """
        return next((p for p in self.threshold_plots() if p["id"] == plot_id), None)

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------

    @property
    def camera_suffix(self) -> str:
        """Filename suffix identifying a camera stream."""
        return (self.camera or {}).get("suffix", DEFAULT_CAMERA_SUFFIX)

    def camera_streams(self, stem: str) -> List[Dict[str, Any]]:
        """
        Discover a log's camera streams on disk.

        Streams are found rather than declared: ``<stem>.mp4`` is the log's
        default stream, and ``<stem>.<id>.mp4`` adds a named one, so a second
        camera is just another file in the folder.

        Args:
            stem: Log stem.

        Returns:
            List of stream dicts with ``id``, ``label``, and absolute ``file``,
            sorted with the default stream first.
        """
        if not self.camera or not stem:
            return []

        suffix = self.camera_suffix
        try:
            entries = os.listdir(self.case_dir)
        except OSError:
            return []

        streams = []
        for name in entries:
            if not name.startswith(stem) or not name.lower().endswith(suffix.lower()):
                continue

            middle = name[len(stem) : -len(suffix)]
            if middle == "":
                stream_id = "camera"
                label = "Camera"
            elif middle.startswith("."):
                stream_id = middle[1:]
                label = stream_id.replace("_", " ").title()
            else:
                # Belongs to a different log whose stem merely shares a prefix.
                continue

            streams.append(
                {
                    "id": stream_id,
                    "label": label,
                    "file": os.path.join(self.case_dir, name),
                }
            )

        return sorted(streams, key=lambda s: (s["id"] != "camera", s["id"]))

    def has_camera(self, stem: str) -> bool:
        """
        Whether a given log has at least one camera stream on disk.

        Args:
            stem: Log stem.

        Returns:
            True when a stream file exists.
        """
        return bool(self.camera_streams(stem))

    # ------------------------------------------------------------------
    # Back-compat and persistence
    # ------------------------------------------------------------------

    def legacy_config(self) -> Dict[str, Any]:
        """
        Project the manifest down to the flat v1 config shape.

        The existing filter / 3D / 2D / stats callbacks read ``config["keys"]``,
        ``config["slider"]``, ``config["x_3d"]`` and friends. Returning that
        shape keeps every one of them working unchanged against a v2 manifest.

        Returns:
            Flat dictionary in v1 ``info.json`` form.
        """
        config = {key: self.radar[key] for key in _V1_RADAR_KEYS if key in self.radar}
        config.setdefault("keys", {})
        config.setdefault("slider", "Frame")
        return config

    def update_radar_view(self, values: Dict[str, Any]) -> None:
        """
        Update the radar axis/slider selections held in the manifest.

        Args:
            values: Subset of ``slider``, ``x_3d``, ``y_3d``, ``z_3d``,
                ``x_ref``, ``y_ref``, ``z_ref``. Unknown keys are ignored.
        """
        radar = self.raw.setdefault("radar", {})
        for key in _V1_RADAR_KEYS:
            if key in values and key != "keys":
                radar[key] = values[key]

    def save(self) -> str:
        """
        Write the manifest back to its case directory.

        Writing preserves the on-disk schema version: a v1 dataset stays a flat
        v1 file, a v2 dataset keeps every block it declared. This matters
        because the 3D view persists axis selections on every change -- dumping
        the flat projection over a v2 file would destroy the lidar, threshold,
        and camera blocks.

        Returns:
            Path written.
        """
        payload = self.legacy_config() if self.source_version == 1 else self.raw

        path = os.path.join(self.case_dir, MANIFEST_NAME)
        with open(path, "w", encoding="utf-8") as write_file:
            json.dump(payload, write_file, indent=4)
        return path


def upgrade_to_v2(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a decoded manifest to the v2 shape.

    A v1 manifest keeps its radar column metadata but is nested under a
    ``radar`` block; it declares no lidar, threshold, or camera sidecars.

    Args:
        raw: Decoded manifest dictionary.

    Returns:
        Dictionary in v2 shape. Returns ``raw`` unchanged when already v2.
    """
    if raw.get("manifest_version"):
        return raw

    radar = {key: raw[key] for key in _V1_RADAR_KEYS if key in raw}
    return {
        "manifest_version": MANIFEST_VERSION,
        "name": raw.get("name"),
        "radar": radar,
    }


def load_manifest(case_dir: str) -> Manifest:
    """
    Load a dataset manifest from a case directory.

    Args:
        case_dir: Directory containing ``info.json``.

    Returns:
        Manifest instance.

    Raises:
        ManifestError: If the manifest is missing or malformed.
    """
    return Manifest.load(case_dir)
