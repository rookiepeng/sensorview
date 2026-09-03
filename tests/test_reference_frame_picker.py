"""Picking the sidecar's frame column.

A reference sidecar is a separate file, paired with the table one row at a time
on a frame id. Which column carries that id is the exporter's choice, and the
name-guessing fallback (`frame`, `frame_id`, `frame_idx`, the table's own slider
column) covers the common spellings and nothing else. A file calling it `t` or
`sample_token` pairs with nothing, every lookup misses, and the reference simply
never appears -- with no control anywhere to say otherwise.

So the frame column is picked in the 3D view like the six pose fields, and
persisted to `info.json` the same way. These tests pin the parts that break
quietly: the picker order the option and value lists are indexed against, the
callback that has to read the new input to write it, and the store cache, which
would otherwise answer a re-pointed frame column out of the old mapping's poses.

Author: Zhengyu Peng
License: GPL-3.0
"""

import json
import os

import dash
import polars as pl
import pytest

from app_config import (
    DROPDOWN_OPTIONS_3D_XYZ_REF,
    DROPDOWN_VALUES_3D_XYZ_REF,
    REFERENCE_PICKER_ORDER,
)
from dataio.manifest import DEFAULT_REFERENCE_COLUMNS, NO_COLUMN, Manifest
from dataio.reference import ReferenceStore
from layouts.canvas_layout import get_canvas_layout
from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks

PICKER_ID = "frame-ref-picker-3d"

# A sidecar naming nothing the fallback chain looks for: the frame column is
# `sample_idx`, and x/y are self-describing so only the pairing is in question.
SIDECAR = {
    "sample_idx": [10, 11, 12],
    "x": [1.0, 2.0, 3.0],
    "y": [-1.0, -2.0, -3.0],
}


def component_ids(layout):
    """Every id in a component tree, whatever it is nested inside."""
    found = []

    def walk(node):
        component_id = getattr(node, "id", None)
        if isinstance(component_id, str):
            found.append(component_id)
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            for child in children:
                walk(child)
        elif children is not None:
            walk(children)

    walk(layout)
    return found


@pytest.fixture
def case(tmp_path):
    """A case whose log has a sidecar with an unguessable frame column."""
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "info.json").write_text(
        json.dumps(
            {
                "version": 2,
                "table": {"slider": "Frame", "keys": {}},
                "reference": {"shape": "marker"},
            }
        ),
        encoding="utf-8",
    )
    pl.DataFrame(SIDECAR).write_parquet(case_dir / "log.reference.parquet")
    return str(case_dir)


class TestPickerOrder:
    """The option and value lists are indexed positionally against the picker
    order, so a field added to one and not the others silently shifts every
    mapping past it."""

    def test_the_three_lists_are_the_same_length(self):
        assert len(DROPDOWN_OPTIONS_3D_XYZ_REF) == len(REFERENCE_PICKER_ORDER)
        assert len(DROPDOWN_VALUES_3D_XYZ_REF) == len(REFERENCE_PICKER_ORDER)

    @pytest.mark.parametrize(
        "outputs", [DROPDOWN_OPTIONS_3D_XYZ_REF, DROPDOWN_VALUES_3D_XYZ_REF]
    )
    def test_each_output_is_its_field_s_picker(self, outputs):
        ids = [output.component_id for output in outputs]

        assert ids == [f"{field}-ref-picker-3d" for field in REFERENCE_PICKER_ORDER]

    def test_frame_is_a_field_the_manifest_can_hold(self):
        # The picker writes into `reference.columns`, which ignores keys it does
        # not know -- a field it never heard of would be dropped on save.
        assert set(REFERENCE_PICKER_ORDER) <= set(DEFAULT_REFERENCE_COLUMNS)


class TestWiring:
    def test_the_picker_is_in_the_layout(self):
        assert PICKER_ID in component_ids(get_canvas_layout())

    def test_the_3d_view_reads_it(self):
        app = dash.Dash(__name__)
        get_scatter_3d_view_callbacks(app)

        reads = {
            dep["id"]
            for callback in app.callback_map.values()
            for dep in callback["inputs"]
        }

        assert PICKER_ID in reads


