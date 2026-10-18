"""
Capture numpy's histogram answers for the real table.

The `auto` bin estimator is the only real numeric port in the view layer and
the easiest to get subtly wrong: a bin width a few percent off still draws a
plausible histogram, just not the same one. These are numpy's own answers on
the columns the views actually bin.
"""

import io
import json
import sys

import numpy as np
import polars as pl

sys.path.insert(0, ".")

TABLE = "data/NuScenes/scene_0061.parquet"

frame = pl.read_parquet(TABLE)
numeric = [
    name
    for name, dtype in zip(frame.columns, frame.dtypes)
    if dtype.is_numeric()
]

cases = []
for name in numeric:
    values = frame[name].cast(pl.Float64).to_numpy()
    values = values[np.isfinite(values)]
    if values.size == 0:
        continue
    edges = np.histogram_bin_edges(values, bins="auto")
    cases.append(
        {
            "column": name,
            "n": int(values.size),
            "bins": int(len(edges) - 1),
            "edges": [float(v) for v in edges],
            "p25": float(np.percentile(values, 25)),
            "p75": float(np.percentile(values, 75)),
        }
    )

# Degenerate shapes the real table does not contain, but a filtered view will.
synthetic = []
for label, values in (
    ("one value", np.array([3.0])),
    ("all identical", np.full(50, 7.5)),
    ("two values", np.array([0.0, 1.0])),
    ("integers", np.arange(100, dtype=float)),
    ("tight iqr", np.concatenate([np.zeros(999), np.array([1000.0])])),
):
    edges = np.histogram_bin_edges(values, bins="auto")
    synthetic.append(
        {
            "label": label,
            "values": [float(v) for v in values[:12]],
            "n": int(values.size),
            "bins": int(len(edges) - 1),
            "edges": [float(v) for v in edges],
        }
    )

# A 2D count grid, as the log-scale heatmap builds it.
x = frame["X"].cast(pl.Float64).to_numpy()
y = frame["Y"].cast(pl.Float64).to_numpy()
keep = np.isfinite(x) & np.isfinite(y)
x, y = x[keep], y[keep]
xe = np.histogram_bin_edges(x, bins="auto")
ye = np.histogram_bin_edges(y, bins="auto")
counts, _, _ = np.histogram2d(x, y, bins=[xe, ye])

io.open("test/fixtures/histogram.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(
        {
            "table": TABLE,
            "cases": cases,
            "synthetic": synthetic,
            "hist2d": {
                "shape": list(counts.shape),
                "total": float(counts.sum()),
                # Row sums rather than the whole grid: thousands of cells of
                # mostly zeros, and a row sum that matches pins the binning
                # of both axes just as firmly.
                "rowSums": [float(v) for v in counts.sum(axis=1)],
                "colSums": [float(v) for v in counts.sum(axis=0)],
                "max": float(counts.max()),
            },
        },
        indent=1,
    )
    + "\n"
)
print("columns:", len(cases), "synthetic:", len(synthetic))
print("hist2d:", counts.shape, "total", counts.sum())
for case in cases[:3]:
    print(" ", case["column"], case["bins"], "bins")
