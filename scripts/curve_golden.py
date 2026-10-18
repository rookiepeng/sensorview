"""
Capture CurveStore's answers for a real curve sidecar.

The (N,2) / (2,N) split is the part worth pinning: MATLAB writes column-major,
so the same logical curve reads back either way, and a port that handles only
one orientation still draws a plausible line from the other.
"""

import io
import json
import sys

import math

import numpy as np

sys.path.insert(0, ".")

from dataio.dense_store import CurveStore, _split_xy  # noqa: E402

PATH = "data/NuScenes/scene_0061.radar_front.h5"
PATTERN = "/frame_{frame_id}/{name}"

def number(value):
    """
    JSON has no NaN, and `json.dump` writes a bare `NaN` that no other
    parser reads -- the same trap the manifest writer has to avoid. NaN is a
    real value in these curves (a bin with no return), so it crosses as null
    and the test reads null back as NaN.
    """
    value = float(value)
    return None if math.isnan(value) else value


store = CurveStore(PATH)
signals = store.signals(PATTERN)

samples = []
for name in signals:
    x, y = store.read_curve(PATTERN.replace("{name}", name), 0)
    samples.append(
        {
            "name": name,
            "n": int(len(y)),
            "hasX": x is not None,
            "x": [number(v) for v in x[:4]] if x is not None else None,
            "y": [number(v) for v in y[:4]],
            "yLast": number(y[-1]),
        }
    )

# Both orientations of the same logical curve, through the splitter itself.
pair = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]], dtype=np.float32)
orientations = []
for label, raw in (("rows are samples", pair), ("columns are samples", pair.T)):
    x, y = _split_xy(raw)
    orientations.append(
        {
            "label": label,
            "shape": list(raw.shape),
            "x": [float(v) for v in x] if x is not None else None,
            "y": [float(v) for v in y],
        }
    )

# Neither orientation: plotted against the sample index.
flat = np.array([5.0, 6.0, 7.0], dtype=np.float32)
x, y = _split_xy(flat)
orientations.append(
    {
        "label": "one dimension",
        "shape": list(flat.shape),
        "x": None,
        "y": [float(v) for v in y],
    }
)

io.open("test/fixtures/curves.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(
        {
            "path": PATH,
            "pattern": PATTERN,
            "signals": signals,
            "samples": samples,
            "orientations": orientations,
        },
        indent=1,
    )
    + "\n"
)
print("signals:", signals)
print("first:", samples[0] if samples else None)
