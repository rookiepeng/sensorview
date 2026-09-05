"""SensorView HTTP API Routes

The endpoints the browser fetches on its own, outside Dash's callback protocol.
Three things need that: the figure buffer the WebWorker fills, the point-cloud
backdrop, and the camera mp4 a ``<video>`` element seeks. All three move payloads
too large or too stream-shaped to travel as callback outputs.

Every one of them is keyed on a session id and resolves paths through that
session's cached manifest, never from the URL, so a request cannot reach outside
the dataset directory.

Usage:
    from routes import register_api_routes
    register_api_routes(app)

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import orjson
from flask import Response, abort, send_file

import dash

from settings import CACHE_KEYS
from utils import cache_get

from frame_sources import (
    get_frame_stem,
    get_log_stems,
    get_manifest,
    get_cloud_trace,
    playable_image_file,
)


def register_api_routes(app: dash.Dash) -> None:
    """
    Register the plain HTTP endpoints on the app's Flask server.

    Args:
        app: The Dash application instance.

    Returns:
        None
    """

    @app.server.route("/api/data/<session>/<start_index_str>", methods=["GET"])
    def get_data_by_index(session: str, start_index_str: str) -> Response:
        """
        Retrieve buffered figure data from cache for a specific session.

        Args:
            session: Unique session identifier for data isolation.
            start_index_str: Starting index from which to retrieve data (converted to int).

        Returns:
            JSON response containing:
                - If start_index_str > latest_server_buffer_index: [{"index": -1}]
                - If start_index_str == latest_server_buffer_index: []
                - Otherwise: List of dictionaries with figure data, hover strings,
                  reference figures, and layouts for each index.
        """
        latest_server_buffer_index = cache_get(session, CACHE_KEYS["figure_idx"])
        start_index = int(start_index_str)

        if latest_server_buffer_index is None:
            latest_server_buffer_index = -1

        _orjson_opts = orjson.OPT_SERIALIZE_NUMPY

        if start_index > latest_server_buffer_index:
            return Response(
                orjson.dumps([{"index": -1}]),
                mimetype="application/json",
            )

        if start_index == latest_server_buffer_index:
            return Response(orjson.dumps([]), mimetype="application/json")

        # Cap the number of frames returned per request to prevent huge JSON responses
        # that cause browser memory spikes. storeBuffer polls on an interval and will
        # pick up remaining frames in subsequent requests.
        MAX_BATCH_SIZE = 40
        end_index = min(
            start_index + 1 + MAX_BATCH_SIZE, latest_server_buffer_index + 1
        )

        buffer = []
        for idx in range(start_index + 1, end_index):
            bundle = cache_get(session, CACHE_KEYS["figure_bundle"], str(idx))
            if bundle is not None:
                buffer.append(
                    {
                        "index": idx,
                        "fig": bundle["fig"],
                        "hover_strings": bundle["hover_strings"],
                        "ref_fig": bundle["ref_fig"],
                        "fig_layout": bundle["fig_layout"],
                    }
                )

        return Response(
            orjson.dumps(buffer, option=_orjson_opts), mimetype="application/json"
        )

    @app.server.route("/api/cloud/<session>/<int:frame_idx>", methods=["GET"])
    def get_cloud_frame(session: str, frame_idx: int) -> Response:
        """
        Serve the point-cloud backdrop trace for one frame.

        The cloud is deliberately kept off the IndexedDB figure-buffer path that the
        radar traces use. The buffer pre-fetches a window of frames ahead, and a
        decimated cloud frame is orders of magnitude larger than a table one --
        buffering it would balloon client storage for data that is pure backdrop.
        Instead the client fetches just the frame it is displaying, and caches it.

        Args:
            session: Session identifier used to look up the manifest and frame list.
            frame_idx: Slider position (an index into the frame list, not a frame id).

        Returns:
            JSON ``{"trace": <scatter3d trace>}``, or ``{"trace": null}`` when the
            dataset has no cloud or that frame is missing.
        """
        empty = Response(orjson.dumps({"trace": None}), mimetype="application/json")

        manifest = get_manifest(session)
        # With logs combined the backdrop comes from whichever log recorded this
        # frame, so the stem is resolved per frame rather than per session.
        stem = get_frame_stem(session, frame_idx)
        if manifest is None or not stem or not manifest.has_cloud(stem):
            return empty

        frame_list = cache_get(session, CACHE_KEYS["frame_list"])
        if frame_list is None or frame_idx < 0 or frame_idx >= len(frame_list):
            return empty

        trace = get_cloud_trace(manifest, stem, frame_list[frame_idx])
        if trace is None:
            return empty

        return Response(
            orjson.dumps({"trace": trace}, option=orjson.OPT_SERIALIZE_NUMPY),
            mimetype="application/json",
        )

    @app.server.route("/api/camera/<session>/<stem>/<stream_id>", methods=["GET"])
    def get_camera_stream(session: str, stem: str, stream_id: str):
        """
        Serve a camera mp4 for the browser's video element.

        Each combined log has its own recording, so which one is served is part of
        the URL -- the video element swaps source as the slider crosses from one
        log into the next.

        The file path still comes from the session's manifest, never from the URL:
        ``stem`` only selects among the logs this session actually loaded, and
        ``stream_id`` among the streams found beside that log, so neither can walk
        outside the dataset directory.

        Args:
            session: Session identifier used to look up the manifest.
            stem: Log stem, which must be one of the session's loaded logs.
            stream_id: Camera stream identifier declared in the manifest.

        Returns:
            The mp4 file response. ``conditional=True`` enables HTTP Range
            requests, which is what makes ``currentTime`` seeking work at all --
            without it the browser must download the whole clip before it can seek.

            A recording in a container browsers cannot play is transcoded on first
            request and served from the video cache, so this can block for a few
            seconds once per log.
        """
        manifest = get_manifest(session)
        if manifest is None or stem not in get_log_stems(session):
            abort(404)

        stream = next(
            (s for s in manifest.image_streams(stem) if s["id"] == stream_id), None
        )
        if stream is None:
            abort(404)

        playable = playable_image_file(stream["file"])
        if playable is None:
            abort(404)

        return send_file(playable, mimetype="video/mp4", conditional=True)
