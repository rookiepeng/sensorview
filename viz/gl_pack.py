"""Binary frame packing for the WebGL renderer.

The figure buffer feeds two renderers. Plotly wants the trace dictionaries it
has always been given; the WebGL renderer wants flat typed arrays, and getting
them out of JSON costs a parse of every coordinate and -- far worse -- a parse
of one hover string per point. This module writes the same frame a second time
in a form the browser can hand straight to the GPU.

Nothing is recomputed here. The traces have already been built by
:mod:`viz.graph_data`; this only re-serializes them, so the two bundles cannot
disagree about what is in the frame.

Container, one blob per frame::

    offset  bytes  content
    0       4      magic "SVF1"
    4       4      uint32 header length
    8       H      header, JSON, utf-8
    8+H     pad    zeros to the next 4-byte boundary
    ...            sections, at the offsets the header declares

Every section is 4-byte aligned because a ``Float32Array`` view onto a
misaligned offset throws in the browser, and the alternative -- copying each
section out -- would give back the copy this format exists to avoid.

Usage:
    from viz.gl_pack import pack_frame, pack_batch

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import orjson

MAGIC_FRAME = b"SVF1"
MAGIC_BATCH = b"SVB1"
MAGIC_CLOUD = b"SVC1"

# Tells the client the buffer restarted, as `[{"index": -1}]` does on the JSON
# route. A count rather than a flag, so "nothing new" (0) stays distinct.
RESET_SENTINEL = 0xFFFFFFFF

# ids are the DataFrame index, packed as uint32. Anything wider would have to
# go as float64 and lose exactness above 2**53; a log with four billion rows in
# one frame is not a thing this app can draw anyway.
MAX_ID = 0xFFFFFFFF


def _align(buffers: List[bytes], offset: int) -> int:
    """
    Pad to the next 4-byte boundary.

    Args:
        buffers: Output list, appended to in place.
        offset: Current byte offset.

    Returns:
        The new offset.
    """
    pad = (-offset) % 4
    if pad:
        buffers.append(b"\0" * pad)
    return offset + pad


def _section(
    buffers: List[bytes], offset: int, array: np.ndarray, dtype: str
) -> Tuple[Dict[str, Any], int]:
    """
    Append one array as a section and describe it.

    Args:
        buffers: Output list, appended to in place.
        offset: Current byte offset.
        array: Values to write.
        dtype: Declared element type, one of ``f32``, ``u32``, ``u8``.

    Returns:
        The section descriptor and the new offset.
    """
    offset = _align(buffers, offset)
    raw = np.ascontiguousarray(array).tobytes()
    buffers.append(raw)
    return {"off": offset, "len": len(raw), "dtype": dtype}, offset + len(raw)


def _xyz(trace: Dict[str, Any]) -> np.ndarray:
    """
    Interleave a trace's coordinates into an (N, 3) float32 array.

    Vertices with a missing component are dropped: a line trace lifts the pen
    with ``None``, and a filtered frame can carry NaN.

    Args:
        trace: A scatter3d or mesh3d trace.

    Returns:
        Contiguous (N, 3) float32 array.
    """
    columns = []
    for axis in ("x", "y", "z"):
        values = trace.get(axis)
        if values is None:
            return np.zeros((0, 3), dtype=np.float32)
        columns.append(
            np.asarray(
                [np.nan if value is None else value for value in values],
                dtype=np.float64,
            )
        )

    size = min(column.size for column in columns)
    stacked = np.stack([column[:size] for column in columns], axis=1)
    return np.ascontiguousarray(
        stacked[np.isfinite(stacked).all(axis=1)], dtype=np.float32
    )


def _hover_blob(
    strings: Optional[Sequence[str]], count: int
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Pack a group's hover text as one blob plus an offset table.

    This is the reason the binary path is worth having. A frame's hover text is
    a string per point, each one a dozen labelled fields; as JSON that is the
    largest thing in the bundle and every point of it is parsed to show one
    tooltip. Here the whole group is one UTF-8 buffer, and a tooltip costs a
    decode of the slice between two offsets.

    Args:
        strings: Hover text per point, or None.
        count: How many points the group has.

    Returns:
        The offset table (``count + 1`` uint32 values) and the text blob.
    """
    if not strings:
        return np.zeros(1, dtype=np.uint32), np.zeros(0, dtype=np.uint8)

    encoded = [str(text).encode("utf-8") for text in list(strings)[:count]]
    encoded.extend(b"" for _ in range(count - len(encoded)))

    offsets = np.zeros(count + 1, dtype=np.uint32)
    running = 0
    for i, item in enumerate(encoded):
        running += len(item)
        offsets[i + 1] = running

    return offsets, np.frombuffer(b"".join(encoded), dtype=np.uint8)


