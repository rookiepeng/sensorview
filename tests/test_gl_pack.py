"""The packed frame format round-trips.

`viz.gl_pack` writes a container the browser reads as typed-array *views*, not
copies -- which only works while every section stays four-byte aligned, because
`new Float32Array(buffer, offset, n)` throws on a misaligned offset rather than
falling back to copying. Nothing in the app would report that; the scene would
simply not draw. So alignment is asserted here, along with the facts the
renderer reads straight out of the header.

Author: Zhengyu Peng
License: GPL-3.0
"""

import struct

import numpy as np
import orjson
import pytest

from viz.gl_pack import (
    MAGIC_BATCH,
    MAGIC_CLOUD,
    MAGIC_FRAME,
    RESET_SENTINEL,
    pack_batch,
    pack_cloud,
    pack_frame,
    pack_reset,
)

COLORWAY = ["#636efa", "#EF553B", "#00cc96"]

LAYOUT = {
    "title": "Index: 3",
    "scene": {
        "xaxis": {"range": [-10, 10], "title": {"text": "X (m)"}},
        "yaxis": {"range": [-20, 20], "title": {"text": "Y (m)"}},
        "zaxis": {"range": [-5, 5], "title": {"text": "Z (m)"}},
        "aspectratio": {"x": 2.0, "y": 4.0, "z": 1.0},
    },
}


def numerical_trace(count=4):
    """One trace coloured by a value, as the numerical branch emits."""
    return {
        "type": "scatter3d",
        "ids": np.arange(count),
        "x": np.arange(count, dtype=float),
        "y": np.arange(count, dtype=float) + 1,
        "z": np.arange(count, dtype=float) + 2,
        "mode": "markers",
        "name": "detections",
        "showlegend": True,
        "marker": {
            "size": 3,
            "color": np.linspace(0.0, 1.0, count),
            "colorbar": {"title": {"text": "Speed"}},
            "cmin": 0.0,
            "cmax": 1.0,
        },
    }


def categorical_traces():
    """Two traces with no marker colour, as the categorical branch emits."""
    return [
        {
            "type": "scatter3d",
            "ids": np.array([0, 1]),
            "x": np.array([0.0, 1.0]),
            "y": np.array([0.0, 1.0]),
            "z": np.array([0.0, 1.0]),
            "mode": "markers",
            "name": name,
            "showlegend": True,
            "marker": {"size": 3},
        }
        for name in ("alpha", "beta")
    ]


def read_header(blob):
    """Magic, header length and the parsed header."""
    assert blob[:4] == MAGIC_FRAME
    length = struct.unpack_from("<I", blob, 4)[0]
    return orjson.loads(blob[8 : 8 + length])


def section(blob, descriptor, dtype):
    """A section read back as the type the header declares."""
    return np.frombuffer(
        blob,
        dtype=dtype,
        count=descriptor["len"] // np.dtype(dtype).itemsize,
        offset=descriptor["off"],
    )


