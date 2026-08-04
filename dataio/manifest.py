"""Dataset Manifest (info.json v2)

The manifest describes a *case* -- a folder that may hold many logs -- and
nothing about any individual log. It declares:

- the table's column metadata (description / decimal / type) driving the filter UI
- the filename suffixes that associate a log's sidecars with it
- per-sensor calibration, so overlaid point clouds share a reference frame
- fixed point-cloud backdrop styling and the 1D curve plot definitions
- how the reference overlay is drawn -- a plain marker, or a box scaled to the
  thing it stands for (see :func:`normalize_reference_display`)

Two things it deliberately does **not** declare:

- **The frame index.** Frame ids and timestamps are derived from the Parquet
  data (see :mod:`dataio.frames`), so a manifest cannot drift out of sync with
  the log it describes.
- **Per-log file lists.** Logs live side by side in the case folder and are
  associated by basename::

      MyCase/
      ├── info.json
      ├── drive_01.parquet          table (the filterable point cloud)
      ├── drive_01.cloud.h5         point-cloud backdrop
      ├── drive_01.curve.h5         1D curves
      ├── drive_01.sensor_2.h5      curves from a second sensor
      ├── drive_01.mp4              image stream
      ├── drive_01.rear.mp4         a second image stream
      └── drive_02.parquet          another log, same conventions

  Adding a log is dropping files in the folder; no manifest edit is needed.

A v1 ``info.json`` (no ``manifest_version``) is still accepted and upgraded in
memory to a table-only v2 manifest, so existing datasets keep working untouched.

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

# Keys a v1 info.json carries at the top level; these move under "table" in v2.
_V1_TABLE_KEYS = (
    "slider",
    "x_3d",
    "y_3d",
    "z_3d",
    "x_ref",
    "y_ref",
    "z_ref",
    "keys",
    "time_unit",
)

# Unit of the table's `Time` column, as seconds per stored unit.
DEFAULT_TIME_UNIT = "s"
TIME_UNIT_SCALES = {
    "s": 1.0,
    "sec": 1.0,
    "second": 1.0,
    "seconds": 1.0,
    "ms": 1e-3,
    "msec": 1e-3,
    "millisecond": 1e-3,
    "milliseconds": 1e-3,
    "us": 1e-6,
    "usec": 1e-6,
    "microsecond": 1e-6,
    "microseconds": 1e-6,
    "ns": 1e-9,
    "nanosecond": 1e-9,
    "nanoseconds": 1e-9,
}

# Default filename suffixes associating a log's sidecars with its table.
DEFAULT_TABLE_SUFFIX = ".parquet"
DEFAULT_CLOUD_SUFFIX = ".cloud.h5"
DEFAULT_CURVE_SUFFIX = ".curve.h5"
# mp4 first: a stream present in both containers is served without a transcode.
DEFAULT_IMAGE_SUFFIXES = (".mp4", ".avi")
DEFAULT_IMAGE_SUFFIX = DEFAULT_IMAGE_SUFFIXES[0]

DEFAULT_CLOUD_PATTERN = "/frame_{frame_id}"
DEFAULT_CURVE_PATTERN = "/frame_{frame_id}/{name}"

# Fallback trace colors, used in order for traces that declare none.
DEFAULT_TRACE_COLORS = (
    "#4c9be8",
    "#e8734c",
    "#5cb85c",
    "#c678dd",
    "#e8c34c",
    "#4cd4e8",
)

# Fixed backdrop styling. The cloud has no runtime UI controls by design, so
# these live in the manifest (or fall back to these defaults) rather than
# being wired to dropdowns.
DEFAULT_CLOUD_DISPLAY = {
    "color": "#8d99ae",
    "size": 1.2,
    "opacity": 0.35,
    "name": "Point Cloud",
}

# Reference marker styling. *Where* the reference sits is picked in the 3D view
# (the x/y/z ref columns, which the user can change per session); *what it looks
# like* is a property of the dataset, so it is declared here. The defaults
# reproduce the plain white dot this was before the block existed, which is why
# a manifest that says nothing about the reference draws exactly as it always
# did.
REFERENCE_SHAPES = ("marker", "box")

DEFAULT_REFERENCE_DISPLAY = {
    "name": "Host Vehicle",
    "shape": "marker",
    "color": "#ffffff",
    "opacity": 1.0,
    # marker only
    "size": 6,
    "symbol": "circle",
    "line_color": "#000000",
    "line_width": 2,
}

# Box-only defaults. A solid box at full opacity would bury every detection
# inside it, so the box is translucent where the dot is not -- hence a separate
# table rather than one flat set of defaults.
DEFAULT_REFERENCE_BOX = {
    "opacity": 0.35,
    # Full extent along the plot's x, y and z axes, in data units. Dimensions
    # are per-axis rather than length/width/height because which physical
    # quantity each axis carries is the user's choice, not the manifest's.
    "dimensions": [1.9, 4.7, 1.5],
    # Box center relative to the reference point. The reference column usually
    # marks a sensor or the rear axle, not the middle of the vehicle.
    "offset": [0.0, 0.0, 0.0],
    "edges": True,
    # None means "follow `color`".
    "edge_color": None,
    "edge_width": 2,
}


class ManifestError(Exception):
    """Raised when a manifest is missing, malformed, or internally inconsistent."""


def _vec3(value: Any, fallback: List[float]) -> List[float]:
    """
    Coerce a manifest 3-vector to three floats.

    Accepts either the list form used by ``calibration`` (``[x, y, z]``) or a
    mapping (``{"x": .., "y": .., "z": ..}``), since both read naturally in a
    hand-written manifest.

    Args:
        value: Raw value from the manifest.
        fallback: Value to use when ``value`` is missing or unusable.

    Returns:
        List of three floats.
    """
    if isinstance(value, dict):
        value = [value.get("x"), value.get("y"), value.get("z")]

    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return list(fallback)

    try:
        return [float(component) for component in value]
    except (TypeError, ValueError):
        return list(fallback)


def normalize_reference_display(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Fill in a manifest ``reference`` block.

    Args:
        raw: The block as authored, or None when the dataset declares none.

    Returns:
        Dict carrying every key the renderer reads. An unknown ``shape`` falls
        back to ``marker`` rather than raising: a typo in a cosmetic field
        should not cost the user their reference point.
    """
    raw = raw or {}

    display = dict(DEFAULT_REFERENCE_DISPLAY)
    shape = str(raw.get("shape", display["shape"])).lower()
    if shape not in REFERENCE_SHAPES:
        shape = DEFAULT_REFERENCE_DISPLAY["shape"]

    if shape == "box":
        display.update(DEFAULT_REFERENCE_BOX)

    display.update({key: value for key, value in raw.items() if key != "shape"})
    display["shape"] = shape

    if shape == "box":
        dimensions = _vec3(display["dimensions"], DEFAULT_REFERENCE_BOX["dimensions"])
        display["dimensions"] = [abs(size) for size in dimensions]
        display["offset"] = _vec3(display["offset"], DEFAULT_REFERENCE_BOX["offset"])
        display["edges"] = bool(display["edges"])
        display["edge_color"] = display["edge_color"] or display["color"]

    return display


