# SensorView

<img src="./assets/sensorview_logo.svg" alt="logo" width="200"/>

A desktop workbench for exploring multi-sensor logs. Its core purpose is data
analysis across three axes: **filtering** the frame table down to the data that
matters, **multi-dimensional inspection** of the same instant through a 3D
point cloud, camera frame and 1D curves side by side, and **statistical
analysis** via six linked views -- all driven by one frame slider and one set
of filters.

Electron, React and TypeScript throughout. It was a Flask/Dash application
until the port recorded in `git log`; nothing of that remains, and the tests
that pinned its behaviour were transliterated rather than rewritten, with the
numeric ones asserting against answers captured from it.
## Screenshots

The workbench on a nuScenes scene: the radar point cloud with its decimated
lidar backdrop and the ego-vehicle overlay, the camera frame and range profile
for the same instant in the inspector, and two statistical views in the dock.

<img src="./assets/screenshot.gif" alt="SensorView workbench, dark theme" width="900"/>

## The Workbench

Everything is sized against the viewport rather than flowing down a page.
Nothing scrolls except panel interiors, so no view is ever more than a click
from visible — which is the point, since all of them describe the same frame.

| Region | Holds |
| --- | --- |
| **Top bar** | Dataset breadcrumb (it *is* the file picker), combine-logs, theme toggle, export menu |
| **Left rail** | Display options and the per-column filters built from the manifest |
| **Canvas** | The 3D point cloud — the only region that grows |
| **Inspector** | The camera stream and the curve plot for the current frame |
| **Transport** | Frame scrubbing, playback, buffering progress |
| **Analysis dock** | Two slots, each showing any one of the six statistical views |

The rail, inspector, and dock each have a splitter on their inner edge; whatever
they give up, the canvas takes. Collapse, drag and theme are the renderer's own:
there is no server for them to be anything to.

### 3D Canvas

Interactive 3D scatter with color mapping, a decay slider that fades previous
frames in behind the current one, and an overlay mode that draws every frame at
once. View settings float over the plot instead of docking above it, since
they're touched only a few times a session. Axis and reference-column mapping
### The Scene

three.js, and the whole window: the canvas spans the viewport and every panel
floats over it as glass, so the cloud is the background rather than a pane
among panes. There is no box cage -- the extent is given by a ground plane at
zero height that fades into the page background at its rim, with the range
labels lying in that plane and three short coloured axes out of the origin,
after the 3D view in
[movens-link](https://github.com/rookidroid/movens-link). The floor is centred
on the data's origin rather than the middle of the filter box, so it reads as
ground around the sensor even when the box is far off-centre.

It owns its camera and its own on-demand render loop -- `invalidate()` on
change, idle at zero cost -- so React never drives a frame. Over the scene sit
a colorbar, a clickable legend, the axis ranges, camera presets and a
frame-rate and point-count readout. Hover and click-to-hide work through GPU
colour picking: one pixel is rendered and read back per pointer move, so cost
does not grow with the number of points.

The scene and the 2D views read one palette. Plotly's own colorway and
colorscales are captured into `src/shared/palette.ts`, so a category coloured
one way in the dock and another in the scene is not a thing that can happen.


### Filter Rail

Filters are generated per column from the manifest — a range slider for each
numerical key, a multi-select for each categorical one. Every view reads the
same filtered table, so a filter change moves all of them together. Points can
be relabelled *hidden* by clicking or lassoing them, then filtered on that
label.

### Inspector

The camera stream and curve plot for the current frame, docked on the right.
Each section has its own minimize toggle and restores from a chip in the panel
bar; the curve section grows into whatever height the image gives up. Sections
hide independently, and the whole inspector hides when a log has neither
sidecar, so the canvas reclaims the width.

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

Slot assignment is the enable switch: a view in a slot is live, everything else
is idle, and a collapsed dock computes nothing.

### Transport and Buffering
### Transport

The frame slider is the single source of truth for time: a video element never
plays on its own, it is seeked to whatever frame the rest of the app shows, and
playback runs the same path. There is no buffering apparatus -- the table is in
memory, so scrubbing it costs nothing and there is nothing to pre-fetch.

### Combining Logs

Several logs open at once from the breadcrumb, checkbox per log, the first
leading. Combining concatenates their rows, so a frame id is the only thing
tying a slider position back to the log whose sidecars hold its cloud, pose,
curves and video -- and logs are free to number their frames the same way, so
one position can belong to several. The camera and curve panels draw one per
owner; the cloud, the pose and the exports take the leader.

A clip is seeked by its log's **own** frame number, not the slider position, so
a log whose frames sit after another's still maps onto its own recording end to
end.

### Other

- **Dark/Light theme** -- chrome, Plotly figures and the WebGL scene switch
  together. The scene reads its colours back off the same CSS custom
  properties, so the two cannot drift. The choice persists in the settings file
- **Export** -- the filtered table as CSV, the scene as PNG or as a captioned
  HTML page, the open dock view as a self-contained HTML page with Plotly
  inlined, and every frame as a video recorded from the scene itself

---

## Data Architecture

Each kind of sensor data gets the storage format that suits its shape, joined by
a single **frame id**:

| Data | Format | Filterable | Updates on |
| --- | --- | --- | --- |
| Table (`table`) | Parquet (tidy table) | **Yes** — full filter pipeline | filter changes + frame changes |
| Cloud (`cloud`) | HDF5, pre-decimated | No — fixed backdrop | frame changes only |
| Curves (`curve`) | HDF5, one (N, 2) pair per frame | No | frame changes only |
| Images (`image`) | mp4, all-intra | No | frame changes only |
| Reference pose (`reference`) | Parquet, one row per frame | No | frame changes only |

The reasoning behind the split:

- **The table is the only queried dataset**, so it stays columnar: Parquet gives
  compression plus projection/predicate pushdown, and MATLAB reads it natively
  (`parquetread`/`parquetwrite`).
- **Cloud and curves are display-only**, frame-indexed blobs — nobody queries
  them by column, so a chunked HDF5 dataset per frame (equally native in
  MATLAB via `h5read`) beats Parquet's columnar overhead.
- **Clouds arrive pre-decimated**; the backdrop has no runtime controls, so no
  full-resolution data is kept on the read path.
- **Images are seeked client-side** via a native `<video>` element and
  `currentTime`, so scrubbing costs no server round trip. All-intra encoding
  lets the browser seek to any frame; a container it can't play (a vendor
  `.avi` off a logger) is transcoded once, on first request, and cached under the
  OS temp directory.
