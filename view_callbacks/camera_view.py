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

Combining logs puts several recordings behind one slider. The mapping is per
log, not per session: the slider is cut into segments, one per run of frames a
log owns, and *N* is that log's own frame count. Crossing into the next segment
swaps the video element's source and then seeks within it, so each log is
measured against its own recording rather than against the concatenated span.

Half a frame is added so the seek lands mid-frame, where float rounding cannot
spill onto a neighbour. ``time_offset`` from the manifest shifts the whole clip,
for a recording that did not start rolling with the data after all.

Usage:
    from view_callbacks.camera_view import get_camera_view_callbacks
    get_camera_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

from typing import Any, Dict, List

import dash
from dash.dependencies import Input, Output, State

from frame_sources import get_log_info, get_manifest, image_stream_frame_count

HIDDEN = {"display": "none"}


def _frame_runs(frame_stems: List[str]) -> List[Dict[str, Any]]:
    """
    Cut the slider into runs of consecutive frames owned by one log.

    Args:
        frame_stems: Owning log stem per slider position.

    Returns:
        List of ``{"stem", "start", "count", "local_start", "local_total"}``.
        ``local_start`` counts how many of that log's frames precede the run and
        ``local_total`` how many it owns overall, so a log whose frames are
        interleaved with another's still maps onto its own recording end to end.
    """
    totals: Dict[str, int] = {}
    for stem in frame_stems:
        totals[stem] = totals.get(stem, 0) + 1

    runs: List[Dict[str, Any]] = []
    consumed: Dict[str, int] = {}
    index = 0
    while index < len(frame_stems):
        stem = frame_stems[index]
        end = index
        while end < len(frame_stems) and frame_stems[end] == stem:
            end += 1
        runs.append(
            {
                "stem": stem,
                "start": index,
                "count": end - index,
                "local_start": consumed.get(stem, 0),
                "local_total": totals[stem],
            }
        )
        consumed[stem] = consumed.get(stem, 0) + (end - index)
        index = end
    return runs


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
            dict: Source URL for the first segment and the descriptor the seek
            callback reads, or both None when no loaded log has a matching
            stream
        """
        if not stream_id:
            return {"src": None, "config": None}

        manifest = get_manifest(session_id)
        if manifest is None:
            return {"src": None, "config": None}

        log_info = get_log_info(session_id)
        frame_count = len(log_info.get("timestamps") or [])
        frame_stems = (
            log_info.get("frame_stems") or [log_info.get("stem", "")] * frame_count
        )

        segments = []
        for run in _frame_runs(frame_stems):
            streams = manifest.image_streams(run["stem"])
            selected = next((s for s in streams if s["id"] == stream_id), None)
            if selected is None:
                # This log recorded no such stream. Leaving the run out means
                # the client holds the previous frame rather than showing
                # another log's footage under this one's data.
                continue

            # Both counts are measured, never declared. A null video count means
            # the probe failed, and the clientside callback leaves the video
            # alone rather than guessing at a position.
            segments.append(
                {
                    # The load counter is appended as a cache-busting query
                    # string: two different logs can share the same session id
                    # and stream id (both named "image"), and a browser never
                    # reloads a <video src> that comes out identical to what it
                    # already has loaded.
                    "src": (
                        f"/api/camera/{session_id}/{run['stem']}/{stream_id}"
                        f"?v={unused_file_loaded}"
                    ),
                    "video_frames": image_stream_frame_count(selected.get("file", "")),
                    "start": run["start"],
                    "count": run["count"],
                    "local_start": run["local_start"],
                    "local_total": run["local_total"],
                }
            )

        if not segments:
            return {"src": None, "config": None}

        return {
            # The slider resets to 0 on load, so the first segment is the one
            # about to be shown; the seek callback swaps it from there.
            "src": segments[0]["src"],
            "config": {
                "segments": segments,
                "offset": float((manifest.image or {}).get("time_offset", 0.0)),
            },
        }

    # Point the video at the segment holding the current frame and seek within
    # it. Kept clientside so scrubbing costs no server round trip -- the browser
    # already has the decoded stream.
    app.clientside_callback(
        """
        function(frame_index, config) {
            const no_update = window.dash_clientside.no_update;
            const hold = [no_update, no_update];
            const segments = (config || {}).segments;
            if (!Array.isArray(segments) || segments.length === 0) {
                return hold;
            }
            const video = document.getElementById('camera-video');
            if (!video) {
                return hold;
            }

            const index = frame_index || 0;
            const segment = segments.find(function (s) {
                return index >= s.start && index < s.start + s.count;
            });
            // No segment owns this frame: the log it belongs to recorded no
            // stream. Hold the current picture rather than showing another
            // log's footage as if it were this one's.
            if (!segment) {
                return hold;
            }

            // Read at fire time rather than captured, so a listener left
            // pending by an earlier frame still seeks to the latest position.
            video.svSeekTarget = { index: index, segment: segment,
                                   offset: (config || {}).offset || 0 };

            // Deferred until metadata has landed, because the mapping needs the
            // element's own duration to turn a frame number into a time.
            const computeTarget = function(target) {
                const duration = video.duration;
                if (!isFinite(duration) || duration <= 0) {
                    return null;
                }
                const seg = target.segment;
                const videoFrames = seg.video_frames || 0;
                const dataFrames = seg.local_total || 0;
                // Nothing to map between: the probe could not read the file.
                // Leave the video where it is rather than guessing.
                if (videoFrames < 1 || dataFrames < 1) {
                    return null;
                }
                // Recording and log cover the same stretch of time, so the
                // fraction of the way through the log is the fraction of the
                // way through the video. Mapping count to count rather than
                // second to second means a camera that ran at a different rate
                // than the data still lands on the nearest real frame instead
                // of somewhere between two.
                const local = seg.local_start + (target.index - seg.start);
                const span = dataFrames > 1 ? dataFrames - 1 : 1;
                const ratio = Math.min(1, Math.max(0, local / span));
                const k = Math.round(ratio * (videoFrames - 1));
                // Aim at the middle of that frame: landing exactly on a
                // boundary can round onto the neighbouring frame.
                return (k + 0.5) * duration / videoFrames;
            };

            const seek = function() {
                const target = video.svSeekTarget;
                if (!target) {
                    return;
                }
                const time = computeTarget(target);
                if (time === null) {
                    return;
                }
                try {
                    video.currentTime = Math.max(0, time + target.offset);
                } catch (err) {
                    /* Element not seekable yet; the loadedmetadata handler
                       below retries once metadata arrives. */
                }
            };

            // Crossing into another log's frames means another recording. The
            // src is handed back as an output so Dash stays the one owning the
            // prop, and the seek waits for the new file's metadata.
            const wanted = segment.src;
            const current = video.getAttribute('src') || '';
            if (current !== wanted) {
                video.addEventListener('loadedmetadata', seek, { once: true });
                return [wanted, null];
            }

            if (video.readyState >= 1) {
                seek();
                return [no_update, video.currentTime];
            }
            video.addEventListener('loadedmetadata', seek, { once: true });
            return [no_update, null];
        }
        """,
        Output("camera-video", "src", allow_duplicate=True),
        Output("camera-seek-ack", "data"),
        Input("slider-frame", "value"),
        Input("camera-config", "data"),
        prevent_initial_call=True,
    )