def _pack_groups(
    buffers: List[bytes],
    offset: int,
    fig: Sequence[Dict[str, Any]],
    hover_strings: Optional[Sequence[Sequence[str]]],
    colorway: Sequence[str],
) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]]:
    """
    Pack the detection traces.

    Args:
        buffers: Output list, appended to in place.
        offset: Current byte offset.
        fig: The frame's scatter traces.
        hover_strings: Hover text per trace.
        colorway: Categorical palette, in the order Plotly assigns it.

    Returns:
        Group descriptors, the new offset, and the frame-level colour facts.
    """
    groups: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {
        "c_type": "categorical",
        "c_range": [0.0, 1.0],
        "c_label": "",
        "base_size": 3,
    }

    for index, trace in enumerate(fig or []):
        marker = trace.get("marker") or {}
        colors = marker.get("color")
        numerical = isinstance(colors, (list, tuple, np.ndarray))

        points = _xyz(trace)
        count = int(points.shape[0])

        descriptor: Dict[str, Any] = {
            "name": "" if trace.get("name") is None else str(trace["name"]),
            "count": count,
            "showlegend": trace.get("showlegend", True) is not False,
        }

        if isinstance(marker.get("size"), (int, float)):
            meta["base_size"] = marker["size"]

        if numerical:
            meta["c_type"] = "numerical"
            if marker.get("cmin") is not None and marker.get("cmax") is not None:
                meta["c_range"] = [float(marker["cmin"]), float(marker["cmax"])]
            title = (marker.get("colorbar") or {}).get("title") or {}
            meta["c_label"] = title.get("text") or meta["c_label"]
            descriptor["rgb"] = None
        else:
            # Plotly assigns colorway entries in trace order and wraps. Resolved
            # here rather than in the browser so both renderers are reading one
            # table instead of two that have to be kept in step.
            descriptor["rgb"] = _hex_to_rgb(colorway[index % len(colorway)])

        section, offset = _section(buffers, offset, points.reshape(-1), "f32")
        descriptor["pos"] = section

        if numerical:
            values = np.asarray(colors, dtype=np.float64)[: len(points)]
            values = np.nan_to_num(values.astype(np.float32), nan=0.0)
            section, offset = _section(buffers, offset, values, "f32")
            descriptor["val"] = section
        else:
            descriptor["val"] = None

        ids = trace.get("ids")
        if ids is not None and count:
            as_array = np.asarray(ids)[:count]
            if as_array.size and np.nanmax(as_array) > MAX_ID:
                raise ValueError(
                    "row index exceeds the uint32 the GL buffer packs ids as; "
                    f"max was {np.nanmax(as_array)}"
                )
            section, offset = _section(
                buffers, offset, as_array.astype(np.uint32), "u32"
            )
            descriptor["ids"] = section
        else:
            descriptor["ids"] = None

        texts = (
            hover_strings[index]
            if hover_strings and index < len(hover_strings)
            else None
        )
        offsets, blob = _hover_blob(texts, count)
        section, offset = _section(buffers, offset, offsets, "u32")
        descriptor["hoff"] = section
        section, offset = _section(buffers, offset, blob, "u8")
        descriptor["htxt"] = section

        groups.append(descriptor)

    return groups, offset, meta


def _hex_to_rgb(value: str) -> List[int]:
    """
    Parse a colour as Plotly writes a colorway entry.

    Args:
        value: ``#rrggbb`` or ``rgb(r, g, b)``.

    Returns:
        ``[r, g, b]``, each 0-255.
    """
    text = str(value).strip()
    if text.startswith("#"):
        text = text[1:]
        if len(text) == 3:
            text = "".join(character * 2 for character in text)
        return [int(text[i : i + 2], 16) for i in (0, 2, 4)]

    if text.lower().startswith("rgb"):
        inner = text[text.find("(") + 1 : text.find(")")]
        parts = [float(part) for part in inner.split(",")[:3]]
        return [int(part) for part in parts]

    return [128, 128, 128]


