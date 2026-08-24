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

Combining logs puts several recordings behind one slider, and logs that share
frame ids put several of them on the *same* slider position. So the panel holds
one video element per loaded log rather than one element the slider re-points:
each element's source is fixed for the life of the load, and *N* is that log's
own frame count. An element whose log recorded nothing at the current position
is hidden, which leaves a single video in the stretches only one log covers and
a grid of them where they overlap.

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
from dash import html
from dash.dependencies import Input, Output, State

from frame_sources import (
    get_frame_positions,
    get_log_stems,
    get_manifest,
    image_stream_frame_count,
)

HIDDEN = {"display": "none"}


def _stem_runs(positions: List[int]) -> List[Dict[str, int]]:
    """
    Compress one log's slider positions into runs of consecutive frames.

    Args:
        positions: Slider positions the log recorded, ascending.

    Returns:
        List of ``{"start", "count", "local_start"}``. ``local_start`` counts
        how many of that log's frames precede the run, so a log whose frames are
        interleaved with another's still maps onto its own recording end to end.
        Runs rather than the raw positions because the whole list is shipped to
        the browser, and a long log has thousands of them.
    """
    runs: List[Dict[str, int]] = []
    index = 0
    while index < len(positions):
        end = index
        while end + 1 < len(positions) and positions[end + 1] == positions[end] + 1:
            end += 1
        runs.append(
            {
                "start": positions[index],
                "count": end - index + 1,
                "local_start": index,
            }
        )
        index = end + 1
    return runs


