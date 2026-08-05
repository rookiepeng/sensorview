# SensorView

<img src="./assets/sensorview_logo.svg" alt="logo" width="200"/>

A Flask/Dash workbench for exploring multi-sensor logs. A 3D point cloud, the
camera frame and 1D curves that go with it, and six statistical views — all
describing the same instant, all driven by one frame slider and one set of
filters.

## Screenshots

The workbench on the bundled `data/Example` case: the 3D point cloud with its
decimated backdrop and host-vehicle box, the camera frame and range profile for
the same instant in the inspector, and two statistical views in the dock.

<img src="./assets/screenshot.png" alt="SensorView workbench, dark theme" width="900"/>

<details>
<summary>Light theme</summary>

<img src="./assets/screenshot_light.png" alt="SensorView workbench, light theme" width="900"/>

</details>

## The Workbench

Everything is sized against the viewport rather than flowing down a page.
Nothing scrolls except panel interiors, so no view is ever more than a click
from visible — which is the point, since all of them describe the same frame.

| Region | Holds |
|---|---|
| **Top bar** | Dataset breadcrumb (it *is* the file picker), combine-logs, theme toggle, export menu |
| **Left rail** | Display options and the per-column filters built from the manifest |
| **Canvas** | The 3D point cloud — the only region that grows |
| **Inspector** | The camera stream and the curve plot for the current frame |
| **Transport** | Frame scrubbing, playback, buffering progress |
| **Analysis dock** | Two slots, each showing any one of the six statistical views |

The rail, inspector, and dock each have a splitter on their inner edge; whatever
they give up, the canvas takes. All of it — collapse, drag, theme — runs
clientside (`assets/workbench.js`), because none of it is anything the server
knows about.

### 3D Canvas

Interactive 3D scatter with color mapping, a decay slider that fades previous
frames in behind the current one, and an overlay mode that draws every frame at
once. View settings float over the plot rather than docking above it: they are
touched a handful of times a session and would otherwise cost their height on
every frame. Axis and reference-column mapping live behind the sliders button.

### Filter Rail

Filters are generated per column from the manifest — a range slider for each
numerical key, a multi-select for each categorical one. Every view reads the
same filtered table, so a filter change moves all of them together. Points can
be relabelled *hidden* by clicking them on the plot or lassoing them in a 2D
view, then filtered on that label.

### Inspector

The camera stream and the curve plot for the current frame, docked on the right
rather than floating over the canvas they accompany. Each section has its own
minimize toggle and restores from a chip in the panel bar; the curve section
grows into whatever height the image gives up. The inspector hides itself
entirely when a log has neither sidecar, and each section hides independently,
so the canvas reclaims the full width.

### Analysis Dock

Two side-by-side slots over a drag-resizable panel that collapses to its own
header. Each slot shows one of six views:

- **2D Scatter A / B** — two independent x/y/color mappings, with lasso and box
  selection wired to the visibility label
- **Histogram** — one column binned, normalized as density or probability,
  optionally split by a category
- **Violin** — distribution by category
- **Parallel Categories** — categorical relationships
- **Heatmap** — 2D density

Slot assignment *is* the enable switch. These figures are expensive, so a view
in a slot is live, everything else is idle, and a collapsed dock computes
nothing at all.

### Transport and Buffering

The frame slider is the single source of truth for time: the video element never
plays on its own, it is seeked to the frame the rest of the app is showing.
Playback runs the same path. Server-side and browser-side buffering progress
ride as two hairlines on the transport's top edge — visible when looked for,
costing no extra height either way.

### Other

- **Multiple File Support**: combine additional logs from the top bar and
  compare them in one view
- **Session Isolation**: each browser session gets its own cache namespace
- **Data Buffering**: a WebWorker pre-fetches frames into IndexedDB so scrubbing
  does not wait on the server
- **Dark/Light Theme**: chrome and Plotly templates switch together; the choice
  persists in `localStorage`
- **Export**: current plot as PNG or HTML, all frames as an HTML video, or the
  filtered data itself for the current frame or all frames

## Data Architecture

Each kind of sensor data gets the storage format that suits its shape, joined by
a single `frame_id`:

| Data | Format | Filterable | Updates on |
|---|---|---|---|
| Table (`table`) | Parquet (tidy table) | **Yes** — full filter pipeline | filter changes + frame changes |
| Cloud (`cloud`) | HDF5, decimated at ingest | No — fixed backdrop | frame changes only |
| Curves (`curve`) | HDF5, one (N, 2) pair per frame | No | frame changes only |
| Images (`image`) | mp4, all-intra | No | frame changes only |