def _pack_reference(
    buffers: List[bytes], offset: int, ref_fig: Sequence[Dict[str, Any]]
) -> Tuple[Dict[str, Any], int]:
    """
    Pack the reference overlay: body, outline, or marker.

    Args:
        buffers: Output list, appended to in place.
        offset: Current byte offset.
        ref_fig: The frame's reference traces.

    Returns:
        The reference descriptor and the new offset.
    """
    ref: Dict[str, Any] = {"mesh": None, "edges": None, "marker": None, "name": ""}

    for trace in ref_fig or []:
        if trace.get("name"):
            ref["name"] = str(trace["name"])

        if trace.get("type") == "mesh3d":
            vertices = _xyz(trace)
            if not vertices.size:
                continue
            faces = np.stack(
                [
                    np.asarray(trace.get(key) or [], dtype=np.uint32)
                    for key in ("i", "j", "k")
                ],
                axis=1,
            ).reshape(-1)
            section, offset = _section(buffers, offset, vertices.reshape(-1), "f32")
            index_section, offset = _section(buffers, offset, faces, "u32")
            ref["mesh"] = {
                "verts": section,
                "faces": index_section,
                "count": int(vertices.shape[0]),
                "rgb": _hex_to_rgb(trace.get("color") or "#ffffff"),
                "opacity": trace.get("opacity", 0.35),
            }
            continue

        if trace.get("mode") == "lines":
            segments = _edge_segments(trace)
            if not segments.size:
                continue
            section, offset = _section(buffers, offset, segments.reshape(-1), "f32")
            ref["edges"] = {
                "segs": section,
                "count": int(segments.shape[0]),
                "rgb": _hex_to_rgb((trace.get("line") or {}).get("color") or "#ffffff"),
            }
            continue

        points = _xyz(trace)
        if not points.size:
            continue
        marker = trace.get("marker") or {}
        section, offset = _section(buffers, offset, points.reshape(-1), "f32")
        ref["marker"] = {
            "pos": section,
            "count": int(points.shape[0]),
            "rgb": _hex_to_rgb(marker.get("color") or "rgb(255,255,255)"),
            "size": marker.get("size", 6),
        }

    return ref, offset


def _edge_segments(trace: Dict[str, Any]) -> np.ndarray:
    """
    Turn a pen-lifting polyline into discrete vertex pairs.

    ``_edge_trace`` draws a whole wireframe as one trace with ``None`` between
    edges. ``LineSegments`` wants pairs, so each run between lifts becomes its
    own chain of pairs -- which handles a run longer than two without assuming
    one.

    Args:
        trace: A ``mode: "lines"`` scatter3d trace.

    Returns:
        (2 * segments, 3) float32 array.
    """
    xs, ys, zs = trace.get("x") or [], trace.get("y") or [], trace.get("z") or []
    size = min(len(xs), len(ys), len(zs))

    segments: List[List[float]] = []
    run: List[List[float]] = []

    def flush() -> None:
        for i in range(len(run) - 1):
            segments.append(run[i])
            segments.append(run[i + 1])
        run.clear()

    for i in range(size):
        if xs[i] is None or ys[i] is None or zs[i] is None:
            flush()
            continue
        run.append([float(xs[i]), float(ys[i]), float(zs[i])])
    flush()

    if not segments:
        return np.zeros((0, 3), dtype=np.float32)
    return np.asarray(segments, dtype=np.float32)


