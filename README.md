# SensorView

<img src="./assets/sensorview_logo.svg" alt="logo" width="200"/>

A Flask/Dash-based web application for sensor data visualization and analysis with advanced caching and interactive features.

## Screenshots

## Features

### Core Visualization Modes

#### 3D Visualization and Filtering

- Interactive 3D scatter plots for data visualization
- Advanced filtering and color mapping options
- Decay effects for temporal data analysis

<img src="./assets/3d.gif" alt="3d" width="600"/>

#### 2D Visualization and Filtering

- Dual-panel 2D scatter plots (left and right views)
- Synchronized data filtering across multiple views
- Interactive data exploration tools

<img src="./assets/2d.gif" alt="2d" width="600"/>

#### Statistical Visualization

- Heatmap visualization for correlation analysis
- Histogram analysis with customizable binning
- Parallel categories (parcats) for categorical data
- Violin plots for distribution analysis

<img src="./assets/stat.gif" alt="stat" width="600"/>

### Advanced Features

- **Efficient Data Processing**: WebWorker-based caching system for smooth performance
- **Multiple File Support**: Load and compare multiple datasets simultaneously
- **Session Management**: Isolated data sessions for concurrent users
- **Interactive Controls**: Frame navigation, playback controls, and data updates
- **Dark/Light Mode**: Theme switching for different viewing preferences
- **Data Buffering**: IndexedDB-based client-side caching for large datasets
- **Configuration Persistence**: JSON-based configuration management
- **Test Case Management**: Organized data file and test case selection

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
series live, which covers `/frames/{frame_id}/{name}` for a sidecar ingest wrote
and `/frame_{frame_id}/{name}` for a MATLAB struct array alike. Optional
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

### Subview Panel

The image stream and curve plot live in a floating panel over the 3D view rather
than stacked below it — all three show the same instant, so scrolling between
them defeats the purpose. The panel is draggable by its header, minimizes to a
title bar, resizes from its bottom-right corner, and stays clamped inside the
viewport. It hides itself entirely when a log has neither an image stream nor
curve data, and each half hides independently.

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

## Architecture

### Server Components

- **Flask/Dash Server**: Main application server with REST API endpoints
- **REST API**: `/api/data/<session>/<start_index>` endpoint for streaming buffered frame data to the client
- **WebWorker Integration**: Client-side data management and processing
- **Cache Management**: Multi-level caching — server-side `diskcache` FanoutCache for session/frame data, client-side IndexedDB via WebWorker
- **Session Isolation**: Independent data sessions for multiple users

### Client Components

- **Interactive UI**: Modal dialogs for configuration and file selection
- **Dynamic Updates**: Automatic data refresh and visualization updates
- **IndexedDB Storage**: Browser-based data persistence and buffering

## Dependencies

### Python Modules

See `requirements.txt` for complete list:

- **dash**, **dash-bootstrap-components**, **dash-daq**: Web framework and interactive UI components
- **polars**, **pandas**, **numpy**, **pyarrow**: Data manipulation and Parquet I/O
- **h5py**: HDF5 sidecars for point clouds and 1D curves
- **imageio-ffmpeg**: Ingest-time only; bundles a static ffmpeg for image mp4 encoding
- **diskcache**: Server-side FanoutCache for session and frame data
- **orjson**: High-performance JSON serialization for API responses
- **kaleido**: Static image export for plots
- **flaskwebgui**: Desktop application wrapper
- **waitress**: Production WSGI server (optional)

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd sensorview
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Data Preparation

1. **Data Format**: Save data as `.pkl` (pickle) or `.csv` files
2. **Directory Structure**: Organize data under `./data` directory
3. **Configuration**: Create `info.json` in each test case directory

### Directory Structure Example

```
./data/
├── Example/
│   ├── info.json          # Required: Column specifications
│   ├── sensor_data.csv    # Data files
│   ├── test_results.pkl   # Alternative format
│   └── subfolder/         # Nested data organization
│       └── more_data.csv
└── Another_Test/
    ├── info.json
    └── dataset.pkl
```

### Configuration File (info.json)

Specify data column mappings, visualization settings, and metadata:

