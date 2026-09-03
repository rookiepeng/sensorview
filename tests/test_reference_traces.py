"""Placing the reference overlay.

The reference has three possible sources of position -- a pose sidecar, the
table's ref columns, or nothing at all -- and what the last one means depends
on whether ``info.json`` declared a `reference` block. It did: the dataset says
it has a reference, so it is drawn at the origin, as its mesh or as the plain
dot. It did not: nothing is drawn, or every dataset in the world would grow a
white dot it never asked for.

The other distinction these tests pin is between "nothing can place this
reference" and "nothing places it *right now*": a frame whose rows were all
filtered away, or a sidecar with no row for it, must not send the reference to
the origin mid-playback.

Author: Zhengyu Peng
License: GPL-3.0
"""

import numpy as np
import pandas as pd
import pytest

from dataio.manifest import normalize_reference_display
from utils import prepare_figure_kwargs
from viz.graph_data import DEFAULT_REFERENCE_ORIGIN, get_reference_traces

# A square pyramid: a mesh with an unmistakable apex, so a misplaced or
# misrotated body is visible in the numbers rather than only on screen.
PYRAMID_VERTICES = [
    [-1.0, -1.0, 0.0],
    [1.0, -1.0, 0.0],
    [1.0, 1.0, 0.0],
    [-1.0, 1.0, 0.0],
    [0.0, 0.0, 2.0],
]
PYRAMID_FACES = [[0, 1, 2], [0, 2, 3], [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]]
APEX = 4


# Both fixtures go through the normalizer rather than being written out by
# hand: `declared` is its reading of the block, and a display dict assembled
# any other way would not carry the flag the renderer keys on.
@pytest.fixture
def mesh():
    return normalize_reference_display(
        {
            "shape": "mesh",
            "color": "#4c9ffe",
            "opacity": 0.3,
            "vertices": list(PYRAMID_VERTICES),
            "faces": list(PYRAMID_FACES),
            "edges": [[0, 1], [1, 2], [2, 3], [3, 0]],
            "edge_color": "#7fc4ff",
        }
    )


@pytest.fixture
def marker():
    return normalize_reference_display({"shape": "marker", "color": "#ffffff"})


@pytest.fixture
def undeclared():
    """What a dataset with no ``reference`` block at all normalizes to."""
    return normalize_reference_display(None)


@pytest.fixture
def frame():
    """One frame carrying ref columns, the way the table path supplies them."""
    return pd.DataFrame(
        {"ref_x": [10.0, 10.0], "ref_y": [20.0, 20.0], "ref_z": [1.0, 1.0]}
    )


def apex_of(trace):
    """Where the pyramid's apex ended up, which is the placement plus (0, 0, 2)."""
    return (trace["x"][APEX], trace["y"][APEX], trace["z"][APEX])


class TestNothingPlacesTheReference:
    """No pose sidecar and no ref columns -- the manifest is all there is."""

    def test_mesh_is_drawn_at_the_origin(self, mesh):
        traces = get_reference_traces(pd.DataFrame(), display=mesh, name="Ego")

        assert traces, "a declared mesh with nowhere to be still describes the dataset"
        assert apex_of(traces[0]) == (0.0, 0.0, 2.0)
        assert DEFAULT_REFERENCE_ORIGIN == (0.0, 0.0, 0.0)
        assert traces[0]["name"] == "Ego"

    def test_wireframe_comes_along(self, mesh):
        traces = get_reference_traces(pd.DataFrame(), display=mesh)

        assert len(traces) == 2
        assert traces[1]["mode"] == "lines"

    def test_the_dot_is_drawn_at_the_origin_too(self, marker):
        # The same reasoning as the mesh: the dataset declared a reference, so
        # the missing sidecar shows up as a reference at (0, 0, 0) rather than
        # as nothing at all.
        traces = get_reference_traces(pd.DataFrame(), display=marker)

        assert len(traces) == 1
        assert (traces[0]["x"], traces[0]["y"], traces[0]["z"]) == ([0.0], [0.0], [0.0])
        assert traces[0]["mode"] == "markers"

    def test_a_dataset_with_no_reference_block_draws_nothing(self, undeclared):
        # Otherwise every dataset that never mentioned a reference would grow a
        # white dot at the origin.
        assert get_reference_traces(pd.DataFrame(), display=undeclared) == []

    def test_no_display_at_all_draws_nothing(self):
        assert get_reference_traces(pd.DataFrame(), display=None) == []