The reasoning behind the split:

- **The table is the only queried dataset**, so it stays columnar. Parquet gives
  compression plus projection/predicate pushdown, and MATLAB reads it natively
  via `parquetread`/`parquetwrite` (Feather/Arrow IPC has no such support).
- **The cloud and curves are display-only** frame-indexed blobs. Nobody
  queries them by column, so Parquet's columnar machinery would be pure
  overhead; a chunked HDF5 dataset per frame reads as one contiguous block and
  is equally native in MATLAB (`h5read`).
- **Cloud decimation happens once at ingest.** Since the backdrop has no runtime
  controls, no full-resolution data is kept on the read path.
- **Images are seeked client-side.** A native `<video>` element does the decoding
  and the frame slider drives `currentTime`, so scrubbing costs no server round
  trip. Video is encoded all-intra because browsers can only seek to keyframes.
  A recording in a container no browser plays — a vendor `.avi` off a logger —
  is transcoded to that same all-intra mp4 on first request and cached under
  `cache/video`, keyed on the source's size and mtime. The case folder is never
  written to.

Because the display-only views never depend on filter state, dragging a filter
slider re-renders the table alone — it never re-reads the cloud, curves, or video.

Table columns are flattened to scalars on the way in. Exporters commonly write a
column as a length-1 list — a sensor id as `["sensor_1"]` rather than
`"sensor_1"` — which nothing downstream can filter or plot, so list columns are
collapsed at load time. Columns the manifest declares but a given log never
exported are dropped from the filter and axis pickers rather than offered and
then failing.

### Dataset Layout

A case folder holds any number of logs side by side. A log's files are
associated by **basename** — no subfolders, no per-file manifest entries:

```
data/MyCase/
├── info.json                # manifest v2 (conventions only)
├── drive_01.parquet         # `table` — the filterable point cloud
├── drive_01.cloud.h5        # `cloud` — decimated backdrop
├── drive_01.curve.h5        # `curve` — 1D curves
├── drive_01.sensor_2.h5     # a second, named curve source
├── drive_01.mp4             # `image` — a video stream
├── drive_01.rear.mp4        # a second, named image stream
├── drive_02.parquet         # the next log, same conventions
└── drive_02.mp4
```

Adding a log is dropping files in the folder — nothing to register. Selecting a
log in the file picker swaps its cloud, curve plots, and video together.
Every sidecar is optional; cards for missing data hide themselves.

### Dataset Manifest (`info.json` v2)

The manifest describes the *case*, not any individual log. Its blocks are named
for the **shape** of the data rather than the sensor that produced it — `table`,
`cloud`, `curve`, `image`, plus `reference` — so a dataset that is not radar
still reads naturally. It carries column metadata, sidecar filename suffixes,
calibration, and cloud styling. Two things it deliberately does **not** contain:

- **The frame index.** Frame ids, timestamps, and capture rate are derived from
  the table Parquet at load time, so a manifest can never drift out of sync with
  the data. The same derivation runs at ingest, which is what guarantees the
  rate a video was *encoded* at matches the rate it is *seeked* at.
- **Per-log file lists.** Sidecars resolve from the selected log's basename, and
  image streams are discovered from the files themselves.

A v1 `info.json` (no `manifest_version`) is still accepted and upgraded in
memory, so **existing datasets keep working with no conversion**.

### Curves (`curve`)

Curve data is 1D, and one HDF5 file holds many named series per frame — a
signal, the threshold applied to it, a noise floor, and so on. Which series
share a plot, and how each curve is drawn, is **declared in `info.json`**: only
the author knows which curves belong on the same axes.

Every dataset is an **(N, 2) pair** — column 0 the x axis, column 1 the value —
so each curve carries its own axis. A shared x vector would be smaller but it
cannot describe real data: range bins differ from one sensor to the next, and
differ frame to frame as the look type alternates. Both orientations are
accepted, so a 2xN array written by MATLAB reads back correctly, and `x` in a
plot definition therefore carries only a label.