```json
{
  "slider": "Frame",
  "x_3d": "Latitude",
  "y_3d": "Longitude",
  "z_3d": "Height",
  "x_ref": "Host_Latitude",
  "y_ref": "Host_Longitude",
  "z_ref": "None",
  "keys": {
    "Height": {
      "description": "Height (m)",
      "decimal": 2,
      "type": "numerical"
    },
    "Longitude": {
      "description": "Longitude (m)",
      "decimal": 2,
      "type": "numerical"
    },
    "Latitude": {
      "description": "Latitude (m)",
      "decimal": 2,
      "type": "numerical"
    },
    "Time": {
      "description": "Time (s)",
      "decimal": 2,
      "type": "numerical"
    },
    "Sensor": {
      "description": "Sensor",
      "type": "categorical"
    },
    "Frame": {
      "description": "Frame",
      "decimal": 0,
      "type": "numerical"
    },
    "Host_Latitude": {
      "description": "Ref Latitude (m)",
      "decimal": 2,
      "type": "numerical"
    },
    "Host_Longitude": {
      "description": "Ref Longitude (m)",
      "decimal": 2,
      "type": "numerical"
    }
  }
}
```

**Configuration Parameters:**

- **slider**: Column to use for frame navigation/time slider
- **x_3d, y_3d, z_3d**: Default columns for 3D visualization axes
- **x_ref, y_ref, z_ref**: Reference point columns for 3D visualization; set to `"None"` (string) to disable a reference axis
- **keys**: Column definitions with metadata:
  - **description**: Human-readable column description
  - **decimal**: Number of decimal places for numerical display
  - **type**: Data type ("numerical" or "categorical")

### Running the Application

#### Development Mode

```bash
python app.py
```

Set `DEBUG = True` in app.py for development with hot reload.

#### Production Mode (Desktop App)

```bash
python app.py
```

The application will launch as a desktop application using FlaskWebGUI on port 8521.

#### Server Mode

Uncomment the Waitress server lines in app.py for production deployment:

```python
from waitress import serve
serve(app.server, listen="*:8000")
```

### Application Features

#### Configuration Modal

- **Data Path Selection**: Choose root directory for data files
- **Test Case Selection**: Pick from available test cases
- **File Selection**: Select specific data files to analyze
- **Settings Persistence**: Automatic configuration saving

#### Visualization Controls

- **Frame Navigation**: Manual frame selection or automatic playback
- **View Customization**: Toggle between different visualization modes
- **Color Mapping**: Customizable color schemes and mappings
- **Filtering**: Interactive data filtering and selection
- **Multi-file Comparison**: Load multiple files for comparative analysis

#### Data Management

- **Automatic Caching**: Server and client-side data buffering
- **Session Management**: Isolated data sessions
- **Dynamic Updates**: Automatic data refresh and synchronization
- **Performance Optimization**: IndexedDB storage for large datasets

## Development

### Callback Architecture

The application uses a modular callback system with separate modules for different views:

- `test_case_view`: Test case management
- `control_view`: Playback and navigation controls
- `scatter_3d_view`: 3D visualization callbacks
- `scatter_3d_view_background`: Background callback for pre-computing and buffering 3D frame data
- `scatter_2d_left_view` & `scatter_2d_right_view`: 2D visualization panels
- `heatmap_view`: Statistical heatmap visualization
- `histogram_view`: Distribution analysis
- `parcats_view`: Parallel categories visualization
- `violin_view`: Violin plot analysis
- `camera_view`: mp4 stream selection, clientside frame-exact seeking, and
  subview panel visibility
- `threshold_view`: Per-frame 1D curve plot rendering

### Data IO Package (`dataio/`)

- `manifest`: `info.json` v2 parsing, v1 upgrade, basename sidecar resolution,
  curve plot definitions, non-destructive persistence
- `frames`: Frame ids, timestamps, and capture rate derived from the Parquet
  data — shared by the ingest pipeline and the running app
- `radar_store`: Parquet table loading with projection/predicate pushdown
- `dense_store`: HDF5 readers/writers for cloud points and 1D curves
- `decimate`: Ingest-time voxel + budget point cloud decimation
- `calibration`: Extrinsics → 4×4 transform for cross-sensor alignment
- `video`: Camera mp4 encoding
- `ingest`: Pipeline orchestration and CLI

### Client-side Functions

The application includes several client-side callback functions for:

- WebWorker initialization and management
- IndexedDB data storage and retrieval
- Dynamic figure updates and buffering
- Performance optimization

## License

GPL-3.0 License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.