class TestRefColumnsPlaceIt:
    def test_mesh_follows_the_columns(self, frame, mesh):
        traces = get_reference_traces(
            frame, x_key="ref_x", y_key="ref_y", z_key="ref_z", display=mesh
        )

        assert apex_of(traces[0]) == (10.0, 20.0, 3.0)

    def test_marker_follows_the_columns(self, frame, marker):
        traces = get_reference_traces(
            frame, x_key="ref_x", y_key="ref_y", z_key="ref_z", display=marker
        )

        placed = (traces[0]["x"], traces[0]["y"], traces[0]["z"])
        assert placed == ([10.0], [20.0], [1.0])

    def test_filtering_every_row_away_does_not_move_it_to_the_origin(self, frame, mesh):
        # The position lives in the rows, so an empty frame says nothing about
        # where the body is -- parking it at the origin because of a filter
        # would be a lie, and one that jumps around during playback.
        traces = get_reference_traces(
            frame.iloc[0:0], x_key="ref_x", y_key="ref_y", z_key="ref_z", display=mesh
        )

        assert traces == []

    def test_the_dot_does_not_jump_to_the_origin_when_filtered_out_either(
        self, frame, marker
    ):
        traces = get_reference_traces(
            frame.iloc[0:0], x_key="ref_x", y_key="ref_y", z_key="ref_z", display=marker
        )

        assert traces == []

    def test_a_column_the_table_does_not_have_is_not_an_error(self, frame, mesh):
        # A config left over from another dataset names columns this table never
        # had; the reference goes missing, the figure still renders.
        traces = get_reference_traces(
            frame, x_key="gone_x", y_key="gone_y", display=mesh
        )

        assert traces == []


class TestPoseWins:
    def test_mesh_is_placed_by_the_pose(self, frame, mesh):
        pose = {"x": 5.0, "y": -5.0, "z": 0.5, "yaw": 0.0, "pitch": 0.0, "roll": 0.0}

        traces = get_reference_traces(
            frame, x_key="ref_x", y_key="ref_y", z_key="ref_z", display=mesh, pose=pose
        )

        assert apex_of(traces[0]) == (5.0, -5.0, 2.5)

    def test_mesh_turns_with_the_pose(self, mesh):
        # A quarter turn about z sends the +x corner to +y.
        pose = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "yaw": np.pi / 2,
            "pitch": 0.0,
            "roll": 0.0,
        }

        traces = get_reference_traces(pd.DataFrame(), display=mesh, pose=pose)

        assert traces[0]["x"][1] == pytest.approx(1.0)
        assert traces[0]["y"][1] == pytest.approx(1.0)
        assert apex_of(traces[0])[2] == pytest.approx(2.0)


class TestAxisRangesReachTheOrigin:
    """The 3D scene fixes its axis ranges, so an unplaced reference at (0, 0, 0)
    is clipped away unless the ranges are widened to reach it. Data that never
    goes near the origin -- a log in map coordinates, say -- is exactly the case
    that would otherwise draw the reference into nowhere."""

    KEYS = {
        "X": {"description": "X", "type": "numerical"},
        "Y": {"description": "Y", "type": "numerical"},
        "Z": {"description": "Z", "type": "numerical"},
        "Frame": {"description": "Frame", "type": "numerical"},
    }
    # Every axis sits well clear of the origin.
    VALUES = [(100.0, 200.0), (100.0, 200.0), (10.0, 20.0), (0.0, 1.0)]

    def kwargs(self, reference):
        config = {
            "keys": self.KEYS,
            "slider": "Frame",
            "x_3d": "X",
            "y_3d": "Y",
            "z_3d": "Z",
            "x_ref": "None",
            "y_ref": "None",
            "z_ref": "None",
        }
        if reference is not None:
            config["reference"] = reference

        return prepare_figure_kwargs(
            config,
            ["X", "Y", "Z", "Frame"],
            self.VALUES,
            "Frame",
            False,
            [0, 1, 2],
            0,
        )

    def test_an_unplaced_dot_is_inside_the_ranges(self):
        fig_kwargs = self.kwargs({"shape": "marker"})

        for range_key in ("x_range", "y_range", "z_range"):
            low, high = fig_kwargs[range_key]
            assert low <= 0.0 <= high, range_key

    def test_an_unplaced_mesh_is_inside_the_ranges(self):
        fig_kwargs = self.kwargs(
            {
                "shape": "mesh",
                "vertices": list(PYRAMID_VERTICES),
                "faces": list(PYRAMID_FACES),
            }
        )

        for axis, range_key in enumerate(("x_range", "y_range", "z_range")):
            low, high = fig_kwargs[range_key]
            assert low <= min(v[axis] for v in PYRAMID_VERTICES)
            assert high >= max(v[axis] for v in PYRAMID_VERTICES)

    def test_a_dataset_with_no_reference_keeps_its_ranges(self):
        fig_kwargs = self.kwargs(None)

        assert fig_kwargs["x_range"] == [100.0, 200.0]
        assert fig_kwargs["z_range"] == [10.0, 20.0]
