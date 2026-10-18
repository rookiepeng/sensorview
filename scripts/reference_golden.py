"""
Capture ReferenceStore's answers for the real sidecar.

The TypeScript port asserts against these. Column resolution, the zero
defaults for a field with no column, and the bounds that widen the scene's
axis ranges are all things a rewrite can get subtly wrong and still draw
something plausible.
"""

import io
import json
import sys

sys.path.insert(0, ".")

from dataio.reference import POSE_FIELDS, ReferenceStore  # noqa: E402

PATH = "data/NuScenes/scene_0061.reference.parquet"

cases = []


def capture(label, columns, frame_key, frames):
    store = ReferenceStore.open(PATH, columns=columns, frame_key=frame_key)
    cases.append(
        {
            "label": label,
            "columns": columns,
            "frameKey": frame_key,
            "usable": bool(store.is_usable),
            "available": store.available_columns,
            "resolved": store.resolved_columns,
            "bounds": (
                {k: list(v) for k, v in store.bounds().items()}
                if store.bounds()
                else None
            ),
            "poses": {
                str(f): (
                    {k: store.pose(f)[k] for k in POSE_FIELDS} if store.pose(f) else None
                )
                for f in frames
            },
        }
    )


store = ReferenceStore.open(PATH, columns=None, frame_key="Frame")
ids = sorted(store._poses.keys())
sample = [ids[0], ids[len(ids) // 2], ids[-1], ids[-1] + 10_000]

capture("unmapped", None, "Frame", sample)
capture("explicit", {f: f for f in POSE_FIELDS} | {"frame": "frame"}, "Frame", sample)
# A field cleared in the picker resolves to nothing, and its value is zero.
capture("yaw cleared", {"yaw": ""}, "Frame", sample)
# No x column at all: nothing to place, so the store is not usable.
capture("x cleared", {"x": ""}, "Frame", sample)
# Pointed at a column the file does not have: fall back to the field's name.
capture("x misnamed", {"x": "not_a_column"}, "Frame", sample)

io.open("test/fixtures/reference.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps({"path": PATH, "cases": cases}, indent=1) + "\n"
)
print("frames:", len(ids), "sample:", sample)
print("resolved:", cases[0]["resolved"])
print("bounds:", cases[0]["bounds"])