```json
"curve": {
    "suffix": ".h5",
    "dataset_pattern": "/frame_{frame_id}/{name}",
    "plots": [
        {
            "id": "range_profile",
            "label": "Range Profile",
            "x": { "label": "Range (m)" },
            "y_label": "Magnitude (dB)",
            "traces": [
                { "name": "mprb",      "label": "Range Bin Power", "color": "#4c9be8" },
                { "name": "cfarThold", "label": "CFAR Threshold",  "color": "#e8734c", "dash": "dash" },
                { "name": "nfEst",     "label": "Noise Floor",     "color": "#8d99ae", "dash": "dot", "width": 1 }
            ]
        }
    ]
}
```

A trace's `name` fills the `{name}` placeholder in the plot's dataset pattern;
an explicit `"dataset"` overrides that. The pattern also sets where a frame's
series live — `/frame_{frame_id}/{name}` by default, which is both what ingest
writes and what a MATLAB struct array reads back as. A nested
`/frames/{frame_id}/{name}` resolves too, for an older export. Optional
per-plot keys: `y_range` (pins the axis instead of estimating it), `x.range`,
and `log_y`. Any number of plots can be declared — the panel gets a selector
when there is more than one.

**Several sources per log.** Curve sidecars are discovered the same way image
streams are, and `suffix` takes either form:

```json
"suffix": ".h5"
"suffix": [".sensor_1.h5", ".sensor_2.h5", ".sensor_3.h5"]
```

A **generic** suffix matches `<stem><suffix>` as the default source and
`<stem>.<id><suffix>` as a named one, so dropping `drive_01.sensor_6.h5` in the
folder adds a sixth sensor with no manifest edit. A **list** names the sidecars
outright — worth the typing when the folder holds `.h5` files that are not
curves (a generic `".h5"` would pick up `drive_01.calibration.h5` and
offer it as a sensor), or when the picker should list sensors in a chosen order
rather than alphabetically. A suffix you list explicitly is always honoured,
including one that would otherwise be skipped as another sidecar's.

Either way the source id is whatever distinguishes the file: the text between
stem and suffix when the suffix is generic, the suffix's own stem when it names
the file outright. Both spellings of the same sensor therefore give the same id,
`sensor_1`. The panel gets a **Sensor** selector, and each source keeps its own
plot list and its own y-range estimate, because one sensor's levels say nothing
about another's.

Non-finite values (`-inf` for bins a threshold does not apply to) are drawn as
gaps in the line rather than being clamped or dropped.

The y axis is held constant across frames rather than autoscaling, so where the
signal sits relative to its threshold stays readable while scrubbing. Ingest
writes a starter config putting every series on one plot, which you then split
and style.

### Images (`image`)

Streams are discovered from the files themselves: `<stem>.mp4` is a log's
default stream and `<stem>.<id>.mp4` adds a named one. `suffix` accepts a list,
and defaults to `[".mp4", ".avi"]` so a recording can be dropped in the folder
in whatever container it came out of the logger in:

```json
"image": {
    "suffix": [".mp4", ".avi"],
    "time_offset": 0.0
}
```

Earlier suffixes win, so a stream shipped as both mp4 and avi serves the mp4 and
skips the transcode. Some recorders stamp a private fourcc onto a stream that is
really a standard codec — `DJLS` frames are plain JPEG-LS — which ffmpeg refuses
until the decoder is named; those tags are mapped in `dataio/video.py`.

The seek is keyed off the log's **wall-clock timestamps**, not the slider index.
For a stream this project encoded the two agree exactly, since frame *i* was
written at *i / fps*. For a recording made alongside the data they do not: a
10 fps dashcam against a 20 Hz radar log shares wall clock and nothing else.
`time_offset` shifts the clip for a camera that did not start rolling at frame 0.

That makes the unit of the table's `Time` column load-bearing, so it is declared
rather than guessed:

```json
"table": { "slider": "Frame", "time_unit": "ms" }
```

Accepts `s` (default), `ms`, `us`, `ns`. A log timestamped in milliseconds and
read as seconds derives a 0.02 Hz capture rate and a video that never moves.

### Reference Overlay

`x_ref` / `y_ref` / `z_ref` mark a moving origin in the 3D view — usually the
host vehicle. By default it draws as a white dot, which says where that origin
is but nothing about how big it is. A `reference` block trades the dot for a
box, so you can see which detections land on the vehicle and which are past it:

```json
"reference": {
    "shape": "box",
    "name": "Host Vehicle",
    "color": "#4c9ffe",
    "opacity": 0.35,
    "dimensions": [1.9, 4.7, 1.5],
    "offset": [0.0, 1.35, 0.75]
}
```

