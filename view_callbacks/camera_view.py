"""SensorView Camera View Callbacks

Drives the mp4 camera panel. The frame slider stays the single source of truth
for time: the video element never plays on its own, it is seeked to the frame
the rest of the app is showing.

Seeking is index-based (``(frame_index + 0.5) / fps``) rather than keyed off
dataset timestamps. Video frame *i* is slider index *i* by construction at
ingest, and an index mapping stays correct even when capture timing is not
perfectly uniform. The half-frame offset lands mid-frame so float rounding
cannot spill onto a neighbour.

Usage:
    from view_callbacks.camera_view import get_camera_view_callbacks
    get_camera_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

from typing import Any, Dict

import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from frame_sources import get_log_info, get_manifest

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
        streams = manifest.camera_streams(stem) if manifest else []

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
        output={"panel_style": Output("subview-panel", "style")},
        inputs={"unused_file_loaded": Input("file-loaded-trigger", "data")},
        state={"session_id": State("session-id", "data")},
    )
    def toggle_subview_panel(
        unused_file_loaded: int, session_id: str
    ) -> Dict[str, Any]:
        """
        Show the floating panel only when the log has something to put in it.

        Args:
            unused_file_loaded (int): File load trigger count
            session_id (str): Session identifier

        Returns:
            dict: Panel visibility style
        """
        manifest = get_manifest(session_id)
        stem = get_log_info(session_id).get("stem", "")
        if manifest is None or not stem:
            return {"panel_style": HIDDEN}

        has_content = manifest.has_camera(stem) or bool(
            manifest.has_threshold(stem) and manifest.threshold_plots()
        )
        # Clearing `display` lets the stylesheet's flex layout take over again.
        return {"panel_style": {} if has_content else HIDDEN}

    @app.callback(
        output={
            "src": Output("camera-video", "src"),
            "config": Output("camera-config", "data"),
        },
        inputs={"stream_id": Input("camera-stream-picker", "value")},
        state={"session_id": State("session-id", "data")},
    )
    def select_camera_stream(stream_id: str, session_id: str) -> Dict[str, Any]:
        """
        Point the video element at the selected stream.

        Args:
            stream_id (str): Selected camera stream identifier
            session_id (str): Session identifier

        Returns:
            dict: Video source URL and the descriptor the seek callback reads

        Raises:
            PreventUpdate: If no stream is selected
        """
        if not stream_id:
            raise PreventUpdate

        manifest = get_manifest(session_id)
        log_info = get_log_info(session_id)
        streams = manifest.camera_streams(log_info.get("stem", "")) if manifest else []

        if not any(s["id"] == stream_id for s in streams):
            return {"src": None, "config": None}

        # The rate comes from the log's own timestamps, computed by the same
        # code the ingest used to encode the video -- so the seek maths and the
        # encode can't disagree.
        return {
            "src": f"/api/camera/{session_id}/{stream_id}",
            "config": {
                "src": f"/api/camera/{session_id}/{stream_id}",
                "fps": log_info.get("fps") or 10.0,
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

            const fps = config.fps > 0 ? config.fps : 10;
            // Aim at the middle of the target frame: landing exactly on a
            // boundary can round onto the neighbouring frame.
            const target = (frame_index + 0.5) / fps;

            const seek = function() {
                try {
                    video.currentTime = target;
                } catch (err) {
                    /* Element not seekable yet; the loadedmetadata handler
                       below retries once metadata arrives. */
                }
            };

            if (video.readyState >= 1) {
                seek();
            } else {
                video.addEventListener('loadedmetadata', seek, { once: true });
            }
            return target;
        }
        """,
        Output("camera-seek-ack", "data"),
        Input("slider-frame", "value"),
        Input("camera-config", "data"),
    )
