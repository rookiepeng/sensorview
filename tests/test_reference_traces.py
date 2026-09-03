"""Where the reference overlay comes from, and where it ends up.

There is exactly one source of a reference position now: the log's
`.reference.parquet` sidecar. The table columns that used to supply one --
`x_ref` / `y_ref` / `z_ref` -- are gone, and with them the case of two sources
describing the same thing.

That leaves one decision, made in :func:`prepare_figure_kwargs` because it is
the only place that sees all of what the manifest declared, whether a sidecar
exists, and whether it produced any poses:

- poses -> the sidecar places it, per frame;
- a declared reference and no sidecar anywhere -> drawn unplaced at the origin,
  because a declared reference that never appears reads as the block having
  been ignored;
- a sidecar that pairs with nothing -> hidden. Its frame column is what pairs
  its rows with the table's, and unset (the picker reading None) is the mapping
  being unset, not the dataset failing to say where the reference goes. Parking
  it at the origin would look placed.

Author: Zhengyu Peng
License: GPL-3.0
"""

import numpy as np
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

MESH_BLOCK = {
    "shape": "mesh",
    "color": "#4c9ffe",
    "opacity": 0.3,
    "vertices": list(PYRAMID_VERTICES),
    "faces": list(PYRAMID_FACES),
    "edges": [[0, 1], [1, 2], [2, 3], [3, 0]],
    "edge_color": "#7fc4ff",
}
MARKER_BLOCK = {"shape": "marker", "color": "#ffffff"}

LEVEL_POSE = {"x": 5.0, "y": -5.0, "z": 0.5, "yaw": 0.0, "pitch": 0.0, "roll": 0.0}


@pytest.fixture
def mesh():
    return normalize_reference_display(MESH_BLOCK)


@pytest.fixture
def marker():
    return normalize_reference_display(MARKER_BLOCK)


def apex_of(trace):
    """Where the pyramid's apex ended up: the placement plus (0, 0, 2)."""
    return (trace["x"][APEX], trace["y"][APEX], trace["z"][APEX])


class TestDrawing:
    """:func:`get_reference_traces` places what it is given and nothing more --
    whether a reference belongs on the figure at all is settled before it is
    called."""

    def test_a_pose_places_it(self, mesh):
        traces = get_reference_traces(display=mesh, pose=LEVEL_POSE, name="Ego")

        assert apex_of(traces[0]) == (5.0, -5.0, 2.5)
        assert traces[0]["name"] == "Ego"

    def test_the_dot_follows_the_pose_too(self, marker):
        traces = get_reference_traces(display=marker, pose=LEVEL_POSE)

        assert (traces[0]["x"], traces[0]["y"], traces[0]["z"]) == (
            [5.0],
            [-5.0],
            [0.5],
        )

    def test_no_pose_puts_the_mesh_at_the_origin(self, mesh):
        traces = get_reference_traces(display=mesh)

        assert apex_of(traces[0]) == (0.0, 0.0, 2.0)
        assert DEFAULT_REFERENCE_ORIGIN == (0.0, 0.0, 0.0)

    def test_no_pose_puts_the_dot_at_the_origin(self, marker):
        traces = get_reference_traces(display=marker)

        assert (traces[0]["x"], traces[0]["y"], traces[0]["z"]) == ([0.0], [0.0], [0.0])

    def test_the_wireframe_comes_along(self, mesh):
        traces = get_reference_traces(display=mesh, pose=LEVEL_POSE)

        assert [trace["type"] for trace in traces] == ["mesh3d", "scatter3d"]
        assert traces[1]["mode"] == "lines"

    def test_the_mesh_turns_with_the_pose(self, mesh):
        # A quarter turn about z sends the +x corner to +y.
        pose = {**LEVEL_POSE, "x": 0.0, "y": 0.0, "z": 0.0, "yaw": np.pi / 2}

        traces = get_reference_traces(display=mesh, pose=pose)

        assert traces[0]["x"][1] == pytest.approx(1.0)
        assert traces[0]["y"][1] == pytest.approx(1.0)
        assert apex_of(traces[0])[2] == pytest.approx(2.0)

    def test_a_geometryless_mesh_falls_back_to_the_dot(self):
        # The normalizer downgrades it, so what reaches the renderer is a
        # marker: a dot in the right place beats an invisible trace.
        display = normalize_reference_display({**MESH_BLOCK, "faces": []})

        traces = get_reference_traces(display=display, pose=LEVEL_POSE)

        assert [trace["type"] for trace in traces] == ["scatter3d"]