def _merged_streams(manifest: Any, stems: List[str]) -> List[Dict[str, str]]:
    """
    Union the image streams the loaded logs recorded.

    Combined logs need not carry the same cameras, and a selector that only
    listed the primary's would hide a stream the second log was combined in for.

    Args:
        manifest: Dataset manifest.
        stems: Loaded log stems, primary first.

    Returns:
        De-duplicated ``{"id", "label"}`` entries in first-seen order.
    """
    merged: List[Dict[str, str]] = []
    seen = set()
    for stem in stems:
        for stream in manifest.image_streams(stem):
            if stream["id"] in seen:
                continue
            seen.add(stream["id"])
            merged.append({"id": stream["id"], "label": stream["label"]})
    return merged


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
        streams = (
            _merged_streams(manifest, get_log_stems(session_id)) if manifest else []
        )

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
        stems = get_log_stems(session_id)
        if manifest is None or not stems:
            return {"panel_style": HIDDEN, "splitter_style": HIDDEN}

        # Any loaded log with a sidecar is reason enough to keep the dock: the
        # panels below draw whichever logs recorded the frame in view.
        has_content = any(manifest.has_image(stem) for stem in stems) or bool(
            manifest.curve_plots() and any(manifest.has_curve(stem) for stem in stems)
        )
        # Clearing `display` lets the stylesheet's flex layout take over again.
        style = {} if has_content else HIDDEN
        return {"panel_style": style, "splitter_style": style}

    @app.callback(
        output={
            "children": Output("camera-video-grid", "children"),
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
        Build one video element per log carrying the selected stream.

        A log gets an element for the whole load, not a turn on a shared one, so
        two logs that recorded the same frame can both be on screen at once. The
        source is therefore fixed per element and never swapped.

        Args:
            stream_id (str): Selected camera stream identifier
            unused_file_loaded (int): File load trigger count, used only to
                force a refresh when the stream id is unchanged across logs
            session_id (str): Session identifier

        Returns:
            dict: The grid's video elements and the descriptor the seek callback
            reads, or an empty grid and None when no loaded log has a matching
            stream
        """
        empty: Dict[str, Any] = {"children": [], "config": None}
        if not stream_id:
            return empty

        manifest = get_manifest(session_id)
        if manifest is None:
            return empty

        cells = []
        logs = []
        for stem in get_log_stems(session_id):
            streams = manifest.image_streams(stem)
            selected = next((s for s in streams if s["id"] == stream_id), None)
            if selected is None:
                # This log recorded no such stream, so it gets no cell at all
                # rather than a black box beside the logs that did.
                continue

            positions = get_frame_positions(session_id, stem)
            if not positions:
                continue

            cells.append(
                html.Div(
                    [
                        html.Video(
                            # The load counter is appended as a cache-busting
                            # query string: two different logs can share the
                            # same session id and stream id (both named
                            # "image"), and a browser never reloads a <video
                            # src> that comes out identical to what it already
                            # has loaded.
                            src=(
                                f"/api/camera/{session_id}/{stem}/{stream_id}"
                                f"?v={unused_file_loaded}"
                            ),
                            # Playback is driven entirely by the frame slider,
                            # so the element never plays on its own: no
                            # controls, no autoplay, muted so browsers never
                            # block the load.
                            controls=False,
                            autoPlay=False,
                            muted=True,
                            preload="auto",
                            className="sv-video",
                            # How the clientside seek finds this log's config
                            # without pattern-matching ids.
                            **{"data-stem": stem},
                        ),
                        html.Span(stem, className="sv-video-label"),
                    ],
                    className="sv-video-cell",
                )
            )

            # Both counts are measured, never declared. A null video count means
            # the probe failed, and the clientside callback leaves the video
            # alone rather than guessing at a position.
            logs.append(
                {
                    "stem": stem,
                    "video_frames": image_stream_frame_count(selected.get("file", "")),
                    "local_total": len(positions),
                    "runs": _stem_runs(positions),
                }
            )

        if not logs:
            return empty

        return {
            "children": cells,
            "config": {
                "logs": logs,
                "offset": float((manifest.image or {}).get("time_offset", 0.0)),
            },
        }

    # Seek every log's video to the current frame, and hide the ones whose log
    # recorded nothing there. Kept clientside so scrubbing costs no server round
    # trip -- the browser already has the decoded streams.
    app.clientside_callback(
        """
        function(frame_index, config) {
            const no_update = window.dash_clientside.no_update;
            const logs = (config || {}).logs;
            if (!Array.isArray(logs) || logs.length === 0) {
                return no_update;
            }
            const offset = (config || {}).offset || 0;
            const index = frame_index || 0;

            // Recording and log cover the same stretch of time, so the fraction
            // of the way through the log is the fraction of the way through the
            // video. Mapping count to count rather than second to second means
            // a camera that ran at a different rate than the data still lands
            // on the nearest real frame instead of somewhere between two.
            const computeTarget = function(video, target) {
                const duration = video.duration;
                if (!isFinite(duration) || duration <= 0) {
                    return null;
                }
                const videoFrames = target.video_frames || 0;
                const dataFrames = target.local_total || 0;
                // Nothing to map between: the probe could not read the file.
                // Leave the video where it is rather than guessing.
                if (videoFrames < 1 || dataFrames < 1) {
                    return null;
                }
                const span = dataFrames > 1 ? dataFrames - 1 : 1;
                const ratio = Math.min(1, Math.max(0, target.local / span));
                const k = Math.round(ratio * (videoFrames - 1));
                // Aim at the middle of that frame: landing exactly on a
                // boundary can round onto the neighbouring frame.
                return (k + 0.5) * duration / videoFrames;
            };

            const seek = function(video) {
                // Read at fire time rather than captured, so a listener left
                // pending by an earlier frame still seeks to the latest
                // position.
                const target = video.svSeekTarget;
                if (!target) {
                    return;
                }
                const time = computeTarget(video, target);
                if (time === null) {
                    return;
                }
                try {
                    video.currentTime = Math.max(0, time + offset);
                } catch (err) {
                    /* Element not seekable yet; the loadedmetadata handler
                       below retries once metadata arrives. */
                }
            };

            const apply = function() {
                const videos = document.querySelectorAll(
                    '#camera-video-grid video[data-stem]');
                let ack = null;
                videos.forEach(function (video) {
                    const stem = video.getAttribute('data-stem');
                    const entry = logs.find(function (l) {
                        return l.stem === stem;
                    });
                    const cell = video.closest('.sv-video-cell') || video;

                    const run = entry && (entry.runs || []).find(function (r) {
                        return index >= r.start && index < r.start + r.count;
                    });
                    // This log recorded nothing at this position. Hiding the
                    // cell leaves the logs that did with the whole grid, rather
                    // than showing another log's footage as if it were this
                    // one's.
                    if (!run) {
                        cell.style.display = 'none';
                        return;
                    }
                    cell.style.display = '';

                    video.svSeekTarget = {
                        local: run.local_start + (index - run.start),
                        local_total: entry.local_total,
                        video_frames: entry.video_frames
                    };

                    if (video.readyState >= 1) {
                        seek(video);
                        if (ack === null) {
                            ack = video.currentTime;
                        }
                    } else {
                        // Deferred until metadata has landed, because the
                        // mapping needs the element's own duration to turn a
                        // frame number into a time.
                        video.addEventListener('loadedmetadata', function () {
                            seek(video);
                        }, { once: true });
                    }
                });
                return { videos: videos.length, ack: ack };
            };

            const result = apply();
            // A fresh config arrives with the grid it describes, and on the
            // very first render the elements may not be in the DOM yet. Retry
            // once on the next frame rather than leaving every video unseeked
            // until the slider next moves.
            if (result.videos === 0) {
                window.requestAnimationFrame(apply);
                return no_update;
            }

            return result.ack;
        }
        """,
        Output("camera-seek-ack", "data"),
        Input("slider-frame", "value"),
        Input("camera-config", "data"),
        prevent_initial_call=True,
    )
