"""Capture filter results from the Python, over the real table.

``utils.filters.filter_all`` is the one function every view runs on every
filter change, and the TypeScript port has to agree with it exactly -- not
approximately, and not only on the cases I thought to write down. A row that
should have dropped out and did not is a point drawn that the user filtered
away, which nothing on screen flags.

So the cases are generated against ``data/NuScenes``: random range and category
combinations, including the edge cases that are easy to get wrong -- an empty
category list, a range that excludes everything, a column full of NaN, a
visibility selection of two states. The surviving row indices are recorded and
asserted against in ``test/filter.test.ts``.

Run while the Python still exists::

    conda run -n dev python scripts/filter_golden.py > test/fixtures/filters.json

Delete this, and the fixture, when the Python goes.

Author: Zhengyu Peng
License: GPL-3.0
"""

import base64
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataio.radar_store import load_radar
from utils.filters import filter_all

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(ROOT, "data", "NuScenes", "scene_0061.parquet")


def pack_mask(mask: "np.ndarray", rows: int) -> str:
    """
    Pack a boolean mask into base64, one bit per row, LSB first.

    Args:
        mask: Boolean array, one entry per row.
        rows: Row count, so the reader knows where the padding starts.

    Returns:
        Base64 of the packed bits.
    """
    packed = np.packbits(np.asarray(mask, dtype=bool)[:rows], bitorder="little")
    return base64.b64encode(packed.tobytes()).decode("ascii")


def build_visible_table(data: pd.DataFrame) -> pd.DataFrame:
    """
    A visibility table with a deterministic scatter of hidden rows.

    Args:
        data: The loaded table.

    Returns:
        One ``_VIS_`` column, index-aligned to ``data``.
    """
    states = np.where(np.arange(len(data)) % 7 == 0, "hidden", "visible")
    return pd.DataFrame({"_VIS_": states}, index=data.index)


def main() -> None:
    """
    Emit the filter cases as JSON on stdout.

    Returns:
        None
    """
    data = load_radar(file_list=[TABLE])
    visible_table = build_visible_table(data)

    numeric = [
        name
        for name in data.columns
        if pd.api.types.is_numeric_dtype(data[name]) and name != "Frame"
    ]
    categorical = [
        name for name in data.columns if not pd.api.types.is_numeric_dtype(data[name])
    ]

    rng = np.random.default_rng(11)
    cases = []

    def record(num_list, num_values, cat_list, cat_values, visible_list, label):
        kept = filter_all(
            data,
            num_list,
            num_values,
            cat_list,
            cat_values,
            visible_table if visible_list is not None else None,
            visible_list,
        )
        cases.append(
            {
                "label": label,
                "numeric": [
                    {"column": name, "min": float(lo), "max": float(hi)}
                    for name, (lo, hi) in zip(num_list, num_values)
                ],
                "categorical": [
                    {"column": name, "allowed": list(values)}
                    for name, values in zip(cat_list, cat_values)
                ],
                "visible": visible_list,
                # A bit per row, base64'd. The positions themselves would be
                # two megabytes across these cases, for a file that is only
                # ever compared whole; a bitmask is the same information at a
                # sixteenth the size and still exact.
                "kept_count": int(len(kept)),
                "kept_bits": pack_mask(
                    np.isin(
                        np.arange(len(data)),
                        np.flatnonzero(data.index.isin(kept.index)),
                    ),
                    len(data),
                ),
            }
        )

    record([], [], [], [], None, "no filters")

    for _ in range(25):
        chosen = list(rng.choice(numeric, size=int(rng.integers(1, 4)), replace=False))
        values = []
        for name in chosen:
            column = data[name].to_numpy(dtype=float)
            finite = column[np.isfinite(column)]
            lo, hi = (0.0, 0.0) if finite.size == 0 else (finite.min(), finite.max())
            span = hi - lo or 1.0
            start = lo + rng.uniform(0, 0.6) * span
            values.append((start, start + rng.uniform(0.05, 0.5) * span))
        record(chosen, values, [], [], None, "numeric ranges")

    for _ in range(15):
        chosen = list(
            rng.choice(categorical, size=int(rng.integers(1, 3)), replace=False)
        )
        values = []
        for name in chosen:
            levels = sorted(data[name].dropna().unique().tolist())
            size = int(rng.integers(1, len(levels) + 1))
            values.append(sorted(rng.choice(levels, size=size, replace=False).tolist()))
        record([], [], chosen, values, None, "categories")

    # The edge cases, named so a failure says which one.
    first_cat = categorical[0]
    first_num = numeric[0]
    levels = sorted(data[first_cat].dropna().unique().tolist())

    record([], [], [first_cat], [[]], None, "empty category list passes nothing")
    record([first_num], [(1e30, 1e31)], [], [], None, "range excluding everything")
    record([first_num], [(-1e31, 1e31)], [], [], None, "range including everything")
    record(
        ["NotAColumn"], [(0.0, 1.0)], [], [], None, "unknown numeric column is skipped"
    )
    record([], [], ["NotAColumn"], [levels], None, "unknown category column is skipped")
    record([], [], [], [], ["visible"], "visibility: visible only")
    record([], [], [], [], ["hidden"], "visibility: hidden only")
    record([], [], [], [], ["visible", "hidden"], "visibility: both is a no-op")
    record([], [], [], [], [], "visibility: none passes nothing")
    record(
        [first_num],
        [(float(data[first_num].min()), float(data[first_num].max()))],
        [first_cat],
        [levels[:1]],
        ["visible"],
        "all three kinds at once",
    )

    json.dump(
        {
            "table": os.path.relpath(TABLE, ROOT).replace(os.sep, "/"),
            "rows": int(len(data)),
            # Every 7th row, matching build_visible_table.
            "hidden_every": 7,
            "cases": cases,
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
