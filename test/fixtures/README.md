# Golden fixtures

Every file here was captured from the Python application this one replaces,
running against `data/NuScenes`. They are the record of what the old app
answered, and the TypeScript is asserted against them rather than against
anything derived from itself.

The capture scripts lived in `scripts/` and imported the Python modules
directly. They were deleted with those modules, because a script that cannot
run is worse than a note saying what it did — it looks runnable. This is the
note.

| File | Captured from | What it pins |
|---|---|---|
| `golden.json` | `dataio.calibration`, `frame_sources._video_frame_for` | A sample of the ZYX rotation product and transform, and the half-up rounding in the frame-count-to-frame-count video mapping. |
| `filters.json` | `utils.filters.filter_all` | 21 filter states over the real table, as a base64 row bitmask. NaN, ±Inf, an empty categorical selection, and the visibility picker's deliberate two-or-more no-op. |
| `reference.json` | `dataio.reference.ReferenceStore` | Five column-mapping cases: unmapped, explicit, a field a picker cleared, a field pointed at a missing column, and no `x` at all. Plus the poses and the position extent. |
| `curves.json` | `dataio.dense_store.CurveStore`, `_split_xy` | The (N,2) and (2,N) orientations MATLAB makes interchangeable, and the real sidecar's samples. NaN crosses as `null`: JSON has no NaN, and `json.dump` writes a bare `NaN` no other parser reads. |
| `histogram.json` | `numpy.histogram_bin_edges(bins='auto')`, `numpy.histogram2d` | Bin edges for every numeric column, the degenerate shapes a filtered view produces, and a 119×74 count grid by row and column sums. |
| `views.json` | `viz.viz`, `view_callbacks/*` | Trace order and contents for the analysis views. Trace order is the load-bearing part: it is the order the colorway is assigned in, so getting it wrong recolors every view at once. |
| `palette` (`src/shared/palette.ts`) | `plotly.io.templates["plotly"]`, `plotly.colors` | Plotly's own colorway and the seventeen colorscales the rail offers. Not a fixture but captured the same way, and regenerable from `plotly.py` in a throwaway environment if the colormap list ever changes. |

To re-capture any of these you would need the Python back; `git log` has it,
and the commit that deleted it names this file.
