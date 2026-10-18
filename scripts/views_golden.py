"""
Capture what the Dash views draw, for the TypeScript ports to match.

Not the whole figure dict -- Plotly's defaults are noise and the port writes
traces out by hand where Express generated them. What matters is the data: how
many traces, in what order, with how many points each, and the values
themselves where a port could get them subtly wrong.
"""

import io
import json
import sys

import numpy as np
import polars as pl

sys.path.insert(0, ".")

TABLE = "data/NuScenes/scene_0061.parquet"

frame = pl.read_parquet(TABLE)
numeric = [n for n, d in zip(frame.columns, frame.dtypes) if d.is_numeric()]
categorical = [n for n, d in zip(frame.columns, frame.dtypes) if d == pl.String]

X, Y = "X", "Y"
CAT = categorical[0]

# Sorted level order is what the colorway is assigned in, so it decides every
# trace's colour across every view.
levels = sorted(frame[CAT].unique().to_list())

scatter_groups = []
for level in levels:
    subset = frame.filter(pl.col(CAT) == level)
    scatter_groups.append(
        {
            "name": level,
            "n": subset.height,
            "firstX": float(subset[X][0]),
            "firstY": float(subset[Y][0]),
        }
    )

# The log-scale heatmap, which is where the numpy port is actually used.
x = frame[X].cast(pl.Float64).to_numpy()
y = frame[Y].cast(pl.Float64).to_numpy()
keep = np.isfinite(x) & np.isfinite(y)
x, y = x[keep], y[keep]
xe = np.histogram_bin_edges(x, bins="auto")
ye = np.histogram_bin_edges(y, bins="auto")
counts, _, _ = np.histogram2d(x, y, bins=[xe, ye])
log_counts = np.log1p(counts.T)
x_centers = (xe[:-1] + xe[1:]) / 2
y_centers = (ye[:-1] + ye[1:]) / 2

# A violin's y values per category, summarised: the trace ships the raw
# samples and Plotly computes the kernel, so matching the samples is matching
# the picture.
violin_groups = []
for level in levels:
    subset = frame.filter(pl.col(CAT) == level)[Y].cast(pl.Float64).to_numpy()
    finite = subset[np.isfinite(subset)]
    violin_groups.append(
        {
            "name": level,
            "n": int(finite.size),
            "min": float(finite.min()),
            "max": float(finite.max()),
            "mean": float(finite.mean()),
        }
    )

io.open("test/fixtures/views.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(
        {
            "table": TABLE,
            "x": X,
            "y": Y,
            "categorical": CAT,
            "levels": levels,
            "rows": frame.height,
            "numeric": numeric,
            "scatter": {"groups": scatter_groups},
            "heatmap": {
                "shape": [len(y_centers), len(x_centers)],
                "xCenters": [float(v) for v in x_centers[:5]],
                "yCenters": [float(v) for v in y_centers[:5]],
                "zMax": float(log_counts.max()),
                "zSum": float(log_counts.sum()),
                "nonZero": int((log_counts > 0).sum()),
            },
            "violin": {"groups": violin_groups},
        },
        indent=1,
    )
    + "\n"
)
print("levels:", levels)
print("heatmap:", log_counts.shape, "sum", round(float(log_counts.sum()), 6))