`dimensions` is the full extent along the plot's **x, y and z axes** rather than
length/width/height, because which physical quantity each axis carries is
chosen in the view, not by the manifest. `offset` shifts the box center off the
reference point, for when the reference columns mark a sensor or the rear axle
instead of the middle of the vehicle. The 3D scene makes room for whatever the
box adds beyond the data, so it is never clipped by the axis ranges.

Optional: `edges` (default `true`) draws the wireframe, with `edge_color` and
`edge_width`. With `"shape": "marker"` — or no block at all — the block instead
styles the dot through `color`, `size`, `symbol`, `line_color`, and
`line_width`. The block is read from both v1 and v2 manifests.

### Ingestion

Convert a recording into the layout above:

```bash
python -m dataio.ingest ./data/Example --out ./data/Example_v2
```

Every table in the source folder becomes a log. Each log's raw sidecars are
discovered by basename, mirroring the output convention:

```
raw/MyCase/
├── drive_01.csv          → drive_01.parquet
├── drive_01/             → drive_01.mp4          (per-frame images)
├── drive_01.rear/        → drive_01.rear.mp4
├── drive_01.cloud/       → drive_01.cloud.h5     (<frame_id>.npy)
└── drive_01.curve/       → drive_01.curve.h5 (<series>/<frame_id>.npy, each (N, 2))
```

A single recording's sidecars can also be passed explicitly:

```bash
python -m dataio.ingest ./data/RawCase --out ./data/MyCase --cloud ./raw/cloud --curve ./raw/curve
```

Key options: `--voxel-size` / `--max-points` / `--coord-decimals` control cloud
decimation, `--fps` overrides the capture rate (inferred from timestamps by
default), and `--keyframe-interval` controls image GOP length (1 = all-intra,
keeping every seek frame-exact).

## Installation

1. Clone the repository:

