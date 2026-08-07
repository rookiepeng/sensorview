"""Reference overlay normalization.

The reference block is cosmetic, and the module treats it that way throughout: a
typo in a colour or an unknown shape costs the user a style, never the reference
point itself. Every degradation path here ends in a drawable marker rather than
an exception or an invisible trace, which is exactly the kind of behaviour that
looks removable until something stops rendering.

Author: Zhengyu Peng
License: GPL-3.0
"""

import json
import os

import pytest

from dataio.manifest import (
    DEFAULT_REFERENCE_COLUMNS,
    DEFAULT_REFERENCE_DISPLAY,
    _mesh_edges,
    _mesh_extent,
    _mesh_radius,
    _vec3,
    normalize_reference_columns,
    normalize_reference_display,
)

# A unit tetrahedron: the smallest thing with enough faces to be a real mesh.
TETRA_VERTICES = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
TETRA_FACES = [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]]


@pytest.fixture
def mesh_block():
    return {
        "shape": "mesh",
        "vertices": list(TETRA_VERTICES),
        "faces": list(TETRA_FACES),
    }


class TestVec3:
    def test_accepts_a_list(self):
        assert _vec3([1, 2, 3], [0.0, 0.0, 0.0]) == [1.0, 2.0, 3.0]

    def test_accepts_a_mapping(self):
        # Both forms read naturally in a hand-written manifest.
        assert _vec3({"x": 1, "y": 2, "z": 3}, [0.0, 0.0, 0.0]) == [1.0, 2.0, 3.0]

    @pytest.mark.parametrize(
        "value",
        [None, [1, 2], [1, 2, 3, 4], "xyz", {"x": 1, "y": 2}, [1, "two", 3]],
    )
    def test_unusable_input_falls_back(self, value):
        assert _vec3(value, [9.0, 9.0, 9.0]) == [9.0, 9.0, 9.0]

    def test_fallback_is_copied_not_aliased(self):
        fallback = [0.0, 0.0, 0.0]
        result = _vec3(None, fallback)
        result[0] = 5.0
        assert fallback == [0.0, 0.0, 0.0]


class TestMeshGeometryHelpers:
    def test_extent_is_per_axis_min_max(self):
        assert _mesh_extent(TETRA_VERTICES) == [[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]]

    def test_extent_of_an_empty_mesh_is_a_point(self):
        assert _mesh_extent([]) == [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]

    def test_radius_is_the_furthest_vertex_norm(self):
        assert _mesh_radius([[3.0, 4.0, 0.0], [1.0, 0.0, 0.0]]) == 5.0

    def test_radius_of_an_empty_mesh_is_zero(self):
        assert _mesh_radius([]) == 0.0

    def test_radius_exceeds_extent_on_a_diagonal(self):
        # Why radius exists at all: a mesh that turns with a pose reaches
        # further than its own per-axis extent.
        vertices = [[1.0, 1.0, 0.0]]
        assert _mesh_radius(vertices) > _mesh_extent(vertices)[0][1]