class TestReferenceSource:
    KEYS = {
        "X": {"description": "X", "type": "numerical"},
        "Y": {"description": "Y", "type": "numerical"},
        "Z": {"description": "Z", "type": "numerical"},
        "Frame": {"description": "Frame", "type": "numerical"},
    }
    # Every axis sits well clear of the origin, so an unplaced reference is
    # outside the data's own extent.
    VALUES = [(100.0, 200.0), (100.0, 200.0), (10.0, 20.0), (0.0, 1.0)]
    BOUNDS = {"x": (300.0, 400.0), "y": (300.0, 400.0), "z": (0.0, 0.0)}

    def kwargs(self, reference=None, ref_bounds=None, has_sidecar=False):
        config = {
            "keys": self.KEYS,
            "slider": "Frame",
            "x_3d": "X",
            "y_3d": "Y",
            "z_3d": "Z",
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
            ref_bounds=ref_bounds,
            has_sidecar=has_sidecar,
        )

    def test_poses_mean_the_sidecar_places_it(self):
        fig_kwargs = self.kwargs(MESH_BLOCK, ref_bounds=self.BOUNDS, has_sidecar=True)

        assert fig_kwargs["ref_source"] == "sidecar"

    def test_a_declared_reference_with_no_sidecar_is_drawn_unplaced(self):
        assert self.kwargs(MESH_BLOCK)["ref_source"] == "origin"
        assert self.kwargs(MARKER_BLOCK)["ref_source"] == "origin"

    def test_a_dataset_that_declared_none_draws_nothing(self):
        assert self.kwargs()["ref_source"] is None

    def test_a_sidecar_that_pairs_with_nothing_is_hidden(self):
        # The frame picker reading None: the file is there, but no row of it
        # belongs to any frame. Hidden, not parked at the origin.
        fig_kwargs = self.kwargs(MESH_BLOCK, ref_bounds=None, has_sidecar=True)

        assert fig_kwargs["ref_source"] is None

    def test_hiding_it_leaves_the_axis_ranges_alone(self):
        fig_kwargs = self.kwargs(MESH_BLOCK, ref_bounds=None, has_sidecar=True)

        assert fig_kwargs["x_range"] == [100.0, 200.0]
        assert fig_kwargs["z_range"] == [10.0, 20.0]


class TestAxisRanges:
    """The 3D scene fixes its axis ranges, so anything drawn outside the data's
    own extent is clipped away unless the ranges are widened for it."""

    def ranges(self, **kwargs):
        fig_kwargs = TestReferenceSource().kwargs(**kwargs)
        return [fig_kwargs[key] for key in ("x_range", "y_range", "z_range")]

    def test_an_unplaced_mesh_is_inside_them(self):
        ranges = self.ranges(reference=MESH_BLOCK)

        for axis, (low, high) in enumerate(ranges):
            assert low <= min(vertex[axis] for vertex in PYRAMID_VERTICES)
            assert high >= max(vertex[axis] for vertex in PYRAMID_VERTICES)

    def test_an_unplaced_dot_is_inside_them(self):
        for low, high in self.ranges(reference=MARKER_BLOCK):
            assert low <= 0.0 <= high

    def test_a_sidecar_s_whole_path_is_inside_them(self):
        ranges = self.ranges(
            reference=MESH_BLOCK,
            ref_bounds=TestReferenceSource.BOUNDS,
            has_sidecar=True,
        )

        # Plus room for the mesh at the far end of it, whatever way it turns.
        assert ranges[0][1] >= 400.0
        assert ranges[0][0] <= 100.0

    def test_a_dataset_with_no_reference_keeps_its_ranges(self):
        assert self.ranges() == [[100.0, 200.0], [100.0, 200.0], [10.0, 20.0]]