def _suffix_source_id(suffix: str) -> str:
    """
    Name a source after the suffix that matched its whole filename.

    ``os.path.splitext`` is no help here: it reads a leading dot as a hidden
    filename, so it would call ``".sensor_1.h5"`` extensionless. Stripping that
    dot first leaves the part that actually distinguishes one sidecar from
    another.

    Args:
        suffix: Filename suffix from the manifest, e.g. ``".sensor_1.h5"``.

    Returns:
        The identifying stem -- ``sensor_1`` here, ``curve`` for the default
        ``".curve.h5"``. A bare extension like ``".h5"`` distinguishes
        nothing, so it falls back to ``curve``.
    """
    body = suffix.lstrip(".")
    if "." not in body:
        return "curve"
    return os.path.splitext(body)[0] or "curve"


def log_stem(file_name: str, table_suffix: str = DEFAULT_TABLE_SUFFIX) -> str:
    """
    Reduce a table filename to the stem its sidecars are keyed on.

    Args:
        file_name: Table file name or path.
        table_suffix: Table file suffix to strip.

    Returns:
        Basename with the table suffix removed. Legacy ``.csv``/``.pkl`` names
        also reduce correctly so v1 datasets share this code path.
    """
    base = os.path.basename(file_name)
    for suffix in (table_suffix, ".parquet", ".csv", ".pkl"):
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
    def name(self) -> str:
        """Human-readable dataset name; defaults to the case directory name."""
        return self.raw.get("name") or os.path.basename(os.path.normpath(self.case_dir))

    @property
    def table(self) -> Dict[str, Any]:
        """The ``table`` block (always present after upgrade)."""
        return self.raw.get("table", {})

    @property
    def cloud(self) -> Optional[Dict[str, Any]]:
        """The ``cloud`` block, or None when the dataset declares no point cloud."""
        return self.raw.get("cloud")

    @property
    def curve(self) -> Optional[Dict[str, Any]]:
        """The ``curve`` block, or None when the dataset declares no curves."""
        return self.raw.get("curve")

    @property
    def image(self) -> Optional[Dict[str, Any]]:
        """The ``image`` block, or None when the dataset declares no images."""
        return self.raw.get("image")

    @property
    def reference(self) -> Optional[Dict[str, Any]]:
        """The ``reference`` block as authored, or None when it is absent."""
        return self.raw.get("reference")

    @property
    def frame_key(self) -> str:
        """Column in the table used as the frame/slider key."""
        return self.table.get("slider", "Frame")

    @property
    def time_unit(self) -> str:
        """
        Unit of the table's ``Time`` column.

        Timestamps drive the capture rate and the image seek, so the unit has
        to be known rather than guessed -- a log timestamped in milliseconds
        read as seconds yields a 0.02 Hz capture rate and a video that never
        moves. Declared rather than sniffed because the only honest signal is
        the exporter's intent.
        """
        return str(self.table.get("time_unit", DEFAULT_TIME_UNIT)).lower()

    @property
    def time_scale(self) -> float:
        """
        Factor converting the ``Time`` column to seconds.

        Returns:
            Seconds per stored unit; 1.0 for an unrecognised declaration, which
            keeps a typo from silently rescaling the whole frame index.
        """
        return TIME_UNIT_SCALES.get(self.time_unit, 1.0)

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    @property
    def table_suffix(self) -> str:
        """Filename suffix identifying a table."""
        return self.table.get("suffix", DEFAULT_TABLE_SUFFIX)

    def stem_of(self, file_name: str) -> str:
        """
        Reduce a table filename to this dataset's log stem.

        Args:
            file_name: Table file name or path.

        Returns:
            Stem used to locate that log's sidecars.
        """
        return log_stem(file_name, self.table_suffix)

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
    # Table
    # ------------------------------------------------------------------

    @property
    def keys(self) -> Dict[str, Dict[str, Any]]:
        """Column metadata driving the filter UI and hover text."""
        return self.table.get("keys", {})

    # ------------------------------------------------------------------
    # Cloud
    # ------------------------------------------------------------------

    @property
    def cloud_suffix(self) -> str:
        """Filename suffix identifying a point-cloud sidecar."""
        return (self.cloud or {}).get("suffix", DEFAULT_CLOUD_SUFFIX)

    def cloud_path(self, stem: str) -> Optional[str]:
        """
        Path to one log's point-cloud sidecar.

        Args:
            stem: Log stem.

        Returns:
            Absolute path, or None when the dataset declares no cloud.
        """
        if not self.cloud:
            return None
        return self._sidecar_path(stem, self.cloud_suffix)

    def has_cloud(self, stem: str) -> bool:
        """
        Whether a given log has a point-cloud backdrop on disk.

        Args:
            stem: Log stem.

        Returns:
            True when the sidecar is declared and present.
        """
        path = self.cloud_path(stem)
        return bool(path and os.path.exists(path))

    def cloud_dataset_pattern(self) -> str:
        """HDF5 dataset path pattern for one cloud frame."""
        return (self.cloud or {}).get("dataset_pattern", DEFAULT_CLOUD_PATTERN)

    def cloud_calibration(self) -> Calibration:
        """Extrinsics for the point cloud."""
        return Calibration.from_dict((self.cloud or {}).get("calibration"))

    def cloud_display(self) -> Dict[str, Any]:
        """
        Fixed styling for the point-cloud backdrop trace.

        Returns:
            Dict with ``color``, ``size``, ``opacity`` and ``name``, merging
            manifest overrides over the module defaults.
        """
        display = dict(DEFAULT_CLOUD_DISPLAY)
        display.update((self.cloud or {}).get("display") or {})
        return display

    # ------------------------------------------------------------------
    # Curves
    # ------------------------------------------------------------------

    @property
    def curve_suffixes(self) -> List[str]:
        """
        Filename suffixes identifying a curve sidecar, in listing order.

        ``suffix`` may be a single string -- generic like ``".h5"`` or specific
        like the default ``".curve.h5"`` -- or a list naming each sidecar
        outright. See :meth:`curve_sources` for how the two forms differ.
        """
        declared = (self.curve or {}).get("suffix", DEFAULT_CURVE_SUFFIX)
        if isinstance(declared, str):
            return [declared]
        return [str(item) for item in declared] or [DEFAULT_CURVE_SUFFIX]

    def curve_dataset_pattern(self) -> str:
        """HDF5 dataset path pattern for one curve."""
        return (self.curve or {}).get("dataset_pattern", DEFAULT_CURVE_PATTERN)

    def curve_sources(self, stem: str) -> List[Dict[str, Any]]:
        """
        Discover a log's curve sidecars on disk.

        Sources are found rather than declared, the same way image streams are.
        ``suffix`` accepts either form:

        - One generic suffix, ``".h5"``, matches ``<stem><suffix>`` as the log's
          default source and ``<stem>.<id><suffix>`` as a named one. Dropping
          ``<stem>.sensor_6.h5`` in the folder adds a sixth sensor with no
          manifest edit.
        - A list, ``[".sensor_1.h5", ".sensor_2.h5", …]``, names the sidecars
          outright. Worth the typing when the folder holds ``.h5`` files that are
          *not* curves, or when the picker should list sensors in a
          particular order rather than alphabetically.

        Either way the source id is whatever distinguishes the file: the text
        between stem and suffix when the suffix is generic, and the suffix's own
        stem when it names the file outright -- so ``".sensor_1.h5"`` yields
        ``sensor_1`` and the default ``".curve.h5"`` yields ``curve``.

        Args:
            stem: Log stem.

        Returns:
            List of source dicts with ``id``, ``label``, and absolute ``file``,
            in discovery order: declared-suffix order first, then filename order
            within a suffix. A file matching more than one suffix is listed once,
            under the first that claimed it.
        """
        if not self.curve or not stem:
            return []

        try:
            entries = sorted(os.listdir(self.case_dir))
        except OSError:
            return []

        suffixes = self.curve_suffixes
        declared = {suffix.lower() for suffix in suffixes}

        # A suffix as generic as ".h5" would otherwise swallow the cloud
        # sidecar, which is a different kind of file entirely. A suffix the
        # dataset declared explicitly is never treated as someone else's.
        reserved = {
            other.lower()
            for other in (self.cloud_suffix, self.table_suffix)
            if other.lower() not in declared
        }

        sources: Dict[str, Dict[str, Any]] = {}
        for suffix in suffixes:
            lowered_suffix = suffix.lower()
            for name in entries:
                lowered = name.lower()
                if not name.startswith(stem) or not lowered.endswith(lowered_suffix):
                    continue
                if any(lowered.endswith(other) for other in reserved):
                    continue

                middle = name[len(stem) : -len(suffix)]
                if middle == "":
                    # The suffix names the file on its own, so it is what tells
                    # this source apart from its siblings.
                    source_id = _suffix_source_id(suffix)
                elif middle.startswith("."):
                    source_id = middle[1:]
                else:
                    # Belongs to a different log whose stem merely shares a prefix.
                    continue

                sources.setdefault(
                    source_id,
                    {
                        "id": source_id,
                        "label": source_id.replace("_", " ").title(),
                        "file": os.path.join(self.case_dir, name),
                    },
                )

        return list(sources.values())

    def curve_path(
        self, stem: str, source_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Path to one of a log's curve sidecars.

        Args:
            stem: Log stem.
            source_id: Source identifier from :meth:`curve_sources`. Defaults
                to the log's first source.

        Returns:
            Absolute path, or None when the dataset declares no curves
            or names a source this log does not have.
        """
        if not self.curve:
            return None

        sources = self.curve_sources(stem)
        if not sources:
            return None
        if source_id is None:
            return sources[0]["file"]

        match = next((s for s in sources if s["id"] == source_id), None)
        return match["file"] if match else None

    def has_curve(self, stem: str) -> bool:
        """
        Whether a given log has curves on disk.

        Args:
            stem: Log stem.

        Returns:
            True when at least one sidecar is declared and present.
        """
        return bool(self.curve_sources(stem))

    def curve_plots(self) -> List[Dict[str, Any]]:
        """
        Normalized curve plot definitions from the manifest.

        Curves are 1D and a single file holds many of them, so what
        goes on which plot -- and how each curve is drawn -- is declared rather
        than guessed. Each plot definition looks like::

            {
              "id": "range_profile",
              "label": "Range Profile",
              "x": {"label": "Range (m)"},
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

        ``x`` carries only a label: every series brings its own x column, so
        there is no shared axis for the plot to name.

        Returns:
            List of plot definitions with defaults filled in. Empty when the
            dataset declares no curve plots.
        """
        block = self.curve or {}
        default_pattern = block.get("dataset_pattern", DEFAULT_CURVE_PATTERN)

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
                    "x_label": x_axis.get("label", ""),
                    "x_range": x_axis.get("range"),
                    "y_label": plot.get("y_label", ""),
                    "y_range": plot.get("y_range"),
                    "log_y": bool(plot.get("log_y", False)),
                    "traces": traces,
                }
            )

        return plots

    def curve_plot(self, plot_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up one normalized curve plot definition.

        Args:
            plot_id: Plot identifier.

        Returns:
            The plot definition, or None when no plot has that id.
        """
        return next((p for p in self.curve_plots() if p["id"] == plot_id), None)

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    @property
    def image_suffixes(self) -> List[str]:
        """
        Filename suffixes identifying an image stream, in preference order.

        ``suffix`` may be a single string or a list. The default accepts the
        recorder's own container alongside mp4, because a log is dropped in the
        folder as it was recorded -- an ``.avi`` no browser can play is
        transcoded on the way out rather than being ignored here.
        """
        declared = (self.image or {}).get("suffix", DEFAULT_IMAGE_SUFFIXES)
        if isinstance(declared, str):
            return [declared]
        return [str(item) for item in declared] or list(DEFAULT_IMAGE_SUFFIXES)

    def image_streams(self, stem: str) -> List[Dict[str, Any]]:
        """
        Discover a log's image streams on disk.

        Streams are found rather than declared: ``<stem>.mp4`` is the log's
        default stream, and ``<stem>.<id>.mp4`` adds a named one, so a second
        second stream is just another file in the folder.

        Args:
            stem: Log stem.

        Returns:
            List of stream dicts with ``id``, ``label``, and absolute ``file``,
            sorted with the default stream first. When one stream is present in
            several containers, the earliest declared suffix wins -- a log
            shipped as both mp4 and avi serves the mp4 and skips the transcode.
        """
        if not self.image or not stem:
            return []

        try:
            entries = sorted(os.listdir(self.case_dir))
        except OSError:
            return []

        streams: Dict[str, Dict[str, Any]] = {}
        for suffix in self.image_suffixes:
            lowered_suffix = suffix.lower()
            for name in entries:
                if not name.startswith(stem) or not name.lower().endswith(
                    lowered_suffix
                ):
                    continue

                middle = name[len(stem) : -len(suffix)]
                if middle == "":
                    stream_id = "image"
                    label = "Image"
                elif middle.startswith("."):
                    stream_id = middle[1:]
                    label = stream_id.replace("_", " ").title()
                else:
                    # Belongs to a different log whose stem merely shares a prefix.
                    continue

                streams.setdefault(
                    stream_id,
                    {
                        "id": stream_id,
                        "label": label,
                        "file": os.path.join(self.case_dir, name),
                    },
                )

        return sorted(
            streams.values(), key=lambda s: (s["id"] != "image", s["id"])
        )

    def has_image(self, stem: str) -> bool:
        """
        Whether a given log has at least one image stream on disk.

        Args:
            stem: Log stem.

        Returns:
            True when a stream file exists.
        """
        return bool(self.image_streams(stem))

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
        config = {key: self.table[key] for key in _V1_TABLE_KEYS if key in self.table}
        config.setdefault("keys", {})
        config.setdefault("slider", "Frame")

        # Carried verbatim rather than normalized: this projection is also what
        # `save` writes back over a v1 file, and rewriting the user's manifest
        # with every default spelled out would be a surprising side effect of
        # changing an axis picker.
        if self.reference is not None:
            config["reference"] = self.reference

        return config

    def update_table_view(self, values: Dict[str, Any]) -> None:
        """
        Update the axis/slider selections held in the manifest.

        Args:
            values: Subset of ``slider``, ``x_3d``, ``y_3d``, ``z_3d``,
                ``x_ref``, ``y_ref``, ``z_ref``. Unknown keys are ignored.
        """
        table = self.raw.setdefault("table", {})
        for key in _V1_TABLE_KEYS:
            if key in values and key != "keys":
                table[key] = values[key]

    def save(self) -> str:
        """
        Write the manifest back to its case directory.

        Writing preserves the on-disk schema version: a v1 dataset stays a flat
        v1 file, a v2 dataset keeps every block it declared. This matters
        because the 3D view persists axis selections on every change -- dumping
        the flat projection over a v2 file would destroy the cloud, curve,
        and image blocks.

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

    A v1 manifest keeps its column metadata but is nested under a ``table``
    block; it declares no cloud, curve, or image sidecars.

    Args:
        raw: Decoded manifest dictionary.

    Returns:
        Dictionary in v2 shape. Returns ``raw`` unchanged when already v2.
    """
    if raw.get("manifest_version"):
        return raw

    table = {key: raw[key] for key in _V1_TABLE_KEYS if key in raw}
    upgraded = {
        "manifest_version": MANIFEST_VERSION,
        "name": raw.get("name"),
        "table": table,
    }

    # The reference block sits at the top level in both schemas, so a v1
    # dataset can style its reference without being migrated first.
    if raw.get("reference") is not None:
        upgraded["reference"] = raw["reference"]

    return upgraded
