"""Cloud column mapping.

A cloud frame is a bare (N, C) array, so nothing about it says which column is
x. The manifest's ``cloud.columns`` block says, the same way ``reference.columns``
does for the pose sidecar -- and when it does not, the reader falls back through
the file's own column names to plain position, which is what every cloud written
xyz-first means.

The failure this guards is silent: get the resolution wrong and the backdrop
still draws, just with its axes swapped, somewhere off in the scene.

Author: Zhengyu Peng
License: GPL-3.0
"""

import h5py
import numpy as np
import pytest

from dataio.dense_store import CloudStore
from dataio.manifest import DEFAULT_CLOUD_COLUMNS, Manifest, normalize_cloud_columns

# Stored north-first, with a trailing column that is not a coordinate at all --
# so a mapping that is ignored shows up as swapped axes rather than as nothing.
POINTS = np.array(
    [[10.0, 20.0, 3.0, 0.9], [11.0, 21.0, 3.5, 0.4]],
    dtype=np.float32,
)


@pytest.fixture
def cloud_file(tmp_path):
    """Write a cloud whose stored order is not xyz, and name its columns."""

    def build(columns=("north", "east", "up", "intensity"), data=POINTS):
        path = tmp_path / "log.cloud.h5"
        with h5py.File(path, "w") as handle:
            if columns is not None:
                handle.attrs["columns"] = list(columns)
            handle.create_dataset("/frame_0", data=data)
        return str(path)

    return build


class TestNormalizeCloudColumns:
    def test_unnamed_fields_stay_none(self):
        assert normalize_cloud_columns(None) == DEFAULT_CLOUD_COLUMNS

    def test_named_fields_are_kept(self):
        assert normalize_cloud_columns({"x": "east", "y": "north"}) == {
            "x": "east",
            "y": "north",
            "z": None,
        }

    def test_unknown_fields_are_dropped(self):
        assert normalize_cloud_columns({"x": "east", "w": "nope"})["x"] == "east"
        assert "w" not in normalize_cloud_columns({"w": "nope"})

    def test_a_field_named_as_nothing_is_left_to_resolve(self):
        # Unlike the reference block there is no NO_COLUMN here: a point with no
        # x is not a point, so an empty value means "guess", not "no column".
        for empty in (None, "", "None"):
            assert normalize_cloud_columns({"x": empty})["x"] is None

    def test_the_legacy_list_form_is_ignored(self):
        # Older manifests carried the file's column names here as provenance.
        # That form is no longer read, and must not be mistaken for a mapping.
        assert normalize_cloud_columns(["x", "y", "z"]) == DEFAULT_CLOUD_COLUMNS
        assert normalize_cloud_columns("x,y,z") == DEFAULT_CLOUD_COLUMNS