class TestTheContainer:
    def test_it_starts_with_its_magic(self):
        blob = pack_frame(3, [numerical_trace()], None, [], LAYOUT, COLORWAY)

        assert blob[:4] == MAGIC_FRAME

    def test_the_header_length_matches_the_header(self):
        blob = pack_frame(3, [numerical_trace()], None, [], LAYOUT, COLORWAY)
        length = struct.unpack_from("<I", blob, 4)[0]

        orjson.loads(blob[8 : 8 + length])  # would raise if the length were wrong

    def test_every_section_is_four_byte_aligned(self):
        # The reason the whole format exists: a misaligned offset makes the
        # browser's typed-array view constructor throw.
        blob = pack_frame(
            3, [numerical_trace(7)], [["x" * 5] * 7], [], LAYOUT, COLORWAY
        )
        header = read_header(blob)

        for group in header["groups"]:
            for key in ("pos", "val", "ids", "hoff", "htxt"):
                if group[key]:
                    assert group[key]["off"] % 4 == 0, f"{key} is misaligned"

    def test_sections_sit_inside_the_blob(self):
        blob = pack_frame(3, [numerical_trace(9)], None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        for group in header["groups"]:
            for key in ("pos", "val", "ids", "hoff", "htxt"):
                part = group[key]
                if part:
                    assert part["off"] + part["len"] <= len(blob)


class TestTheGeometry:
    def test_coordinates_round_trip(self):
        blob = pack_frame(3, [numerical_trace(4)], None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        points = section(blob, header["groups"][0]["pos"], np.float32).reshape(-1, 3)

        assert points.tolist() == [
            [0.0, 1.0, 2.0],
            [1.0, 2.0, 3.0],
            [2.0, 3.0, 4.0],
            [3.0, 4.0, 5.0],
        ]

    def test_the_count_matches_the_section_length(self):
        blob = pack_frame(3, [numerical_trace(6)], None, [], LAYOUT, COLORWAY)
        header = read_header(blob)
        group = header["groups"][0]

        assert group["count"] == 6
        assert group["pos"]["len"] == 6 * 3 * 4
        assert group["val"]["len"] == 6 * 4
        assert group["ids"]["len"] == 6 * 4

    def test_a_vertex_with_a_missing_component_is_dropped(self):
        trace = numerical_trace(3)
        trace["y"] = np.array([0.0, np.nan, 2.0])
        blob = pack_frame(3, [trace], None, [], LAYOUT, COLORWAY)

        assert read_header(blob)["groups"][0]["count"] == 2


class TestTheColourMode:
    def test_a_marker_colour_array_makes_it_numerical(self):
        blob = pack_frame(3, [numerical_trace()], None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert header["c_type"] == "numerical"
        assert header["c_range"] == [0.0, 1.0]
        assert header["c_label"] == "Speed"
        assert header["groups"][0]["val"] is not None
        assert header["groups"][0]["rgb"] is None

    def test_no_marker_colour_makes_it_categorical(self):
        blob = pack_frame(3, categorical_traces(), None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert header["c_type"] == "categorical"
        for group in header["groups"]:
            assert group["val"] is None

    def test_categorical_groups_take_the_colorway_in_order(self):
        # Resolved server-side precisely so the two renderers cannot disagree
        # about which group is which colour.
        blob = pack_frame(3, categorical_traces(), None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert [group["rgb"] for group in header["groups"]] == [
            [0x63, 0x6E, 0xFA],
            [0xEF, 0x55, 0x3B],
        ]

    def test_the_colorway_wraps(self):
        traces = categorical_traces() * 2  # four groups, three colours
        blob = pack_frame(3, traces, None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert header["groups"][3]["rgb"] == header["groups"][0]["rgb"]


class TestHoverText:
    def test_the_offsets_slice_the_blob(self):
        texts = ["a", "bb", "ccc", "dddd"]
        blob = pack_frame(3, [numerical_trace(4)], [texts], [], LAYOUT, COLORWAY)
        header = read_header(blob)
        group = header["groups"][0]

        offsets = section(blob, group["hoff"], np.uint32)
        text = blob[group["htxt"]["off"] : group["htxt"]["off"] + group["htxt"]["len"]]

        assert [
            text[offsets[i] : offsets[i + 1]].decode() for i in range(len(offsets) - 1)
        ] == texts

    def test_there_is_one_more_offset_than_points(self):
        blob = pack_frame(3, [numerical_trace(5)], [["x"] * 5], [], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert header["groups"][0]["hoff"]["len"] // 4 == 6

    def test_the_offsets_only_increase(self):
        blob = pack_frame(
            3, [numerical_trace(5)], [["", "a", "", "bb", "c"]], [], LAYOUT, COLORWAY
        )
        header = read_header(blob)

        offsets = section(blob, header["groups"][0]["hoff"], np.uint32)

        assert np.all(np.diff(offsets.astype(np.int64)) >= 0)

    def test_the_last_offset_is_the_blob_length(self):
        blob = pack_frame(
            3, [numerical_trace(4)], [["a", "bb", "ccc", "d"]], [], LAYOUT, COLORWAY
        )
        header = read_header(blob)
        group = header["groups"][0]

        offsets = section(blob, group["hoff"], np.uint32)

        assert offsets[-1] == group["htxt"]["len"]

    def test_a_frame_without_hover_still_packs(self):
        # The buffer only carries hover text for a paused view.
        blob = pack_frame(3, [numerical_trace(4)], None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert header["groups"][0]["htxt"]["len"] == 0


class TestTheEmptyFrame:
    def test_a_filtered_out_frame_packs_to_nothing(self):
        # `get_scatter3d_data` emits a placeholder trace with empty coordinates
        # and no marker key at all when a filter removes everything.
        placeholder = {
            "type": "scatter3d",
            "x": [],
            "y": [],
            "z": [],
            "mode": "markers",
        }
        blob = pack_frame(3, [placeholder], None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert header["groups"][0]["count"] == 0

    def test_a_frame_with_no_traces_packs(self):
        blob = pack_frame(3, [], None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert header["groups"] == []
        assert header["layout"]["ranges"]["x"] == [-10.0, 10.0]


class TestTheIdGuard:
    def test_an_index_too_wide_for_uint32_is_refused(self):
        trace = numerical_trace(2)
        trace["ids"] = np.array([0, 2**33], dtype=np.int64)

        with pytest.raises(ValueError, match="uint32"):
            pack_frame(3, [trace], None, [], LAYOUT, COLORWAY)

    def test_ids_round_trip(self):
        trace = numerical_trace(3)
        trace["ids"] = np.array([7, 1000, 123456], dtype=np.int64)
        blob = pack_frame(3, [trace], None, [], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert section(blob, header["groups"][0]["ids"], np.uint32).tolist() == [
            7,
            1000,
            123456,
        ]


class TestTheReference:
    def test_a_mesh_carries_its_faces(self):
        mesh = {
            "type": "mesh3d",
            "x": [0.0, 1.0, 0.0],
            "y": [0.0, 0.0, 1.0],
            "z": [0.0, 0.0, 0.0],
            "i": [0],
            "j": [1],
            "k": [2],
            "color": "#ffffff",
            "opacity": 0.35,
            "name": "Ego",
        }
        blob = pack_frame(3, [], None, [mesh], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert header["ref"]["mesh"]["count"] == 3
        assert header["ref"]["mesh"]["rgb"] == [255, 255, 255]
        assert section(blob, header["ref"]["mesh"]["faces"], np.uint32).tolist() == [
            0,
            1,
            2,
        ]

    def test_a_pen_lift_splits_the_outline_into_segments(self):
        # `_edge_trace` draws a whole wireframe as one polyline with None
        # between edges; LineSegments wants pairs.
        edges = {
            "type": "scatter3d",
            "mode": "lines",
            "name": "Ego",
            "x": [0.0, 1.0, None, 2.0, 3.0],
            "y": [0.0, 0.0, None, 0.0, 0.0],
            "z": [0.0, 0.0, None, 0.0, 0.0],
            "line": {"color": "#ffffff", "width": 2},
        }
        blob = pack_frame(3, [], None, [edges], LAYOUT, COLORWAY)
        header = read_header(blob)

        # Two edges, two vertices each.
        assert header["ref"]["edges"]["count"] == 4

    def test_a_plain_marker_reference_packs(self):
        marker = {
            "type": "scatter3d",
            "mode": "markers",
            "name": "Origin",
            "x": [1.0],
            "y": [2.0],
            "z": [3.0],
            "marker": {"color": "rgb(255, 255, 255)", "size": 6},
        }
        blob = pack_frame(3, [], None, [marker], LAYOUT, COLORWAY)
        header = read_header(blob)

        assert header["ref"]["marker"]["count"] == 1
        assert header["ref"]["marker"]["rgb"] == [255, 255, 255]


class TestTheLayout:
    def test_the_ranges_are_taken_as_given(self):
        # Fixed from the filter sliders with autorange off, so they must not be
        # re-derived from the points.
        blob = pack_frame(3, [numerical_trace()], None, [], LAYOUT, COLORWAY)

        assert read_header(blob)["layout"]["ranges"] == {
            "x": [-10.0, 10.0],
            "y": [-20.0, 20.0],
            "z": [-5.0, 5.0],
        }

    def test_the_aspect_ratio_survives(self):
        blob = pack_frame(3, [numerical_trace()], None, [], LAYOUT, COLORWAY)

        assert read_header(blob)["layout"]["aspect"] == {"x": 2.0, "y": 4.0, "z": 1.0}

    def test_the_axis_labels_survive(self):
        blob = pack_frame(3, [numerical_trace()], None, [], LAYOUT, COLORWAY)

        assert read_header(blob)["layout"]["labels"]["y"] == "Y (m)"


class TestTheBatch:
    def test_it_carries_a_length_per_frame(self):
        one = pack_frame(0, [numerical_trace(2)], None, [], LAYOUT, COLORWAY)
        two = pack_frame(1, [numerical_trace(9)], None, [], LAYOUT, COLORWAY)

        batch = pack_batch([one, two])

        assert batch[:4] == MAGIC_BATCH
        assert struct.unpack_from("<I", batch, 4)[0] == 2
        assert struct.unpack_from("<I", batch, 8)[0] == len(one)
        assert struct.unpack_from("<I", batch, 12)[0] == len(two)

    def test_the_frames_can_be_sliced_back_out(self):
        frames = [
            pack_frame(i, [numerical_trace(i + 1)], None, [], LAYOUT, COLORWAY)
            for i in range(3)
        ]
        batch = pack_batch(frames)

        count = struct.unpack_from("<I", batch, 4)[0]
        cursor = 8 + count * 4
        recovered = []
        for i in range(count):
            length = struct.unpack_from("<I", batch, 8 + i * 4)[0]
            recovered.append(batch[cursor : cursor + length])
            cursor += length

        assert recovered == frames

    def test_an_empty_batch_is_not_a_reset(self):
        batch = pack_batch([])

        assert struct.unpack_from("<I", batch, 4)[0] == 0

    def test_the_reset_sentinel_is_distinct(self):
        assert struct.unpack_from("<I", pack_reset(), 4)[0] == RESET_SENTINEL


class TestTheCloud:
    def test_it_packs_the_points(self):
        points = np.arange(9, dtype=np.float64).reshape(3, 3)

        blob = pack_cloud(points, {"color": "#8d99ae", "size": 1.2})

        assert blob[:4] == MAGIC_CLOUD
        length = struct.unpack_from("<I", blob, 4)[0]
        header = orjson.loads(blob[8 : 8 + length])
        assert header["count"] == 3
        assert header["rgb"] == [0x8D, 0x99, 0xAE]

    def test_extra_columns_are_dropped(self):
        # A cloud may carry intensity or ring beyond xyz; the backdrop is
        # position only.
        points = np.arange(20, dtype=np.float64).reshape(4, 5)

        blob = pack_cloud(points, None)
        length = struct.unpack_from("<I", blob, 4)[0]
        prefix = 8 + length
        start = prefix + (-prefix) % 4

        assert len(blob) - start == 4 * 3 * 4

    def test_no_cloud_packs_to_a_count_of_zero(self):
        blob = pack_cloud(None, None)
        length = struct.unpack_from("<I", blob, 4)[0]

        assert orjson.loads(blob[8 : 8 + length])["count"] == 0