- **Reference pose is per frame, not per detection** — six extra columns on
  every one of a log's 300k rows to say where one vehicle was would be
  wasteful, and table columns can't express orientation anyway.

Because the display-only views never depend on filter state, dragging a filter
slider re-renders the table alone — it never re-reads the cloud, curves, pose, or
video.

**SensorView reads these files; it does not write them.** Producing the
layout is the job of whatever exports the data. The complete on-disk
contract — exact filenames, HDF5 paths, dtypes, and every manifest key, plus
a worked converter and a validation checklist — lives in
[DATA_FORMAT.md](DATA_FORMAT.md).

---

---

## Installation

```bash
npm ci
```

Node 24 or newer. Nothing else: the Parquet reader, the HDF5 reader and ffmpeg
all arrive as npm packages, two of them native and unpacked from the asar at
build time.

## Usage

### Preparing data

A case is a folder of logs plus an `info.json` manifest. SensorView reads these
files and does not write them, apart from the manifest when you change an axis
mapping. The complete on-disk contract lives in
[DATA_FORMAT.md](DATA_FORMAT.md).

### Bundled case

`data/NuScenes` holds five scenes converted from nuScenes -- radar tables,
decimated lidar clouds, curve sidecars, camera mp4s and ego-vehicle pose. It is
what the checks run against. `data/NuScenes/build_nuscenes_case.py` is the
converter that produced it; it is not part of the application and needs the
nuScenes devkit.

### Running

```bash
npm run dev
```

Opens the app with the renderer on Vite's dev server. `SENSORVIEW_OPEN_CASE`
names a case to open at startup instead of using the dialog.

```bash
npm run web
```

Serves the renderer alone in a browser tab against a checked-in fixture, which
is faster to iterate on than an Electron restart. The bridge the renderer talks
to is the same interface either way -- `src/preload` provides it in Electron,
`src/renderer/lib/webBridge.ts` in a tab.

### Checks

```bash
npm run typecheck
npm test
npm run lint
npm run smoke -- --case data/NuScenes
```

The smoke run is the one worth knowing about. It builds, then runs fifteen
checks **inside Electron against that build**: the `sv://` protocol and its
Range handling, the data process reading real Parquet and HDF5, and a probe
window that opens the bundled case and asserts what the scene drew, what the
dock rendered, that combining two logs seeks each camera by its own frame, and
that every export writes a file -- reopening the exported HTML page in a window
with no preload to prove it is self-contained.

Flags: `--save-dir` runs the exports, `--shot` captures a PNG of the probe
window, `--packaged` runs `dist/win-unpacked` instead of the dev build, which
is the only configuration where an asar or a missing runtime can show up.

### Packaging

```bash
npm run dist
```

---

## Architecture

Four processes, and a contract between them.

| | |
|---|---|
| `src/main` | The window, the menus, the save and open dialogs, the `sv://` protocol, and the client for the data process |
| `src/preload` | The bridge. ~20 lines, annotated with the contract |
| `src/shared` | The IPC contract plus the logic both sides need: the table and its filters, calibration, the video frame mapping, log combining, numpy's histogram binning |
| `src/data` | A `utilityProcess` running polars, h5wasm and ffmpeg |
| `src/renderer` | React, the three.js modules under `gl/`, the Plotly figures under `figures/` |

**The data layer is its own process** because its readers are native. A
sandboxed renderer cannot `require` a `.node`, and loading a 40 MB addon on the
window's process would stall the window; a native fault in a separate process
costs a reload of the data layer rather than the app.

**The contract is one TypeScript interface.** `src/shared/types.ts` describes
every channel, and the preload is annotated with it -- so typechecking the
preload is what guarantees the renderer's calls. Every result is normalized to
`{ok, status, data?, error?}`: errors do not cross as exceptions, and renderer
code has no try/catch around IPC.

**The table lives in the renderer.** It is 19,756 rows here, and filtering it
is one pass over typed arrays -- sub-millisecond, so it runs on every filter
change with no caching anywhere. The Dash app had a disk cache, a background
worker pre-computing every frame and an IndexedDB prefetch; all three existed
because each filter change crossed a network boundary, and none of them was
ported because none of them has a reason to exist.

**`sv://` replaces the media routes.** A `<video>` cannot scrub a file it
cannot range-request, so main serves one with Range support -- and only from
directories the user has opened this session. The renderer may ask for any
path and can widen nothing.

### Tests

`test/` holds vitest suites over `src/shared` and `src/data` in a node
environment; the React tree is verified by running the app, which is what the
smoke run does. Where a port had numeric or formatting behaviour, the answers
were captured from the Python into `test/fixtures` and are asserted against --
see [test/fixtures/README.md](test/fixtures/README.md) for what each one pins
and where it came from.

## License

GPL-3.0 License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.
