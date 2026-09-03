# Data Format Reference

Part of [SensorView](README.md). This is the on-disk contract for the
`data/<Case>/` layout described in the README's
[Data Architecture](README.md#data-architecture) section.

Everything below is the on-disk contract. It is written to be enough to build a
converter from any source format without reading the application code: exact
filenames, exact HDF5 paths, exact dtypes, and what each manifest key does.
[Writing a Converter](#writing-a-converter) has a worked example and a
validation checklist.

## At a Glance

```
data/MyCase/                     ← a "case": one info.json, any number of logs
├── info.json                    ← manifest v2, describes the case
├── drive_01.parquet             ← log "drive_01": the filterable table  (REQUIRED)
├── drive_01.cloud.h5            ←   point-cloud backdrop                (optional)
├── drive_01.curve.h5            ←   1D curves, default source           (optional)
├── drive_01.sensor_2.h5         ←   1D curves, a second named source    (optional)
├── drive_01.mp4                 ←   default image stream                (optional)
├── drive_01.rear.mp4            ←   a second, named image stream        (optional)
├── drive_01.reference.parquet   ←   per-frame reference pose            (optional)
├── drive_02.parquet             ← log "drive_02": same conventions
└── drive_02.mp4
```

| Store | Type | Where | Shape |
|---|---|---|---|
| Table | Parquet | `<stem>.parquet` | one row per point per frame, scalar columns |
| Cloud | HDF5 | `<stem>.cloud.h5` | one dataset per frame, `float32 (N, 3+)` |
| Curve | HDF5 | `<stem>.curve.h5` | one dataset per (frame, series), `float32 (N, 2)` |
| Image | mp4 | `<stem>.mp4` | H.264, yuv420p, all-intra |
| Pose | Parquet | `<stem>.reference.parquet` | one row per frame: `frame x y z yaw pitch roll` |
| Manifest | JSON | `info.json` | column metadata + sidecar conventions |

Adding a log is dropping files in the folder — there is nothing to register.
Every sidecar is optional; panels for missing data hide themselves.

## Vocabulary

| Term | Meaning |
|---|---|
| **case** | A folder holding one `info.json` and one or more logs. This is what you pick in the open dialog. |
| **log** | One recording: a table plus whatever sidecars share its basename. Selecting a log swaps its cloud, curves, pose, and video together. |
| **stem** | A log's basename with the table suffix removed — `drive_01.parquet` → `drive_01`. Every sidecar of that log starts with this exact string. |
| **frame id** | A value from the table's slider column. The join key across every store. |
| **frame index** | The 0-based position of a frame id in the sorted unique list. This is what the slider reports and what the URL routes take. |
| **source id** | Which curve sidecar (i.e. which sensor) a curve plot is read from. |
| **stream id** | Which video file an image panel plays. |

## File Naming and Association

Files are associated by **basename**. There are no subfolders and no per-file
entries in the manifest.

```
stem         = basename(<table file>) with ".parquet" removed
cloud file   = <stem><cloud.suffix>                    exactly one per log
curve files  = <stem><suffix>            → source id derived from the suffix
               <stem>.<id><suffix>       → source id = <id>
image files  = <stem><suffix>            → stream id "image" (the default stream)
               <stem>.<id><suffix>       → stream id = <id>
pose file    = <stem><reference.suffix>                exactly one per log
```

Rules a converter has to respect:

- **The table must sit at the top level of the case folder.** Sidecars resolve
  against the case directory, not against the table's own directory. The file
  picker will list a table found in a subfolder, but that log's sidecars will
  not be found.
- **`<stem>.<id>` uses a dot separator.** `drive_01_rear.mp4` is not a second
  stream of `drive_01`; it is a stream of a log called `drive_01_rear`. A file
  whose name continues past the stem with anything other than `.` is skipped as
  belonging to a different log that merely shares a prefix.
- **Source and stream ids come from the filename, not the manifest.** Dropping
  `drive_01.sensor_6.h5` into the folder adds a sixth curve source with no
  manifest edit. `_` in an id becomes a space in the picker label
  (`radar_front_left` → "Radar Front Left").
- **The default curve source's id is derived from its suffix**: `.curve.h5` →
  `curve`, `.radar_front.h5` → `radar_front`, a bare `.h5` → `curve`. Both
  `drive_01.radar_front.h5` matched by a generic `.h5` and a declared
  `.radar_front.h5` suffix therefore give the same id.
- **First declared suffix wins.** When a file matches more than one suffix, the
  earliest one in the `suffix` list claims it — which is why the default image
  suffix list is `[".mp4", ".avi"]`: a stream shipped in both containers serves
  the mp4 and skips the transcode.
- **Generic curve suffixes skip other sidecars.** A `suffix` of `".h5"` would
  otherwise swallow `drive_01.cloud.h5`; the cloud and table suffixes are
  excluded unless they are themselves listed in `curve.suffix`.
- **The pose sidecar is Parquet like the table**, so it is named out of the file
  picker by its suffix. A file ending in `reference.suffix` (default
  `.reference.parquet`) is never offered as a log.

Use a `suffix` **list** when the folder holds `.h5` files that are not curves,
or when the picker should list sensors in a chosen order rather than
alphabetically:

```json
"curve": { "suffix": [".radar_front.h5", ".radar_front_left.h5", ".lidar.h5"] }
```

## The Frame ID Contract

This is the single most important thing to get right: every store is joined by
frame id, and nothing validates the join for you — a mismatch shows up as an
empty backdrop or a motionless video, not as an error.

**The frame index is derived from the table, never declared in the manifest.**
That is deliberate: a manifest cannot drift out of sync with the data it
describes, and re-exporting a log needs no manifest edit.

```python
frame_ids  = sorted(table[slider].unique())      # the frame ids, ascending
timestamps = [t - t0 for t in per-frame min(Time)] * time_scale   # seconds, first frame at 0
```

- When there is no `Time` column (or it contains nulls), timestamps fall back to
  `index / 10.0`.
- Frame ids do **not** need to be contiguous or start at zero; they only need to
  sort ascending and identify a frame uniquely.
- **Use an integer frame column.** The frame id is substituted into HDF5 dataset
  paths with Python's `str()`, so `0` yields `/frame_0` while `0.0` yields
  `/frame_0.0`. Any consistent formatting works, but integers are what every
  reader and every example here assumes.
- Slider position *i* addresses `frame_ids[i]` and `timestamps[i]`; the cloud,
  curve, and pose stores are all addressed by the id, not the position.
- A frame present in the table but missing from a sidecar renders as empty for
  that panel; it is not an error.

### Frame ids across combined logs

The top bar can combine several logs behind one slider, and every sidecar is
keyed on its log's stem — so the app has to know which log each frame came from.
It works that out by reading each selected table's frame column on its own and
mapping frame id → owning stem. Two consequences:

- **Give the logs in a case disjoint frame ids.** Numbering each log from zero
  makes ids collide across logs, and most of what is keyed on a frame id —
  including the browser's point-cloud cache — can then serve one log's data
  while another is selected. Running the ids end to end across the case (log A
  0–38, log B 39–78, …) makes that class of bug impossible. `data/NuScenes` is
  built this way.
- A frame id claimed by two logs collapses onto **one** slider position, and
  there is no error either way. The two panels with room for more than one
  answer show both logs: the image section gives each its own video, labelled
  with its stem, and the curve section stacks one band per log against a shared
  x axis and y range. Everything with room for a single answer — the point
  cloud, the reference pose, the stills in the HTML export, and the browser's
  cloud cache — resolves to the primary log, the one picked in the file modal
  rather than added through **Combine**.

## Table (`.parquet`)

The only store the app queries. One row per detection/point per frame.

### Requirements

| Rule | Detail |
|---|---|
| **Tidy rows** | One row = one point at one frame. No nesting, no per-frame arrays. |
| **Scalar columns** | List/array columns are collapsed at load: a numeric list keeps its first element, anything else is joined into a comma-separated string. Length-1 lists (`["sensor_1"]`) are the common exporter mistake this covers, but write scalars if you can. |
| **Slider column** | Integer, present on every row. Named by `table.slider` (default `Frame`). |
| **Time column** | Optional but recommended: named `Time`, numeric, non-decreasing, in the unit declared by `table.time_unit`. It is what the transport reports; the camera seek does not depend on it. |
| **Numerical columns** | Any numeric dtype. `±inf` is normalized to `NaN` on load. |
| **Categorical columns** | Strings. The filter's options are the column's `unique()` values, so keep the cardinality sane (tens, not thousands). |
| **Column names** | Must match the manifest's `keys` entries exactly, case included. |

### What the app does with it

- **Columns not declared in `keys` are invisible** — no filter, no axis, no hover
  entry. They still cost space in the file.
- **Columns declared in `keys` but absent from a given log are dropped** at load
  rather than offered and then failing. A case-wide manifest may therefore
  describe the union of columns across its logs.
- **Numerical filters** are inclusive ranges spanning `floor(min)` to
  `ceil(max)`. A row whose value in a filtered numeric column is `NaN` fails the
  comparison and disappears — if a column is meaningfully optional, consider
  whether it should be a filter at all.
- **Categorical filters** start with every value selected. Decoding a status
  word to its documented labels (`"moving"`, `"stationary"`, …) rather than
  shipping the raw integer is what makes the rail readable.
- **Combining logs** concatenates diagonally: the union of columns, null-filled
  where a log lacks one.
- **Hover text** is built from every `keys` entry present in the data, formatted
  by that key's `format` or `decimal`.
- Row order is not meaningful; the app resets to a fresh `RangeIndex` on load.

### Recommended schema

Nothing here is mandatory beyond the slider column, but this shape covers the
whole feature set:

| Column | Type | Role |
|---|---|---|
| `Frame` | int32/int64 | `table.slider` — the frame id |
| `Time` | float | wall clock, unit declared by `time_unit` |
| `X` / `Y` / `Z` | float | `x_3d` / `y_3d` / `z_3d` |
| `Sensor` | string | categorical, splits the statistical views |
| *(anything else)* | numeric or string | color scales, extra filters, hover |

A world frame — the host travelling *through* fixed coordinates rather than
sitting at the origin — is what makes the decay slider draw trails, the cloud
backdrop accumulate into a map, and a reference pose worth carrying.

### Writing it

```python
# Python: pandas + pyarrow, or polars
df.to_parquet("drive_01.parquet", index=False)
```

```matlab
% MATLAB
parquetwrite("drive_01.parquet", tbl)
```

Any codec Arrow can read is fine (`zstd` and `snappy` both compress well here).
Parquet is the only table format the file picker offers and the only one the
loader reads; selecting anything else raises `Unsupported file type`.

## Cloud (`.cloud.h5`)

The fixed backdrop behind the detections. Display-only: never filtered, never
hovered, no runtime controls.

### Layout

```
/                      attribute "columns" = ["x", "y", "z", ...]   (optional)
/frame_<frame_id>      float32, shape (N, C) with C >= 3
/frame_<frame_id>      ... one dataset per frame
```

- The dataset path comes from `cloud.dataset_pattern`, default
  `/frame_{frame_id}`. A nested `/frames/{frame_id}` also resolves.
- **Columns 0, 1, 2 are x, y, z** in the same coordinate frame as the table's
  3D axes. Extra columns are read and carried but not rendered today.
- Dtype is `float32` in every file here; any numeric dtype h5py can read works.
- **Decimate before writing** — the app has no way to ask for more resolution
  later, and every point costs WebGL fill rate plus JSON payload on the
  per-frame fetch. A voxel downsample followed by a hard per-frame budget is
  what `build_nuscenes_case.py` does (0.25 m voxels, 12 000 points, coordinates
  rounded to 2 decimals), and roughly 10–25k points per frame is the range these
  panels are built for.
- `gzip` compression with one chunk per frame keeps a frame read to one
  contiguous block. It is optional — see the curve note below.
- Omit the dataset for a frame with no points rather than writing an empty one.
- The `columns` root attribute is informational; the renderer always uses the
  first three columns.

### Calibration

`cloud.calibration` is applied to columns 0–2 at read time, so a cloud stored in
its sensor's own frame lines up with a table stored in the vehicle or world
frame:

```json
"cloud": {
    "calibration": { "translation": [3.7, 0.0, 0.6], "rotation_rpy_deg": [0, 0, -45] }
}
```

Rotation is ZYX intrinsic — `Rz(yaw) @ Ry(pitch) @ Rx(roll)` — with the angles
given in degrees. An all-zero block is an identity transform and is skipped
entirely.

## Curve (`.curve.h5`)

Per-frame 1D curves — a range profile, the threshold applied to it, a noise
floor. One file holds many named series per frame.

### Layout

```
/frame_<frame_id>/<series name>     float32, shape (N, 2)
                                    column 0 = x, column 1 = y
```

- The dataset path comes from `curve.dataset_pattern`, default
  `/frame_{frame_id}/{name}`. A nested `/frames/{frame_id}/{name}` also
  resolves, as does a `{sensor_id}` placeholder for files that key their series
  by sensor internally instead of one file per sensor.
- **Every dataset is an (N, 2) pair — each curve carries its own x axis.** A
  shared x vector would be smaller but cannot describe real data: range bins
  differ from one sensor to the next, and differ frame to frame as the look type
  alternates. Because of that, `x` in a plot definition carries only a *label*.
- **Both orientations are accepted.** `(N, 2)` is read as columns; `(2, N)` is
  read as rows, so an array written column-major by MATLAB reads back correctly.
  The ambiguous `(2, 2)` case is read as columns.
- A 1D dataset is accepted too and plotted against its sample index.
- `N` may vary per frame and per series.
- **Non-finite values are drawn as gaps**, not clamped or dropped. Write `NaN`
  (or `-inf`) for bins nothing was measured in and the line breaks there — which
  for a binned profile is most of them, and is the honest picture.
- **Series names must match the `name` of a trace** in the manifest's plot
  definitions, unless that trace gives an explicit `dataset` path instead.
- Compression is optional and often not worth it: a curve is a kilobyte, where a
  chunked, compressed HDF5 dataset costs several in bookkeeping alone. The
  bundled case writes its curves contiguous and uncompressed, and its clouds
  gzipped.

### Several sources per log

One file per sensor. They are separate sources rather than merged series because
their bins do not line up — one radar's profile ends at 130 m and another's at
254 m in the same scene, so there is no shared axis to draw them against. The
inspector gets a **Sensor** selector, and each source keeps its own plot list and
its own y-range estimate, because one sensor's levels say nothing about
another's.

A plot whose series are all missing from the selected source is not offered, so
one case-wide set of plot definitions can cover sensors that recorded different
things — the bundled case gives its five radars two plots and its lidar two
others, from one `plots` list.

### Y-axis behaviour

The y axis is held constant across frames rather than autoscaling, so where the
signal sits relative to its threshold stays readable while scrubbing. The range
is estimated once per (log, source, plot) from up to 50 evenly spaced frames,
plus 5% padding. A manifest-declared `y_range` always wins over the estimate.

## Image (`.mp4`)

### Encoding requirements

| Requirement | Why |
|---|---|
| Container a browser plays: `.mp4`, `.m4v`, `.webm`, `.ogv` | Served straight to a `<video>` element. Anything else is transcoded on first request into `cache/video` (keyed on the source's size and mtime) — correct, but it blocks that first request for a few seconds, and only if ffmpeg can decode it. |
| H.264 / yuv420p | What every browser decodes. |
| **All-intra** (`-g 1 -keyint_min 1 -sc_threshold 0`) | Browsers can only seek to keyframes, and the slider jumps to arbitrary frames. A long GOP means the panel shows the wrong frame. |
| Even pixel dimensions | Required by yuv420p. |
| `+faststart` | Lets the browser seek before the whole clip has downloaded (the server serves HTTP Range requests). |

```bash
ffmpeg -framerate 2 -i frames/%05d.jpg -an -c:v libx264 -pix_fmt yuv420p \
       -g 1 -keyint_min 1 -sc_threshold 0 -crf 23 -movflags +faststart out.mp4
```

### The seek contract

The video element never plays on its own; it is seeked to the frame the rest of
the app is showing. The mapping is **frame count to frame count**, and it is the
only mapping there is: slider frame *i* of *N* lands on video frame

```
k = round(i / (N - 1) × (M - 1))
```

of *M*, then seeks to the middle of that frame. Both counts are measured, never
declared — *M* by demuxing the file with ffmpeg, *N* from the log's own Parquet —
and frame duration comes from the video element's own `duration`.

For a converter that means:

- **The recording and the log are assumed to cover the same stretch of time.**
  Encode a clip that starts when the log starts and ends when it ends, and the
  mapping is exact whatever rate either ran at. A 10 fps dashcam against a 20 Hz
  log advances one video frame every second slider step rather than being
  interpolated between two.
- **No declared rate enters the mapping.** Nothing in the manifest configures
  it; an `image.seek` key from an earlier version is obsolete and ignored. The
  encode rate only has to make the clip's *duration* match the log's.
- **`image.time_offset` (seconds) shifts the whole clip**, for a recording that
  did not start rolling with the data after all.
- If *M* cannot be read — no ffmpeg, or a file it cannot demux — the video is
  left where it is rather than seeked to a guessed position.

With logs combined, the slider is cut into segments, one per run of frames a log
owns; crossing into the next segment swaps the video source and re-maps against
*that* log's own frame count. A log with no such stream leaves its segment out
entirely, and the panel holds the previous picture rather than showing another
log's footage under this one's data.

### Stills in the HTML export

"All frames as HTML video" writes one self-contained file with no server behind
it, so there is nothing for a `<video>` element to seek. That export instead
pulls one still per frame out of the recording — the stream selected in the
camera panel, mapped frame-for-frame exactly as the panel maps it — and inlines
them as base64 JPEGs drawn in the corner of the scene.

Every frame comes out of one ffmpeg pass per log (a `select` expression naming
each index), and stills are downscaled to 640 px wide, since they render as a
thumbnail and every one of them lands inside the file. Frames that map onto the
same video frame share one encoded copy. Without ffmpeg the export still works;
it just carries no pictures.

## Reference Pose (`.reference.parquet`)

A sidecar of its own marks the moving origin in the 3D view — usually the host
vehicle. It is the only thing that places one.

> Earlier versions also read a position from three table columns, `x_ref` /
> `y_ref` / `z_ref`. They carried a position and nothing else, so a shape placed
> from them sat square to the axes however the vehicle was actually pointing,
> and they cost every row of the table three columns to say where one vehicle
> was in a few hundred frames. **They are no longer read.** A manifest that
> still names them is not an error — the keys are ignored, and dropped the next
> time a v1 manifest is written.

### Layout

One row per frame, positions in **meters**, angles in **radians**:

| `frame` | `x` | `y` | `z` | `yaw` | `pitch` | `roll` |
|---|---|---|---|---|---|---|
| 0 | 0.0 | 0.0 | 0.0 | -1.9236 | 0.0107 | -0.0213 |
| 1 | -1.5608 | -4.2134 | 0.0 | -1.9178 | 0.0138 | -0.0243 |

- The frame column holds the same frame ids as the table — that is what pairs a
  pose with a frame. Ids are matched numerically, so `5`, `5.0`, and a numpy
  scalar all hit the same row.
- Angles are rotations about the plot's **x, y and z axes** (roll, pitch, yaw
  respectively, applied ZYX: `Rz(yaw) @ Ry(pitch) @ Rx(roll)`), for the same
  reason `vertices` are: which physical quantity each axis carries is chosen in
  the view, not by the manifest.
- **`x` and `y` are required**; `z` and all three angles default to 0, which is
  a flat, unrotated reference rather than a missing one.
- A frame the sidecar has no row for **draws no reference**, rather than
  stranding it at its last known pose.
- Ints are cast to float on read; nulls become 0.
- The whole file is read once and cached (it is a few hundred rows), not re-read
  per frame.

### Column mapping

Column names are the exporter's, so the mapping is configured — either in the
manifest, or in the 3D view's reference pickers, which write back to it:

```json
"reference": {
    "suffix": ".reference.parquet",
    "columns": {
        "frame": "frame_id",
        "x": "ref_east_m",  "y": "ref_north_m", "z": "ref_up_m",
        "yaw": "ref_yaw_rad", "pitch": "ref_pitch_rad", "roll": "ref_roll_rad"
    }
}
```

An unmapped field falls back to a column named after the field itself (`x`,
`yaw`, …), so **a file that already names its columns `frame`/`x`/`y`/`z`/`yaw`/
`pitch`/`roll` needs no mapping at all**. `frame` additionally falls back to the
table's own frame column, then to `frame`, `frame_id`, `frame_idx`.

All seven — the frame key included — are pickers in the 3D view's axis panel,
listing the sidecar's own columns and writing straight back to this block. The
frame key matters most: it is what pairs a sidecar row with a table frame, so a
file that spells it something the fallbacks do not look for (`t`, `sample_idx`)
matches nothing, and the reference never appears. Pick the column there and the
choice is saved to `info.json` with the rest.

The axis ranges widen to cover wherever the pose travels — across every combined
log, not just the current frame's. Overlay mode draws no reference at all: every
frame at once leaves no single pose to show.

### When nothing places it

Declaring a `reference` block is the dataset saying it has a reference. So a
dataset that declares one and ships **no sidecar at all** draws it at the origin
`(0, 0, 0)` rather than not at all, with the axis ranges widened to reach it
there: a missing sidecar then reads as a reference sitting at the origin rather
than as a `reference` block that was quietly ignored, which is the harder of the
two to diagnose.

- The shape is whatever the block declared: its **mesh** if it declares
  geometry, the plain **dot** if it does not.
- A dataset with **no `reference` block at all** draws nothing, exactly as
  before — otherwise every case in the world would grow a white dot it never
  asked for.
- A log **whose sidecar pairs with nothing** — the frame picker reading `None`,
  so no row of the file belongs to any frame — draws nothing either. That is the
  pairing being unset, not the dataset failing to say where its reference goes,
  and a body parked at the origin would look placed. Map the frame column and it
  appears.
- This is for a reference the dataset *cannot* place, not one that is unplaced
  for a moment. A frame the sidecar has no row for, and a frame whose rows were
  all filtered away, both keep drawing nothing rather than sending the reference
  to the origin mid-playback.

### Mesh geometry

The reference draws as a white dot by default. A `reference` block with
`"shape": "mesh"` trades it for a body you declare vertex by vertex, so you can
see which detections land on the vehicle and which are past it:

```json
"reference": {
    "shape": "mesh",
    "name": "Ego Vehicle",
    "color": "#4c9ffe",
    "opacity": 0.3,
    "vertices": [
        [-0.97, 0.0, 0.0], [-0.62, 4.2, 0.0], [0.62, 4.2, 0.0], [0.97, 0.0, 0.0],
        [-0.97, 0.0, 1.5], [-0.62, 4.2, 1.5], [0.62, 4.2, 1.5], [0.97, 0.0, 1.5]
    ],
    "faces": [
        [0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7], [0, 3, 7], [0, 7, 4],
        [1, 2, 6], [1, 6, 5], [0, 1, 5], [0, 5, 4], [3, 2, 6], [3, 6, 7]
    ],
    "edges": [
        [0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4],
        [0, 4], [1, 5], [2, 6], [3, 7]
    ],
    "edge_color": "#7fc4ff"
}
```

- `vertices` are in **meters relative to the reference point**, on the plot's x,
  y and z axes. Nothing is generated from a size and an offset: the shape is
  stated outright, which is also how you say which end is the front — the
  example above narrows toward `+y`, so the nose stays legible as the mesh turns
  with a pose. With a pose whose `yaw` is measured from `+x`, author the mesh
  pointing along `+x` instead.
- `faces` are vertex-index triangles. Malformed or out-of-range triangles are
  dropped (Plotly renders a bad index as a hole, which is harder to diagnose).
- `edges` draws the wireframe: a list of index pairs draws exactly those
  (usually what you want — a silhouette without the triangulation showing),
  `true` derives them from `faces` including every diagonal, `false` draws none.
- A mesh with no usable triangles falls back to the marker, as does an unknown
  `shape` — a dot in the right place beats nothing at all.
- The 3D scene makes room for whatever the mesh adds beyond the data, using the
  furthest vertex as a radius so a rotating mesh is never clipped.

The block is read from both v1 and v2 manifests.

## `info.json` Reference

One manifest per **case**, describing the case rather than any individual log.
Its blocks are named for the **shape** of the data rather than the sensor that
produced it — `table`, `cloud`, `curve`, `image`, plus `reference` — so a
dataset that is not radar still reads naturally.

Two things it deliberately does **not** contain:

- **The frame index.** Frame ids and timestamps are derived from the table at
  load time, so the manifest can never drift out of sync.
- **Per-log file lists.** Sidecars resolve from the selected log's stem.

A v1 `info.json` (no `manifest_version`, table keys at the top level) is
accepted and upgraded in memory, so **existing datasets keep working with no
conversion**. Saving a v1 dataset writes v1 back rather than silently upgrading
it.

> The app writes back to `info.json` when you change a 3D axis or reference
> picker — the `slider` / `x_3d` / `y_3d` / `z_3d` values and
> `reference.columns`, with every other block preserved. `config.json`
> in the repo root is something else entirely: per-installation UI state (last
> data path, case, and file), auto-created and git-ignored.

### Top level

| Key | Type | Default | Notes |
|---|---|---|---|
| `manifest_version` | int | — | `2` selects the v2 schema. Absent means v1. |
| `name` | string | case folder name | Display name. |
| `table` | object | — | **Required.** |
| `cloud` | object | absent | Omit and no backdrop is read. |
| `curve` | object | absent | Omit and no curve panel appears. |
| `image` | object | absent | Omit and no video panel appears. |
| `reference` | object | absent | Pose source and overlay styling. |

### `table`

| Key | Type | Default | Notes |
|---|---|---|---|
| `slider` | string | `"Frame"` | The frame id column. Integer. |
| `x_3d`, `y_3d`, `z_3d` | string | first numeric keys | Default 3D axes. A column the loaded log lacks is ignored. |
| `time_unit` | string | `"s"` | Unit of the `Time` column: `s`, `ms`, `us`, `ns` (long spellings accepted). An unrecognized value falls back to 1.0 rather than rescaling the index. |
| `suffix` | string | `".parquet"` | Table file suffix; also what stem extraction strips. |
| `keys` | object | `{}` | Column metadata; see below. |
| `format`, `calibration` | any | — | Carried by some datasets as a record of provenance; read by nothing. |

#### `table.keys.<column>`

| Key | Type | Notes |
|---|---|---|
| `description` | string | Label in pickers, filters, axis titles, and hover. Falls back to the column name. |
| `type` | `"numerical"` \| `"categorical"` | Numerical gets a range slider and can drive a continuous color scale; categorical gets a multi-select and can split the statistical views. |
| `decimal` | int | Decimal places in hover text. |
| `format` | string | A Python format spec (e.g. `"{:.3e}"`) used for hover instead of `decimal`. |

### `cloud`

| Key | Type | Default | Notes |
|---|---|---|---|
| `suffix` | string | `".cloud.h5"` | One file per log. |
| `dataset_pattern` | string | `"/frame_{frame_id}"` | Must contain `{frame_id}`. |
| `calibration` | object | identity | `translation` `[x, y, z]` in meters, `rotation_rpy_deg` `[roll, pitch, yaw]` in degrees. Applied at read. |
| `display` | object | see below | Fixed trace styling: `color` `"#8d99ae"`, `size` `1.2`, `opacity` `0.35`, `name` `"Point Cloud"`. |
| `format`, `columns`, `decimation` | any | — | Provenance only; read by nothing. Worth writing anyway — a decimated cloud cannot say elsewhere how it was decimated. |

The backdrop has no runtime controls by design, which is why its styling lives
in the manifest rather than in a dropdown.

### `curve`

| Key | Type | Default | Notes |
|---|---|---|---|
| `suffix` | string \| list | `".curve.h5"` | See [File Naming](#file-naming-and-association) for how the two forms differ. |
| `dataset_pattern` | string | `"/frame_{frame_id}/{name}"` | Supports `{frame_id}`, `{name}`, `{sensor_id}`. |
| `plots` | list | `[]` | Plot definitions; the panel gets a selector when there is more than one. |
| `format` | any | — | Provenance only. |

#### `curve.plots[]`

| Key | Type | Default | Notes |
|---|---|---|---|
| `id` | string | `plot_<index>` | Stable identifier. |
| `label` | string | the id | Shown in the plot selector. |
| `x.label` | string | `""` | X-axis title. **Only a label** — every series brings its own x vector. |
| `x.range` | `[min, max]` | auto | Pins the x axis. |
| `y_label` | string | `""` | Y-axis title. |
| `y_range` | `[min, max]` | estimated | Pins the y axis; always wins over the estimate. |
| `log_y` | bool | `false` | Logarithmic y axis. |
| `dataset_pattern` | string | the block's | Per-plot override. |
| `traces` | list | `[]` | Draw order is list order. |

#### `curve.plots[].traces[]`

A bare string is accepted as shorthand for `{"name": <string>}`.

| Key | Type | Default | Notes |
|---|---|---|---|
| `name` | string | — | The HDF5 series name; fills `{name}` in the dataset pattern. |
| `dataset` | string | from pattern | Explicit dataset path, overriding `name` entirely. |
| `label` | string | the name | Legend entry. |
| `color` | string | cycled | Falls back to a six-color palette by position. |
| `dash` | string | `"solid"` | Plotly dash style: `dash`, `dot`, `dashdot`, … |
| `width` | number | `2` | Line width. |
| `mode` | string | `"lines"` | `lines`, `markers`, `lines+markers`. |
| `size`, `symbol` | number, string | `6`, `"circle"` | Marker styling when `mode` includes markers. |

```json
"curve": {
    "suffix": ".h5",
    "dataset_pattern": "/frame_{frame_id}/{name}",
    "plots": [
        {
            "id": "range_profile",
            "label": "Range Profile",
            "x": { "label": "Range (m)" },
            "y_label": "RCS (dBsm)",
            "traces": [
                { "name": "rcs_peak", "label": "Peak RCS", "color": "#4c9be8" },
                { "name": "rcs_mean", "label": "Mean RCS", "color": "#e8734c", "dash": "dash" }
            ]
        }
    ]
}
```

### `image`

| Key | Type | Default | Notes |
|---|---|---|---|
| `suffix` | string \| list | `[".mp4", ".avi"]` | Preference order; earlier suffixes win, so a stream present in both containers skips the transcode. |
| `time_offset` | float | `0.0` | Seconds added to every seek, for a recording that did not start rolling with the data. |
| `format` | any | — | Provenance only. |
| `seek` | any | — | Obsolete and ignored; the mapping is measured, not declared. |

### `reference`

| Key | Type | Default | Applies to |
|---|---|---|---|
| `suffix` | string | `".reference.parquet"` | pose sidecar — also what the file picker excludes |
| `columns` | object | field-named fallbacks | pose sidecar — see [Column mapping](#column-mapping) |
| `shape` | `"marker"` \| `"mesh"` | `"marker"` | An unknown value falls back to `marker`. |
| `name` | string | `"Host Vehicle"` | both |
| `color` | string | `"#ffffff"` | both |
| `opacity` | float | `1.0` marker / `0.35` mesh | both |
| `size` | number | `6` | marker |
| `symbol` | string | `"circle"` | marker |
| `line_color`, `line_width` | string, number | `"#000000"`, `2` | marker |
| `vertices` | `[[x, y, z], …]` | `[]` | mesh — meters relative to the reference point |
| `faces` | `[[i, j, k], …]` | `[]` | mesh — vertex-index triangles; no faces means fall back to the marker |
| `edges` | bool \| `[[i, j], …]` | `true` | mesh — wireframe: derived from faces, exactly these pairs, or none |
| `edge_color`, `edge_width` | string, number | follows `color`, `2` | mesh |

Dropping a `<stem>.reference.parquet` beside a log gives it a pose with no
`reference` block at all — the block is only needed to map non-obvious column
names or to draw something other than a dot.

### Minimal manifest

The table block is the only required one:

```json
{
  "manifest_version": 2,
  "table": {
    "slider": "Frame",
    "x_3d": "X",
    "y_3d": "Y",
    "z_3d": "Z",
    "time_unit": "s",
    "keys": {
      "Frame":  { "description": "Frame",      "decimal": 0, "type": "numerical" },
      "Time":   { "description": "Time (s)",   "decimal": 2, "type": "numerical" },
      "X":      { "description": "East (m)",   "decimal": 2, "type": "numerical" },
      "Y":      { "description": "North (m)",  "decimal": 2, "type": "numerical" },
      "Z":      { "description": "Up (m)",     "decimal": 2, "type": "numerical" },
      "RCS":    { "description": "RCS (dBsm)", "decimal": 1, "type": "numerical" },
      "Sensor": { "description": "Radar",                    "type": "categorical" }
    }
  }
}
```

`data/NuScenes/info.json` is the same thing with every optional block filled in.

## Writing a Converter

The formats are plain Parquet, plain HDF5, and plain JSON — no SensorView import
is needed to produce any of them, and the app ships no writers.
`data/NuScenes/build_nuscenes_case.py` is a complete worked converter (real
sensor data in, a five-log case folder out, numpy/pandas/pyarrow/h5py plus
ffmpeg only). What follows is the same contract in miniature.

```python
import json
import h5py
import numpy as np
import pandas as pd

OUT, STEM = "data/MyCase", "run_01"

# 1. Table: one row per point per frame, scalar columns, integer frame id.
table.to_parquet(f"{OUT}/{STEM}.parquet", index=False)
frame_ids = np.sort(table["Frame"].unique())

# 2. Cloud: one float32 (N, 3+) dataset per frame, already decimated.
with h5py.File(f"{OUT}/{STEM}.cloud.h5", "w") as handle:
    handle.attrs["columns"] = ["x", "y", "z"]
    for frame_id in frame_ids:
        points = cloud_of(frame_id).astype(np.float32)        # (N, 3), xyz
        handle.create_dataset(
            f"/frame_{frame_id}", data=points,
            compression="gzip", compression_opts=4,
        )

# 3. Curves: one float32 (N, 2) dataset per (frame, series); col 0 = x.
with h5py.File(f"{OUT}/{STEM}.curve.h5", "w") as handle:
    for frame_id in frame_ids:
        group = handle.create_group(f"/frame_{frame_id}")
        for name, (x, y) in curves_of(frame_id).items():      # y may hold NaN gaps
            group.create_dataset(
                name, data=np.column_stack([x, y]).astype(np.float32)
            )

# 4. Reference pose: one row per frame, meters and radians.
pd.DataFrame(poses).to_parquet(                               # frame,x,y,z,yaw,pitch,roll
    f"{OUT}/{STEM}.reference.parquet", index=False
)

# 5. Manifest.
manifest = {
    "manifest_version": 2,
    "name": "MyCase",
    "table": {
        "slider": "Frame",
        "x_3d": "X", "y_3d": "Y", "z_3d": "Z",
        "time_unit": "s",
        "keys": {
            "Frame":  {"description": "Frame",      "decimal": 0, "type": "numerical"},
            "Time":   {"description": "Time (s)",   "decimal": 2, "type": "numerical"},
            "X":      {"description": "East (m)",   "decimal": 2, "type": "numerical"},
            "Y":      {"description": "North (m)",  "decimal": 2, "type": "numerical"},
            "Z":      {"description": "Up (m)",     "decimal": 2, "type": "numerical"},
            "RCS":    {"description": "RCS (dBsm)", "decimal": 1, "type": "numerical"},
            "Sensor": {"description": "Radar",                    "type": "categorical"},
        },
    },
    "cloud": {"suffix": ".cloud.h5", "dataset_pattern": "/frame_{frame_id}"},
    "curve": {
        "suffix": ".curve.h5",
        "dataset_pattern": "/frame_{frame_id}/{name}",
        "plots": [{
            "id": "range_profile", "label": "Range Profile",
            "x": {"label": "Range (m)"}, "y_label": "RCS (dBsm)",
            "traces": [
                {"name": "rcs_peak", "label": "Peak RCS"},
                {"name": "rcs_mean", "label": "Mean RCS", "dash": "dash"},
            ],
        }],
    },
    "image": {"suffix": [".mp4"]},
    "reference": {"shape": "mesh", "vertices": [...], "faces": [...]},
}
with open(f"{OUT}/info.json", "w", encoding="utf-8") as write_file:
    json.dump(manifest, write_file, indent=4)
```

Encode the video separately with the ffmpeg invocation in
[Image](#image-mp4), writing it to `data/MyCase/run_01.mp4`.

### From MATLAB

Every format here is one MATLAB call away:

```matlab
parquetwrite("run_01.parquet", tbl)

h5create("run_01.cloud.h5", "/frame_0", size(pts), "Datatype", "single")
h5write("run_01.cloud.h5",  "/frame_0", single(pts))

h5create("run_01.curve.h5", "/frame_0/signal", size(pair), "Datatype", "single")
h5write("run_01.curve.h5",  "/frame_0/signal", single(pair))
```

MATLAB writes column-major, so an `N×2` array lands in the file as `2×N` — which
reads back correctly, since both orientations are accepted. A struct array saved
with `-v7.3` produces the same `/frame_<id>/<name>` layout the default dataset
pattern expects.

### Validation checklist

Run through this before opening the case; each item is a failure mode that
surfaces as silence rather than an error.

- [ ] `info.json` sits in the case folder, and the table sits **beside it**, not
      in a subfolder.
- [ ] Every sidecar filename starts with the table's exact stem, and any extra
      id is separated with a `.`.
- [ ] `table.slider` names a column that exists and is integer-valued.
- [ ] Logs in the same case have **disjoint** frame ids.
- [ ] Every column you want to filter, plot, or hover has a `keys` entry with a
      matching name and a `type`.
- [ ] Categorical columns are strings; numeric columns hold no `NaN` in
      anything you plan to filter on.
- [ ] HDF5 frame paths use the **same string form** as the table's frame ids
      (`/frame_0`, not `/frame_0.0` or `/frame_000`).
- [ ] Curve datasets are `(N, 2)` (or `(2, N)`), and every trace `name` in the
      manifest matches a dataset name in the file.
- [ ] Cloud frames are already decimated — a few tens of thousands of points at
      most.
- [ ] The pose sidecar's frame column holds table frame ids, its positions are
      meters and its angles radians.
- [ ] The mp4 is all-intra, and its duration covers the same span as the log.

A quick smoke test without launching the UI:

```python
from dataio.manifest import Manifest
from dataio.dense_store import CloudStore, CurveStore
from dataio.frames import build_frame_index
from dataio.radar_store import load_radar
from dataio.reference import ReferenceStore

manifest = Manifest.load("data/MyCase")
stem = manifest.stem_of("run_01.parquet")
print(manifest.has_cloud(stem), manifest.has_curve(stem), manifest.has_image(stem))
print(manifest.curve_sources(stem), manifest.image_streams(stem))

data = load_radar(["data/MyCase/run_01.parquet"])
frame_ids, timestamps, fps = build_frame_index(
    data, manifest.frame_key, time_scale=manifest.time_scale
)
print(len(frame_ids), "frames,", round(timestamps[-1], 2), "s")

cloud = CloudStore(manifest.cloud_path(stem), manifest.cloud_dataset_pattern())
print(cloud.columns(), cloud.read_frame(frame_ids[0]).shape)

curve = CurveStore(manifest.curve_path(stem))
print(curve.signals(manifest.curve_dataset_pattern()))

pose = ReferenceStore.open(
    manifest.reference_path(stem), manifest.reference_columns(), manifest.frame_key
)
print(pose and pose.resolved_columns, pose and pose.pose(frame_ids[0]))
```

If `read_frame` returns `None`, `signals()` comes back empty, or `pose(...)` is
`None`, the frame ids or the dataset pattern disagree with the file — the things
nothing else checks for you.
