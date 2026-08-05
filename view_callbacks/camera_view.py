"""SensorView Camera View Callbacks

Drives the mp4 camera panel. The frame slider stays the single source of truth
for time: the video element never plays on its own, it is seeked to the frame
the rest of the app is showing.

Seeking maps frame count to frame count, and is the only mapping there is. The
recording and the log are assumed to start and stop at around the same moment,
so slider frame *i* of *N* lands on video frame *round(i / (N - 1) * (M - 1))*
of *M* -- the closest real frame, whatever rate the camera ran at relative to
the data. A 10 fps dashcam against a 20 Hz radar log therefore advances one
video frame every second slider step instead of being interpolated between two.

Both counts are measured: *M* by ffmpeg from the file (see
``probe_frame_count``), *N* from the log's own Parquet. Frame duration comes
from the video element's ``duration``. No declared rate enters the mapping
anywhere, which is why the manifest needs nothing to describe it -- an earlier
``image.seek`` key is obsolete and ignored.

When *M* cannot be read -- no ffmpeg, or a file it cannot demux -- the video is
left where it is rather than seeked to a guessed position.

Half a frame is added so the seek lands mid-frame, where float rounding cannot
spill onto a neighbour. ``time_offset`` from the manifest shifts the whole clip,
for a recording that did not start rolling with the data after all.

Usage:
    from view_callbacks.camera_view import get_camera_view_callbacks
    get_camera_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

from typing import Any, Dict

import dash
from dash.dependencies import Input, Output, State

from frame_sources import get_log_info, get_manifest, image_stream_frame_count

HIDDEN = {"display": "none"}


def get_camera_view_callbacks(app: dash.Dash) -> None:
    """
    Register the callback functions for the camera view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    @app.callback(
        output={
            "section_style": Output("subview-camera-section", "style"),
            "stream_options": Output("camera-stream-picker", "options"),
            "stream_value": Output("camera-stream-picker", "value"),
            "picker_style": Output("camera-stream-picker-col", "style"),
        },
        inputs={"unused_file_loaded": Input("file-loaded-trigger", "data")},
        state={"session_id": State("session-id", "data")},
    )
    def populate_camera_streams(
        unused_file_loaded: int, session_id: str
    ) -> Dict[str, Any]:
        """
        Populate the stream selector and show or hide the camera section.

        Args:
            unused_file_loaded (int): File load trigger count
            session_id (str): Session identifier

        Returns:
            dict: Section visibility, stream options, and selected stream
        """
        manifest = get_manifest(session_id)
        stem = get_log_info(session_id).get("stem", "")
        streams = manifest.image_streams(stem) if manifest else []

        if not streams:
            return {
                "section_style": HIDDEN,
                "stream_options": [],
                "stream_value": None,
                "picker_style": HIDDEN,
            }

        options = [{"label": s["label"], "value": s["id"]} for s in streams]
        return {
            "section_style": {},
            "stream_options": options,
            "stream_value": streams[0]["id"],
            # A selector is noise when there is only one stream to select.
            "picker_style": HIDDEN if len(streams) == 1 else {},
        }

    @app.callback(
        output={
            "panel_style": Output("subview-panel", "style"),
            "splitter_style": Output("inspector-splitter", "style"),
        },
        inputs={"unused_file_loaded": Input("file-loaded-trigger", "data")},
        state={"session_id": State("session-id", "data")},
    )
    def toggle_subview_panel(
        unused_file_loaded: int, session_id: str
    ) -> Dict[str, Any]:
        """
        Show the floating panel only when the log has something to put in it.

        The panel's resize handle goes with it -- a splitter on the edge of a
        panel that is not there would drag nothing.

        Args:
            unused_file_loaded (int): File load trigger count
            session_id (str): Session identifier

        Returns:
            dict: Panel and splitter visibility styles
        """
        manifest = get_manifest(session_id)
        stem = get_log_info(session_id).get("stem", "")
        if manifest is None or not stem:
            return {"panel_style": HIDDEN, "splitter_style": HIDDEN}

        has_content = manifest.has_image(stem) or bool(
            manifest.has_curve(stem) and manifest.curve_plots()
        )
        # Clearing `display` lets the stylesheet's flex layout take over again.
        style = {} if has_content else HIDDEN
        return {"panel_style": style, "splitter_style": style}

    @app.callback(
        output={
            "src": Output("camera-video", "src"),
            "config": Output("camera-config", "data"),
        },
        inputs={
            "stream_id": Input("camera-stream-picker", "value"),
            # A new log can keep the same stream id (an unnamed stream is
            # always "image"), in which case the picker's value never changes
            # and this callback would otherwise not refire at all. Depending on
            # the trigger directly guarantees it runs on every load.
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
        },
        state={"session_id": State("session-id", "data")},
    )
    def select_camera_stream(
        stream_id: str, unused_file_loaded: int, session_id: str
    ) -> Dict[str, Any]:
        """
        Point the video element at the selected stream.

        Args:
            stream_id (str): Selected camera stream identifier
            unused_file_loaded (int): File load trigger count, used only to
                force a refresh when the stream id is unchanged across logs
            session_id (str): Session identifier

        Returns:
            dict: Video source URL and the descriptor the seek callback reads,
            or both None when the current log has no matching stream
        """
        if not stream_id:
            return {"src": None, "config": None}

        manifest = get_manifest(session_id)
        log_info = get_log_info(session_id)
        streams = manifest.image_streams(log_info.get("stem", "")) if manifest else []

        selected = next((s for s in streams if s["id"] == stream_id), None)
        if selected is None:
            return {"src": None, "config": None}

        # Both counts are measured, never declared. A null video count means the
        # probe failed, and the clientside callback leaves the video alone
        # rather than guessing at a position.
        video_frames = image_stream_frame_count(selected.get("file", ""))
        data_frames = len(log_info.get("timestamps") or [])

        # The load counter is appended as a cache-busting query string: two
        # different logs can share the same session id and stream id (both
        # named "image"), and a browser never reloads a <video src> that comes
        # out identical to what it already has loaded.
        src = f"/api/camera/{session_id}/{stream_id}?v={unused_file_loaded}"
        return {
            "src": src,
            "config": {
                "src": src,
                "video_frames": video_frames,
                "data_frames": data_frames,
                "offset": float((manifest.image or {}).get("time_offset", 0.0)),
            },
        }

    # Seek the video to the current frame. Kept clientside so scrubbing costs
    # no server round trip -- the browser already has the decoded stream.
    app.clientside_callback(
        """
        function(frame_index, config) {
            const no_update = window.dash_clientside.no_update;
            if (config === null || config === undefined || !config.src) {
                return no_update;
            }
            const video = document.getElementById('camera-video');
            if (!video) {
                return no_update;
            }

            const videoFrames = config.video_frames || 0;
            const dataFrames = config.data_frames || 0;
            // Nothing to map between: the probe could not read the file. Leave
            // the video where it is rather than guessing at a position.
            if (videoFrames < 1 || dataFrames < 1) {
                return no_update;
            }

            // Deferred until metadata has landed, because the mapping needs the
            // element's own duration to turn a frame number into a time.
            const computeTarget = function() {
                const duration = video.duration;
                if (!isFinite(duration) || duration <= 0) {
                    return null;
                }
                // Both recordings cover the same stretch of time, so the
                // fraction of the way through the log is the fraction of the
                // way through the video. Mapping count to count rather than
                // second to second means a camera that ran at a different rate
                // than the data still lands on the nearest real frame instead
                // of somewhere between two.
                const span = dataFrames > 1 ? dataFrames - 1 : 1;
                const ratio = Math.min(1, Math.max(0, frame_index / span));
                const k = Math.round(ratio * (videoFrames - 1));
                // Aim at the middle of that frame: landing exactly on a
                // boundary can round onto the neighbouring frame.
                return (k + 0.5) * duration / videoFrames;
            };

            const seek = function() {
                const target = computeTarget();
                if (target === null) {
                    return;
                }
                try {
                    video.currentTime = Math.max(0, target + (config.offset || 0));
                } catch (err) {
                    /* Element not seekable yet; the loadedmetadata handler
                       below retries once metadata arrives. */
                }
            };

            if (video.readyState >= 1) {
                seek();
                return video.currentTime;
            }
            video.addEventListener('loadedmetadata', seek, { once: true });
            return null;
        }
        """,
        Output("camera-seek-ack", "data"),
        Input("slider-frame", "value"),
        Input("camera-config", "data"),
    )