class TestMappingTheFrameColumn:
    def test_an_unguessable_frame_column_leaves_the_sidecar_empty(self, case):
        manifest = Manifest.load(case)

        store = ReferenceStore.open(
            manifest.reference_path("log"),
            manifest.reference_columns(),
            frame_key=manifest.frame_key,
        )

        # Nothing to pair the rows with, so no frame has a pose -- which is the
        # state the picker exists to get the user out of.
        assert store.pose(10) is None
        # It still offers its columns, or there would be nothing to pick from.
        assert "sample_idx" in store.available_columns

    def test_mapping_it_pairs_the_rows(self, case):
        manifest = Manifest.load(case)
        manifest.update_reference_columns({"frame": "sample_idx"})

        store = ReferenceStore.open(
            manifest.reference_path("log"),
            manifest.reference_columns(),
            frame_key=manifest.frame_key,
        )

        assert store.pose(10)["x"] == 1.0
        assert store.pose(12)["y"] == -3.0

    def test_the_choice_reaches_info_json(self, case):
        manifest = Manifest.load(case)
        manifest.update_reference_columns({"frame": "sample_idx"})
        manifest.save()

        written = json.loads(
            open(os.path.join(case, "info.json"), encoding="utf-8").read()
        )

        assert written["reference"]["columns"]["frame"] == "sample_idx"
        # Saving the mapping must not cost the block its styling.
        assert written["reference"]["shape"] == "marker"

    def test_it_survives_a_reload(self, case):
        manifest = Manifest.load(case)
        manifest.update_reference_columns({"frame": "sample_idx"})
        manifest.save()

        assert Manifest.load(case).reference_columns()["frame"] == "sample_idx"


class TestClearingIt:
    """The picker's empty dropdown is the reference's off switch, so it has to
    outrank the name guessing -- otherwise picking None on a file that does
    have a `frame` column silently resolves straight back to it, and the
    control does nothing at all."""

    @pytest.fixture
    def plain(self, tmp_path):
        """A sidecar the guesses would resolve on their own."""
        path = tmp_path / "log.reference.parquet"
        pl.DataFrame({"frame": [0, 1], "x": [1.0, 2.0], "y": [3.0, 4.0]}).write_parquet(
            path
        )
        return str(path)

    def test_the_guess_pairs_an_unmapped_file(self, plain):
        store = ReferenceStore.open(plain, dict(DEFAULT_REFERENCE_COLUMNS), "Frame")

        assert store.resolved_columns["frame"] == "frame"
        assert store.pose(0) is not None

    def test_clearing_the_frame_column_unpairs_it(self, plain):
        columns = {**DEFAULT_REFERENCE_COLUMNS, "frame": NO_COLUMN}

        store = ReferenceStore.open(plain, columns, "Frame")

        assert store.resolved_columns["frame"] is None
        assert store.pose(0) is None
        # No poses means no extent, which is what tells the figure to hide it.
        assert store.bounds() is None

    def test_the_pickers_own_spelling_of_empty_clears_it(self, case):
        # Straight from the dropdown, through the manifest, to the store.
        manifest = Manifest.load(case)
        manifest.update_reference_columns({"frame": "None"})
        manifest.save()

        reloaded = Manifest.load(case)
        store = ReferenceStore.open(
            reloaded.reference_path("log"),
            reloaded.reference_columns(),
            frame_key=reloaded.frame_key,
        )

        assert store.resolved_columns["frame"] is None

    def test_clearing_a_pose_field_sticks_too(self, plain):
        columns = {**DEFAULT_REFERENCE_COLUMNS, "y": NO_COLUMN}

        store = ReferenceStore.open(plain, columns, "Frame")

        assert store.resolved_columns["y"] is None
        # x and y are what place it, so cleared it places nothing.
        assert not store.is_usable


class TestStoreCache:
    """The store is cached per (file, mapping). The frame column is part of the
    mapping: re-pointing it re-keys every pose in the file, so answering the new
    mapping out of the old store would leave the picker looking inert."""

    def test_repointing_the_frame_column_is_not_answered_from_the_cache(self, case):
        path = Manifest.load(case).reference_path("log")
        columns = dict(DEFAULT_REFERENCE_COLUMNS)

        before = ReferenceStore.open(path, columns, frame_key="Frame")
        after = ReferenceStore.open(
            path, {**columns, "frame": "sample_idx"}, frame_key="Frame"
        )

        assert before is not after
        assert before.pose(10) is None
        assert after.pose(10) is not None

    def test_an_unchanged_mapping_still_reuses_the_parsed_file(self, case):
        path = Manifest.load(case).reference_path("log")
        columns = {**DEFAULT_REFERENCE_COLUMNS, "frame": "sample_idx"}

        first = ReferenceStore.open(path, columns, frame_key="Frame")
        second = ReferenceStore.open(path, dict(columns), frame_key="Frame")

        assert first is second