def _layout_header(layout: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reduce a Plotly layout to the scene geometry the renderer needs.

    Args:
        layout: The frame's layout, from ``get_scatter3d_layout``.

    Returns:
        Ranges, aspect ratio, axis labels, and title.
    """
    scene = (layout or {}).get("scene") or {}

    def axis(key: str) -> Tuple[List[float], str]:
        config = scene.get(key) or {}
        bounds = config.get("range") or [-20, 20]
        title = (config.get("title") or {}).get("text")
        return [float(bounds[0]), float(bounds[1])], "" if title is None else str(title)

    x_range, x_label = axis("xaxis")
    y_range, y_label = axis("yaxis")
    z_range, z_label = axis("zaxis")
    aspect = scene.get("aspectratio") or {"x": 1, "y": 1, "z": 1}
    title = (layout or {}).get("title")

    return {
        "ranges": {"x": x_range, "y": y_range, "z": z_range},
        "aspect": {
            "x": float(aspect.get("x", 1)),
            "y": float(aspect.get("y", 1)),
            "z": float(aspect.get("z", 1)),
        },
        "labels": {"x": x_label, "y": y_label, "z": z_label},
        "title": title if isinstance(title, str) else (title or {}).get("text", ""),
    }


def _shift_offsets(header: Dict[str, Any], shift: int) -> Dict[str, Any]:
    """
    Rewrite every section offset as it will sit in the finished blob.

    Sections are measured from the start of the section area; in the blob that
    area begins after the header. Returns a copy rather than mutating, so the
    caller can try a different shift without the previous one baked in.

    Args:
        header: Frame header, with offsets relative to the section area.
        shift: Byte offset the section area starts at.

    Returns:
        A copy of the header with absolute offsets.
    """

    def move(section: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not section:
            return section
        return {**section, "off": section["off"] + shift}

    groups = []
    for group in header["groups"]:
        moved = dict(group)
        for key in ("pos", "val", "ids", "hoff", "htxt"):
            moved[key] = move(group.get(key))
        groups.append(moved)

    ref = dict(header["ref"])
    for part, keys in (
        ("mesh", ("verts", "faces")),
        ("edges", ("segs",)),
        ("marker", ("pos",)),
    ):
        if ref.get(part):
            moved = dict(ref[part])
            for key in keys:
                moved[key] = move(ref[part].get(key))
            ref[part] = moved

    return {**header, "groups": groups, "ref": ref}


def pack_frame(
    index: int,
    fig: Sequence[Dict[str, Any]],
    hover_strings: Optional[Sequence[Sequence[str]]],
    ref_fig: Sequence[Dict[str, Any]],
    layout: Dict[str, Any],
    colorway: Sequence[str],
) -> bytes:
    """
    Pack one frame.

    Args:
        index: Slider position this frame is for.
        fig: Detection traces.
        hover_strings: Hover text per trace.
        ref_fig: Reference traces.
        layout: The figure layout.
        colorway: Categorical palette, in Plotly's assignment order.

    Returns:
        The frame blob.

    Raises:
        ValueError: If a row index does not fit the uint32 ids are packed as.
    """
    buffers: List[bytes] = []
    offset = 0

    groups, offset, meta = _pack_groups(buffers, offset, fig, hover_strings, colorway)
    ref, offset = _pack_reference(buffers, offset, ref_fig)

    header = {
        "index": int(index),
        "groups": groups,
        "ref": ref,
        "layout": _layout_header(layout),
    }
    header.update(meta)

    # Sections were measured from the start of the section area, which sits
    # after the header -- and the header's length depends on the offsets it
    # carries, since a larger offset is more digits. So the shift is solved
    # rather than assumed: guess, re-serialize, repeat until the length stops
    # moving. Two or three rounds in practice; bounded so a pathological case
    # fails loudly instead of spinning.
    def with_shift(value):
        blob = orjson.dumps(
            _shift_offsets(header, value), option=orjson.OPT_SERIALIZE_NUMPY
        )
        prefix = len(MAGIC_FRAME) + 4 + len(blob)
        return blob, prefix + (-prefix) % 4

    encoded, shift = with_shift(0)
    for _ in range(8):
        encoded, settled = with_shift(shift)
        if settled == shift:
            break
        shift = settled
    else:
        raise AssertionError("frame header length did not settle")

    pad = shift - (len(MAGIC_FRAME) + 4 + len(encoded))

    return b"".join(
        [MAGIC_FRAME, len(encoded).to_bytes(4, "little"), encoded, b"\0" * pad]
        + buffers
    )


def pack_batch(frames: Sequence[bytes]) -> bytes:
    """
    Concatenate frame blobs for one HTTP response.

    Args:
        frames: Frame blobs, in slider order.

    Returns:
        The batch blob: magic, count, a length table, then the frames.
    """
    header = [MAGIC_BATCH, len(frames).to_bytes(4, "little")]
    header.extend(len(frame).to_bytes(4, "little") for frame in frames)
    return b"".join(header + list(frames))


def pack_reset() -> bytes:
    """
    The "buffer restarted" response.

    Returns:
        A batch blob carrying the reset sentinel instead of a frame count.
    """
    return MAGIC_BATCH + RESET_SENTINEL.to_bytes(4, "little")


def pack_cloud(
    points: Optional[np.ndarray], display: Optional[Dict[str, Any]]
) -> bytes:
    """
    Pack the point-cloud backdrop.

    Takes the raw array rather than the Plotly trace, which skips the per-axis
    contiguous copies ``get_cloud_scatter3d_data`` makes only to satisfy orjson.

    Args:
        points: (N, 3+) array of decimated points, or None.
        display: Manifest styling for the cloud.

    Returns:
        The cloud blob.
    """
    display = display or {}
    if points is None or len(points) == 0:
        xyz = np.zeros((0, 3), dtype=np.float32)
    else:
        xyz = np.ascontiguousarray(np.asarray(points)[:, :3], dtype=np.float32)

    header = orjson.dumps(
        {
            "count": int(xyz.shape[0]),
            "rgb": _hex_to_rgb(display.get("color", "#8d99ae")),
            "size": display.get("size", 1.2),
            "opacity": display.get("opacity", 0.35),
            "name": display.get("name", "Point Cloud"),
        }
    )
    prefix_len = len(MAGIC_CLOUD) + 4 + len(header)
    pad = (-prefix_len) % 4

    return b"".join(
        [
            MAGIC_CLOUD,
            len(header).to_bytes(4, "little"),
            header,
            b"\0" * pad,
            xyz.reshape(-1).tobytes(),
        ]
    )
