"""Capture golden values from the Python implementation.

The TypeScript port is checked against its own transliterated tests, which
catch a misread of the spec. They do not catch a faithful-looking port that
disagrees with the Python on real numbers -- a transposed matrix, a rounding
rule, a degrees-versus-radians slip. Those only show as a cloud that is subtly
in the wrong place.

So the answers come from the code being replaced, once, and are checked in.
Run while the Python still exists::

    conda run -n dev python scripts/golden.py > test/fixtures/golden.json

Delete this, and the fixture, when the Python goes.

Author: Zhengyu Peng
License: GPL-3.0
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataio.calibration import Calibration, apply_transform, rotation_matrix
from dataio.manifest import Manifest, normalize_reference_display
from frame_sources import _video_frame_for

CASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "NuScenes"
)


def main() -> None:
    """
    Emit the golden values as JSON on stdout.

    Returns:
        None
    """
    # Seeded, so re-running produces the same fixture and a diff means a real
    # change rather than new random draws.
    rng = np.random.default_rng(7)
    out = {"rotation": [], "transform": [], "video": [], "manifest": None}

    for _ in range(200):
        roll, pitch, yaw = rng.uniform(-np.pi, np.pi, 3)
        out["rotation"].append(
            {
                "rpy": [roll, pitch, yaw],
                "matrix": rotation_matrix(roll, pitch, yaw).ravel().tolist(),
            }
        )

    for _ in range(100):
        translation = rng.uniform(-10, 10, 3)
        degrees = rng.uniform(-180, 180, 3)
        points = rng.uniform(-50, 50, (4, 3))
        calibration = Calibration(
            translation=translation.tolist(), rotation_rpy_deg=degrees.tolist()
        )
        out["transform"].append(
            {
                "translation": translation.tolist(),
                "rpy_deg": degrees.tolist(),
                "points": points.ravel().tolist(),
                "result": apply_transform(points, calibration).ravel().tolist(),
            }
        )

    for _ in range(300):
        total = int(rng.integers(1, 200))
        local = int(rng.integers(0, total))
        frames = int(rng.integers(1, 500))
        out["video"].append(
            [local, total, frames, _video_frame_for(local, total, frames)]
        )

    # The manifest, read from the real case. Normalizing a hand-written block
    # is where a port drifts quietly: a default filled in differently, a mesh
    # edge derived in another order, a colour that falls back somewhere else.
    # None of it raises; it just draws something slightly wrong.
    if os.path.isdir(CASE):
        manifest = Manifest.load(CASE)
        stem = "scene_0061"
        out["manifest"] = {
            "name": manifest.name,
            "frame_key": manifest.table.get("slider"),
            "cloud_suffix": manifest.cloud_suffix,
            "cloud_display": manifest.cloud_display(),
            "cloud_columns": manifest.cloud_columns(),
            "curve_suffixes": manifest.curve_suffixes,
            "curve_sources": [
                {
                    "id": s["id"],
                    "label": s["label"],
                    "file": os.path.basename(s["file"]),
                }
                for s in manifest.curve_sources(stem)
            ],
            "curve_plots": manifest.curve_plots(),
            "image_streams": [
                {
                    "id": s["id"],
                    "label": s["label"],
                    "file": os.path.basename(s["file"]),
                }
                for s in manifest.image_streams(stem)
            ],
            "reference_columns": manifest.reference_columns(),
            "reference_display": normalize_reference_display(manifest.reference),
            "stem_of": manifest.stem_of(os.path.join(CASE, "scene_0061.parquet")),
        }

    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