```bash
git clone https://github.com/rookiepeng/sensorview.git
cd sensorview
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Preparing Data

1. Put each case in its own folder under `./data` (or point the app at any
   other directory from the open dialog).
2. Give the case an `info.json` — the manifest described above.
3. Drop the logs in: `<stem>.parquet` plus whatever sidecars exist for it.
   Anything missing simply does not appear.

Existing `.csv` and `.pkl` tables are still offered in the file picker and load
without conversion, as does a v1 `info.json` with its keys at the top level.
Running `dataio.ingest` over such a folder gets you the Parquet layout, the
sidecar conventions, and the performance that comes with them.

### Minimal `info.json`

The table block is the only required one — it names the frame column, the
default 3D axes, and the metadata for each column:

```json
{
  "manifest_version": 2,
  "table": {
    "slider": "Frame",
    "x_3d": "Latitude",
    "y_3d": "Longitude",
    "z_3d": "Height",
    "x_ref": "Host_Latitude",
    "y_ref": "Host_Longitude",
    "z_ref": "None",
    "keys": {
      "Latitude":       { "description": "Latitude (m)",     "decimal": 2, "type": "numerical" },
      "Longitude":      { "description": "Longitude (m)",    "decimal": 2, "type": "numerical" },
      "Height":         { "description": "Height (m)",       "decimal": 2, "type": "numerical" },
      "Time":           { "description": "Time (s)",         "decimal": 2, "type": "numerical" },
      "Frame":          { "description": "Frame",            "decimal": 0, "type": "numerical" },
      "Sensor":         { "description": "Sensor",                         "type": "categorical" },
      "Host_Latitude":  { "description": "Ref Latitude (m)", "decimal": 2, "type": "numerical" },
      "Host_Longitude": { "description": "Ref Longitude (m)","decimal": 2, "type": "numerical" }
    }
  }
}
```

**Parameters:**

- **slider**: integer column used as the temporal axis for the frame slider
- **x_3d, y_3d, z_3d**: default columns for the 3D axes
- **x_ref, y_ref, z_ref**: reference-point columns; `"None"` (the string)
  disables an axis
- **time_unit**: unit of the `Time` column — `s` (default), `ms`, `us`, `ns`
- **keys**: one entry per column
  - **description**: label shown in pickers, filters, and axis titles
  - **decimal**: decimal places for numerical display
  - **type**: `"numerical"` (range filter) or `"categorical"` (multi-select)

`cloud`, `curve`, `image`, and `reference` are all optional; see the sections
above for what each accepts. `data/Example` is a working two-log case that
exercises all of them.

### Running the Application

#### Desktop app

```bash
python app.py
```

Launches through FlaskWebGUI on port 8521 in its own window.

#### Development

Set `DEBUG = True` at the bottom of `app.py` for the Dash dev server with hot
reload.

#### Server

Uncomment the Waitress lines in `app.py` for a deployment:

```python
from waitress import serve
serve(app.server, listen="*:8000")
```

## Architecture

### Server Components

- **Flask/Dash Server**: main application server with REST API endpoints
- **REST API**: `/api/data/<session>/<start_index>` streams buffered frame data
  to the client, `/api/cloud/<session>/<frame>` serves the decimated backdrop,
  and `/api/camera/<session>/<stream>` serves (and, if needed, transcodes) a
  log's video
- **Background Callbacks**: 3D frames are pre-computed off the request thread
  through a `diskcache` job manager, with cooperative cancellation when a newer
  request supersedes an in-flight one
- **Cache Management**: multi-level — server-side `diskcache` FanoutCache for
  session/frame data, client-side IndexedDB via WebWorker
- **Session Isolation**: independent data sessions for multiple users

### Client Components

- **Workbench chrome** (`assets/workbench.js`): panel collapse, splitter drags,
  theme persistence, and the Plotly re-fit that follows any layout change
- **WebWorker** (`assets/worker.js`): pulls frames from the REST API and stores
  them in IndexedDB ahead of the slider
- **Clientside callbacks** (`assets/client_side.js`): worker startup, figure
  swapping from the local buffer, and a bounded in-memory cache of cloud
  backdrops so revisiting a frame costs nothing

## Dependencies

### Python Modules

See `requirements.txt` for the complete list:

- **dash**, **dash-bootstrap-components**, **dash-daq**: web framework and interactive UI components
- **polars**, **pandas**, **numpy**, **pyarrow**: data manipulation and Parquet I/O
- **h5py**: HDF5 sidecars for point clouds and 1D curves
- **imageio-ffmpeg**: bundles a static ffmpeg for image mp4 encoding and transcoding
- **diskcache**: server-side FanoutCache for session and frame data
- **orjson**: high-performance JSON serialization for API responses
- **kaleido**: static image export for plots
- **flaskwebgui**: desktop application wrapper
- **waitress**: production WSGI server (optional)

## Development

### Layout Package (`layouts/`)

One module per region of the shell:

- `app_layout`: the shell itself — which region owns what, and the stores the
  views coordinate through
- `topbar_layout`: brand, dataset breadcrumb, combine-logs, theme, export
- `filter_panel_layout`: the collapsible left rail
- `canvas_layout`: the 3D stage, its floating controls, and the transport
- `inspector_layout`: the camera and curve sections of the right dock
- `analysis_dock_layout`: the two-slot bottom dock and the six panes it hosts
- `modal_layout`: the open-dataset dialog and the load-failure dialog

### Callback Architecture

A modular callback system, one module per view:

- `test_case_view`: dataset selection, loading, and the filter rail it builds
- `control_view`: playback and navigation controls
- `scatter_3d_view`: 3D visualization callbacks
- `scatter_3d_view_background`: background callback pre-computing and buffering
  3D frame data
- `scatter_2d_left_view` & `scatter_2d_right_view`: the two 2D scatter panes
- `heatmap_view`: statistical heatmap visualization
- `histogram_view`: distribution analysis
- `parcats_view`: parallel categories visualization
- `violin_view`: violin plot analysis
- `camera_view`: mp4 stream selection, clientside frame-exact seeking, and
  inspector visibility
- `threshold_view`: per-frame 1D curve plot rendering

### Data IO Package (`dataio/`)

- `manifest`: `info.json` v2 parsing, v1 upgrade, basename sidecar resolution,
  curve plot definitions, non-destructive persistence
- `frames`: frame ids, timestamps, and capture rate derived from the Parquet
  data — shared by the ingest pipeline and the running app
- `radar_store`: Parquet table loading with projection/predicate pushdown
- `dense_store`: HDF5 readers/writers for cloud points and 1D curves
- `decimate`: ingest-time voxel + budget point cloud decimation
- `calibration`: extrinsics → 4×4 transform for cross-sensor alignment
- `video`: mp4 encoding and on-demand transcoding of foreign containers
- `ingest`: pipeline orchestration and CLI

## License

GPL-3.0 License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.