class TestMeshEdges:
    def test_true_derives_a_wireframe_from_faces(self):
        edges = _mesh_edges(True, TETRA_FACES, len(TETRA_VERTICES))
        # A tetrahedron has six unique edges however many triangles share them.
        assert len(edges) == 6
        assert {frozenset(edge) for edge in edges} == {
            frozenset(pair) for pair in [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        }

    def test_shared_edges_are_not_duplicated(self):
        # Two triangles sharing edge 0-1 must yield that edge once.
        edges = _mesh_edges(True, [[0, 1, 2], [1, 0, 3]], 4)
        assert len([e for e in edges if frozenset(e) == frozenset((0, 1))]) == 1

    @pytest.mark.parametrize("raw", [False, None, 0, []])
    def test_falsy_draws_no_edges(self, raw):
        assert _mesh_edges(raw, TETRA_FACES, 4) == []

    def test_explicit_pairs_are_used_verbatim(self):
        assert _mesh_edges([[0, 1], [2, 3]], TETRA_FACES, 4) == [[0, 1], [2, 3]]

    def test_out_of_range_pairs_are_dropped(self):
        assert _mesh_edges([[0, 1], [0, 99]], TETRA_FACES, 4) == [[0, 1]]

    def test_malformed_pairs_are_dropped(self):
        assert _mesh_edges([[0, 1], [0], "xy", [0, "b"]], TETRA_FACES, 4) == [[0, 1]]


class TestNormalizeReferenceDisplayMarker:
    def test_absent_block_yields_the_documented_default(self):
        display = normalize_reference_display(None)
        assert display["shape"] == "marker"
        assert display["color"] == DEFAULT_REFERENCE_DISPLAY["color"]
        assert display["size"] == DEFAULT_REFERENCE_DISPLAY["size"]

    def test_overrides_are_applied(self):
        display = normalize_reference_display({"color": "#ff0000", "size": 12})
        assert display["color"] == "#ff0000"
        assert display["size"] == 12

    def test_unknown_shape_degrades_to_marker(self):
        # A typo in a cosmetic field must not cost the reference point.
        assert normalize_reference_display({"shape": "hexagon"})["shape"] == "marker"

    def test_shape_is_case_insensitive(self):
        assert (
            normalize_reference_display(
                {"shape": "MESH", "vertices": TETRA_VERTICES, "faces": TETRA_FACES}
            )["shape"]
            == "mesh"
        )

    def test_source_keys_are_not_display_keys(self):
        # suffix/columns say where the data comes from, not how it is drawn.
        display = normalize_reference_display(
            {"suffix": ".pose.parquet", "columns": {"x": "east"}}
        )
        assert "suffix" not in display
        assert "columns" not in display


class TestNormalizeReferenceDisplayMesh:
    def test_valid_mesh_is_normalized(self, mesh_block):
        display = normalize_reference_display(mesh_block)
        assert display["shape"] == "mesh"
        assert display["vertices"] == TETRA_VERTICES
        assert display["faces"] == TETRA_FACES

    def test_mesh_gains_extent_and_radius(self, mesh_block):
        display = normalize_reference_display(mesh_block)
        assert display["extent"] == [[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]]
        assert display["radius"] == pytest.approx(1.0)

    def test_mesh_defaults_are_translucent(self, mesh_block):
        # A solid body at full opacity would bury every detection inside it.
        assert normalize_reference_display(mesh_block)["opacity"] == 0.35

    def test_edges_default_to_the_derived_wireframe(self, mesh_block):
        assert len(normalize_reference_display(mesh_block)["edges"]) == 6

    def test_edge_color_follows_color_when_unset(self, mesh_block):
        display = normalize_reference_display({**mesh_block, "color": "#123456"})
        assert display["edge_color"] == "#123456"

    def test_explicit_edge_color_wins(self, mesh_block):
        display = normalize_reference_display(
            {**mesh_block, "color": "#123456", "edge_color": "#abcdef"}
        )
        assert display["edge_color"] == "#abcdef"

    def test_mesh_without_faces_degrades_to_marker(self, mesh_block):
        # Vertices enclose nothing without triangles, and a mesh trace with no
        # triangles is an invisible reference.
        display = normalize_reference_display({**mesh_block, "faces": []})
        assert display["shape"] == "marker"

    def test_mesh_without_vertices_degrades_to_marker(self, mesh_block):
        # Every face indexes past an empty vertex list, so none survive.
        display = normalize_reference_display({**mesh_block, "vertices": []})
        assert display["shape"] == "marker"

    def test_faces_pointing_past_the_vertices_are_dropped(self):
        display = normalize_reference_display(
            {
                "shape": "mesh",
                "vertices": TETRA_VERTICES,
                "faces": [[0, 1, 2], [0, 1, 99]],
            }
        )
        # Plotly renders an out-of-range index as a hole, which is harder to
        # diagnose than a missing face.
        assert display["faces"] == [[0, 1, 2]]

    def test_malformed_vertices_are_dropped(self):
        display = normalize_reference_display(
            {
                "shape": "mesh",
                # The bad entry sits last, so dropping it renumbers nothing the
                # face below refers to.
                "vertices": TETRA_VERTICES + [[1.0, 2.0]],
                "faces": [[0, 1, 2]],
            }
        )
        assert display["vertices"] == TETRA_VERTICES

    def test_dropping_a_vertex_renumbers_and_can_invalidate_a_face(self):
        # The subtle one. Vertices are dropped by position, so a malformed entry
        # early in the list shifts every index after it. Here that leaves the
        # only face pointing past the end, it is discarded as out of range, and
        # a mesh with no faces degrades to a marker -- rather than rendering
        # silently mis-indexed geometry.
        display = normalize_reference_display(
            {
                "shape": "mesh",
                # Four authored entries, one unusable. The face names entries
                # 0, 2 and 3 as the author counted them; after the drop only
                # three vertices remain, so index 3 no longer exists.
                "vertices": [[0.0, 0.0, 0.0], "nope", [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                "faces": [[0, 2, 3]],
            }
        )
        assert display["shape"] == "marker"

    def test_degrading_to_marker_keeps_the_other_overrides(self, mesh_block):
        display = normalize_reference_display(
            {**mesh_block, "faces": [], "color": "#ff0000", "name": "Ego"}
        )
        assert display["shape"] == "marker"
        assert display["color"] == "#ff0000"
        assert display["name"] == "Ego"

    def test_marker_result_carries_no_mesh_keys(self, mesh_block):
        display = normalize_reference_display({**mesh_block, "faces": []})
        assert "extent" not in display
        assert "radius" not in display


class TestNormalizeReferenceColumns:
    def test_absent_block_leaves_every_field_unmapped(self):
        assert normalize_reference_columns(None) == DEFAULT_REFERENCE_COLUMNS

    def test_mapped_fields_are_kept(self):
        columns = normalize_reference_columns({"x": "east", "yaw": "heading"})
        assert columns["x"] == "east"
        assert columns["yaw"] == "heading"

    @pytest.mark.parametrize("unset", [None, "", "None"])
    def test_the_three_unset_spellings_all_become_none(self, unset):
        # "None" is what the view's pickers emit for an empty dropdown; all
        # three must be one thing downstream rather than three.
        assert normalize_reference_columns({"x": unset})["x"] is None

    def test_unknown_fields_are_ignored(self):
        columns = normalize_reference_columns({"not_a_field": "x"})
        assert "not_a_field" not in columns

    def test_values_are_coerced_to_str(self):
        assert normalize_reference_columns({"x": 3})["x"] == "3"

    def test_every_field_is_always_present(self):
        columns = normalize_reference_columns({"x": "east"})
        assert set(columns) == set(DEFAULT_REFERENCE_COLUMNS)


class TestShippedExampleReference:
    """The bundled dataset declares a mesh; it has to normalize to one."""

    def test_bundled_nuscenes_mesh_survives_normalization(self):
        case_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "NuScenes",
        )
        with open(os.path.join(case_dir, "info.json"), encoding="utf-8") as handle:
            raw = json.load(handle)

        display = normalize_reference_display(raw["reference"])
        # Degrading to a marker here would mean the shipped geometry is broken.
        assert display["shape"] == "mesh"
        assert display["faces"]
        assert display["radius"] > 0