class TestResolution:
    def test_no_mapping_reads_positionally(self, cloud_file):
        # The file names its columns, but none of them x/y/z -- so position is
        # all that is left, which is what such a file has always meant.
        store = CloudStore(cloud_file())
        assert store.xyz_indices() == (0, 1, 2)

    def test_mapping_selects_the_named_columns(self, cloud_file):
        store = CloudStore(
            cloud_file(), columns={"x": "east", "y": "north", "z": "up"}
        )
        assert store.xyz_indices() == (1, 0, 2)
        assert store.resolved_columns == {"x": "east", "y": "north", "z": "up"}

    def test_matching_is_case_insensitive(self, cloud_file):
        store = CloudStore(cloud_file(), columns={"x": "EAST"})
        assert store.xyz_indices()[0] == 1

    def test_a_field_named_for_a_missing_column_takes_what_is_left(self, cloud_file):
        # y and z are honoured; x gets the column nothing else claimed rather
        # than costing the other two their mapping.
        store = CloudStore(
            cloud_file(), columns={"x": "nope", "y": "north", "z": "up"}
        )
        assert store.xyz_indices() == (1, 0, 2)

    def test_a_partial_mapping_keeps_the_axis_it_names(self, cloud_file):
        # Resolving field by field would let the unmapped y take position 1
        # first, and x would lose the only column it actually asked for.
        store = CloudStore(cloud_file(), columns={"x": "east"})
        assert store.xyz_indices() == (1, 0, 2)

    def test_a_self_describing_file_needs_no_mapping(self, cloud_file):
        # Columns named x/y/z are honoured wherever they sit, which is the whole
        # point of the file carrying the attribute.
        store = CloudStore(cloud_file(columns=("z", "x", "y"), data=POINTS[:, :3]))
        assert store.xyz_indices() == (1, 2, 0)

    def test_a_file_naming_nothing_is_positional(self, cloud_file):
        store = CloudStore(cloud_file(columns=None, data=POINTS[:, :3]))
        assert store.xyz_indices() == (0, 1, 2)

    def test_two_fields_naming_one_column_do_not_collide(self, cloud_file):
        # A contradiction the manifest cannot mean. The earlier axis keeps the
        # column and the later one falls through, so no axis is dropped.
        indices = CloudStore(
            cloud_file(), columns={"x": "east", "y": "east"}
        ).xyz_indices()
        assert indices[0] == 1
        assert len(set(indices)) == 3

    def test_an_index_past_the_frame_width_is_not_used(self, cloud_file):
        # The attribute names four columns but the frame carries three.
        store = CloudStore(cloud_file(data=POINTS[:, :3]), columns={"x": "intensity"})
        assert store.xyz_indices(3) == (0, 1, 2)


class TestReadFrame:
    def test_columns_are_reordered_into_xyz(self, cloud_file):
        store = CloudStore(
            cloud_file(), columns={"x": "east", "y": "north", "z": "up"}
        )
        assert list(store.read_frame(0)[0][:3]) == [20.0, 10.0, 3.0]

    def test_extra_columns_survive_in_stored_order(self, cloud_file):
        store = CloudStore(
            cloud_file(), columns={"x": "east", "y": "north", "z": "up"}
        )
        frame = store.read_frame(0)
        assert frame.shape == (2, 4)
        assert frame[0][3] == pytest.approx(0.9)

    def test_an_already_ordered_frame_reads_straight_through(self, cloud_file):
        # The common case: xyz already lead the array, so the frame is returned
        # as stored rather than copied on every frame change.
        store = CloudStore(
            cloud_file(columns=("x", "y", "z", "intensity")),
            columns={"x": "x", "y": "y", "z": "z"},
        )
        assert store.xyz_indices() == (0, 1, 2)
        assert np.array_equal(store.read_frame(0), POINTS)

    def test_a_missing_frame_is_still_none(self, cloud_file):
        store = CloudStore(cloud_file(), columns={"x": "east"})
        assert store.read_frame(99) is None

    def test_a_missing_file_is_still_none(self, tmp_path):
        store = CloudStore(str(tmp_path / "absent.cloud.h5"))
        assert store.read_frame(0) is None
        assert store.available_columns() == ["x", "y", "z"]


class TestManifestAccessor:
    def test_reads_the_declared_mapping(self, make_case):
        case_dir = make_case(
            {
                "manifest_version": 2,
                "table": {"slider": "Frame"},
                "cloud": {"columns": {"x": "east", "y": "north", "z": "up"}},
            }
        )
        assert Manifest.load(case_dir).cloud_columns() == {
            "x": "east",
            "y": "north",
            "z": "up",
        }

    def test_a_cloud_block_without_columns_resolves_on_its_own(self, make_case):
        case_dir = make_case(
            {
                "manifest_version": 2,
                "table": {"slider": "Frame"},
                "cloud": {"suffix": ".cloud.h5"},
            }
        )
        assert Manifest.load(case_dir).cloud_columns() == DEFAULT_CLOUD_COLUMNS

    def test_no_cloud_block_at_all(self, make_case):
        case_dir = make_case({"manifest_version": 2, "table": {"slider": "Frame"}})
        assert Manifest.load(case_dir).cloud_columns() == DEFAULT_CLOUD_COLUMNS
