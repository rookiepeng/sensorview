"""SensorView 3D Scatter View Interactive Callbacks

Interactive callbacks for 3D scatter plot view handling real-time user interactions,
UI state management, and synchronous visualization updates.

Features: UI controls, click-to-hide, theming, filters, exports (HTML/PNG/CSV),
and figure regeneration.

Usage:
    from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks
    get_scatter_3d_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

from typing import List, Tuple
import json
import os
import datetime

import dash
from dash.dcc import send_file  # pyright: ignore[reportPrivateImportUsage]
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
import plotly.io as pio
import plotly.graph_objs as go

from settings import CACHE_KEYS, KEY_TYPES

from utils import clamp_frame_index
from utils import filter_all
from utils import cache_set, cache_get
from utils import load_data

from dataio.manifest import log_stem

from frame_sources import cache_manifest, get_log_stem, get_manifest

from layouts.layout_constants import HIDE_LOADING, SHOW_LOADING

from process_frame import process_overlay_frame
from process_frame import process_single_frame


def get_scatter_3d_view_callbacks(app: dash.Dash) -> None:
    """
    Register interactive callbacks for 3D scatter plot view.

    Sets up UI interactions, real-time updates, user controls, and export functionality.
    Includes configuration panels, slider/overlay changes, theming, size variation,
    click-to-hide, figure regeneration, and export operations.

    Args:
        app: Dash application instance with required layout components.

    Returns:
        None

    Note:
        Call after layout definition but before app.run_server().
    """

    @app.callback(
        output={
            "is_open": Output("3d-config-collapse", "is_open"),
        },
        inputs={
            "n_clicks": Input("3d-config-more-button", "n_clicks"),
        },
        state={
            "is_open": State("3d-config-collapse", "is_open"),
        },
    )
    def toggle_3d_config_collapse(n_clicks: int, is_open: bool) -> dict:
        """
        Toggle the visibility of the 3D configuration collapse panel.

        Args:
            n_clicks: Number of times the more button has been clicked.
            is_open: Current state of the collapse panel.

        Returns:
            Dictionary with updated collapse panel state.

        Raises:
            PreventUpdate: If button has not been clicked.
        """
        if n_clicks == 0:
            raise PreventUpdate

        return {"is_open": not is_open}

    # Collapsing the filter rail is handled clientside (assets/workbench.js).
    # It changes nothing the server knows about, so a round trip per click would
    # only add latency to a purely visual change.

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "unused_remote_trigger": Input("trigger-remote-figure", "data"),
            "overlay_enable": Input("overlay-switch", "value"),
        },
        state={
            "slider_arg": State("slider-frame", "value"),
            "ispaused": State("interval-component", "disabled"),
            "decay": State("decay-slider", "value"),
            "cat_values": State({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": State({"type": "filter-slider", "index": ALL}, "value"),
            "visible_list": State("visible-picker", "value"),
            "colormap": State("colormap-3d", "value"),
            "c_key": State("c-picker-3d", "value"),
            "size_vary": State("size-vary-switch", "value"),
            "darkmode": State("darkmode-switch", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        prevent_initial_call=True,
    )
    def server_side_figure_update_callback(
        # Input parameters (ordered by input definition)
        unused_remote_trigger: int,
        overlay_enable: list,
        # Animation state parameters
        slider_arg: int,
        ispaused: bool,
        decay: int,
        # Filter state parameters
        cat_values: List[List[str]],
        num_values: List[Tuple[float, float]],
        visible_list: list,
        # Visual state parameters
        colormap: str,
        c_key: str,
        size_vary: str,
        darkmode: list,
        # Common state parameters
        session_id: str,
        file: str,
        file_list: list,
    ) -> dict:
        """
        Handle server-side figure updates for slider and overlay changes.

        Processes frames in single or overlay mode based on settings, optimized
        for real-time animation playback.

        Args:
            unused_remote_trigger: Remote trigger count (unused).
            overlay_enable: Overlay mode state (empty=disabled).
            slider_arg: Current frame index.
            ispaused: Animation pause state.
            decay: Past frames to show in overlay mode.
            cat_values: List of lists containing categorical filter values.
            num_values: List of (min, max) tuples for numerical filter ranges.
            visible_list: List of visible data elements.
            colormap: Selected colormap name.
            c_key: Color mapping column name.
            size_vary: Size variation enable state.
            darkmode: Dark mode state (empty=disabled).
            session_id: Session identifier.
            file: Current file path (JSON string).
            file_list: All loaded file paths.

        Returns:
            Dictionary with updated scatter plot figure including theme and visual settings.

        Raises:
            PreventUpdate: If configuration is unavailable.
        """
        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None:
            raise PreventUpdate

        if overlay_enable:
            fig = process_overlay_frame(
                slider_arg,
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                size_vary,
                session_id,
                file,
                file_list,
            )
        else:
            fig = process_single_frame(
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                size_vary,
                decay,
                session_id,
                slider_arg,
                ispaused,
            )

        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {"scatter3d": fig}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "colormap": Input("colormap-3d", "value"),
        },
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def colormap_change_callback(colormap: str, fig: dict) -> dict:
        """
        Update the colormap of the 3D scatter plot.

        Args:
            colormap: Name of the selected colormap.
            fig: Current figure dictionary.

        Returns:
            Dictionary with updated figure containing new colormap.
        """
        for trace in fig["data"]:
            # Empty-frame placeholder traces have no "marker" key; skip them
            if "marker" in trace:
                trace["marker"]["colorscale"] = colormap

        return {"scatter3d": fig}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "darkmode": Input("darkmode-switch", "value"),
        },
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def darkmode_change_callback(darkmode: list, fig: dict) -> dict:
        """
        Toggle dark mode for the 3D scatter plot.

        Args:
            darkmode: Dark mode enable state (non-empty = enabled).
            fig: Current figure dictionary.

        Returns:
            Dictionary with updated figure containing new theme.
        """
        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {"scatter3d": fig}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "size_vary": Input("size-vary-switch", "value"),
        },
        state={
            "fig": State("scatter3d", "figure"),
            "session_id": State("session-id", "data"),
            "c_key": State("c-picker-3d", "value"),
        },
        prevent_initial_call=True,
    )
    def size_vary_callback(
        size_vary: list, fig: dict, session_id: str, c_key: str
    ) -> dict:
        """
        Toggle point size variation for categorical data visualization.

        Applies different sizes to each category when enabled and color key is categorical.

        Args:
            size_vary: Enable state (empty=disabled).
            fig: Current figure data and layout.
            session_id: Session identifier.
            c_key: Color mapping column name.

        Returns:
            Dictionary with figure containing modified marker sizes.

        Raises:
            PreventUpdate: If configuration is unavailable.
        """

        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None or "keys" not in config:
            raise PreventUpdate
        keys_dict = config["keys"]

        ctype = keys_dict[c_key].get("type", KEY_TYPES["NUM"])

        data_length = len(fig["data"])

        if size_vary and ctype == KEY_TYPES["CAT"]:
            for i in range(0, data_length):
                size_offset = data_length - 1 - i
                # Empty-frame placeholder traces may have no "marker" key
                if "marker" in fig["data"][i]:
                    fig["data"][i]["marker"]["size"] = 3 + size_offset
        else:
            for i in range(0, data_length):
                if "marker" in fig["data"][i]:
                    fig["data"][i]["marker"]["size"] = 3

        return {"scatter3d": fig}

    @app.callback(
        output={
            "trigger": Output("visible-table-change-trigger", "data"),
        },
        inputs={
            "click_data": Input("scatter3d", "clickData"),
        },
        state={
            "trigger_input": State("visible-table-change-trigger", "data"),
            "click_hide": State("click-hide-switch", "value"),
            "session_id": State("session-id", "data"),
        },
        prevent_initial_call=True,
    )
    def visible_table_change_callback(
        click_data: dict,
        trigger_input: int,
        click_hide: list,
        session_id: str,
    ) -> dict:
        """
        Handle visibility changes from click interactions on data points.

        Args:
            click_data: Data from click event containing point information.
            trigger_input: Current trigger state value.
            click_hide: Click-to-hide feature state (empty=disabled).
            session_id: Session identifier.

        Returns:
            Dictionary with updated trigger value.

        Raises:
            PreventUpdate: If click-to-hide is not enabled or click data is invalid.
        """
        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
        if click_hide and visible_table is not None and click_data is not None:
            point_id = (
                click_data.get("points", [{}])[0].get("id")
                if click_data.get("points")
                else None
            )
            if (
                point_id is not None
                and "_VIS_" in visible_table
                and point_id in visible_table["_VIS_"]
            ):
                if visible_table["_VIS_"][point_id] == "visible":
                    visible_table.at[point_id, "_VIS_"] = "hidden"
                else:
                    visible_table.at[point_id, "_VIS_"] = "visible"

                cache_set(visible_table, session_id, CACHE_KEYS["visible_table"])

                return {"trigger": trigger_input + 1}

        raise PreventUpdate

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
            "trigger": Output("background-trigger", "data"),
            "local_buffer_idx": Output(
                "local-buffer-index", "data", allow_duplicate=True
            ),
            "buffer_color": Output("buffer", "color", allow_duplicate=True),
            "buffer_value": Output("buffer", "value", allow_duplicate=True),
            "buffer_tooltip": Output(
                "buffer-tooltip", "children", allow_duplicate=True
            ),
        },
        inputs={
            "cat_values": Input({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": Input({"type": "filter-slider", "index": ALL}, "value"),
            "visible_list": Input("visible-picker", "value"),
            "slider_picker_3d": Input("slider-picker-3d", "value"),
            "x_picker_3d": Input("x-picker-3d", "value"),
            "y_picker_3d": Input("y-picker-3d", "value"),
            "z_picker_3d": Input("z-picker-3d", "value"),
            "x_ref_picker_3d": Input("x-ref-picker-3d", "value"),
            "y_ref_picker_3d": Input("y-ref-picker-3d", "value"),
            "z_ref_picker_3d": Input("z-ref-picker-3d", "value"),
            "yaw_ref_picker_3d": Input("yaw-ref-picker-3d", "value"),
            "pitch_ref_picker_3d": Input("pitch-ref-picker-3d", "value"),
            "roll_ref_picker_3d": Input("roll-ref-picker-3d", "value"),
            "frame_ref_picker_3d": Input("frame-ref-picker-3d", "value"),
            "unused_vistable_trigger": Input("visible-table-change-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "unused_right_hide_trigger": Input("right-hide-trigger", "data"),
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
            "c_key": Input("c-picker-3d", "value"),
        },
        state={
            "slider_arg": State("slider-frame", "value"),
            "ispaused": State("interval-component", "disabled"),
            "decay": State("decay-slider", "value"),
            "colormap": State("colormap-3d", "value"),
            "overlay_enable": State("overlay-switch", "value"),
            "size_vary": State("size-vary-switch", "value"),
            "darkmode": State("darkmode-switch", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
            "trigger_val": State("background-trigger", "data"),
            "data_path": State("data-path", "value"),
            "case": State("test-case", "value"),
        },
        # Filtering re-reads the whole log, so on a large one this callback is
        # the app's longest synchronous pause -- long enough for the rail to
        # still look live and invite a second adjustment, which would queue
        # another full pass behind this one. The overlay covers the viewport
        # for exactly as long as the callback runs, which puts every control
        # out of reach until the figure it is about to return is on screen.
        #
        # Tied to the callback's lifetime rather than raised and lowered by
        # hand: PreventUpdate and unhandled exceptions both end it, and both
        # are reachable here, so hiding it from inside the body would strand
        # it over a working app.
        running=[
            (Output("update-loading-view", "style"), SHOW_LOADING, HIDE_LOADING),
        ],
        prevent_initial_call=True,
    )
    def regenerate_figure_callback(
        # Filter inputs
        cat_values: List[List[str]],
        num_values: List[Tuple[float, float]],
        visible_list: list,
        # Picker 3D inputs
        slider_picker_3d: str,
        x_picker_3d: str,
        y_picker_3d: str,
        z_picker_3d: str,
        x_ref_picker_3d: str,
        y_ref_picker_3d: str,
        z_ref_picker_3d: str,
        yaw_ref_picker_3d: str,
        pitch_ref_picker_3d: str,
        roll_ref_picker_3d: str,
        frame_ref_picker_3d: str,
        # Trigger inputs
        unused_vistable_trigger: int,
        unused_left_hide_trigger: int,
        unused_right_hide_trigger: int,
        unused_file_loaded: int,
        # Other inputs
        c_key: str,
        # Animation state
        ispaused: bool,
        slider_arg: int,
        decay: int,
        # Visual state
        overlay_enable: list,
        colormap: str,
        # Common state
        size_vary: str,
        darkmode: list,
        session_id: str,
        file: str,
        file_list: list,
        # Additional state
        trigger_val: int,
        data_path: str,
        case: str,
    ) -> dict:
        """
        Complete 3D scatter plot figure regeneration for major configuration changes.

        Handles axis selections, filters, visibility updates, and triggers background
        processing for animation buffers. Manages immediate figure generation and
        configuration persistence.

        Args:
            cat_values: List of lists containing categorical filter selections.
            num_values: List of (min, max) tuples for numerical filter ranges.
            visible_list: List of visible data elements.
            slider_picker_3d: Frame/time slider column name.
            x_picker_3d: X-axis column name.
            y_picker_3d: Y-axis column name.
            z_picker_3d: Z-axis column name.
            x_ref_picker_3d: Reference x column name (sidecar only).
            y_ref_picker_3d: Reference y column name (sidecar only).
            z_ref_picker_3d: Reference z column name (sidecar only).
            yaw_ref_picker_3d: Reference yaw column name (sidecar only).
            pitch_ref_picker_3d: Reference pitch column name (sidecar only).
            roll_ref_picker_3d: Reference roll column name (sidecar only).
            frame_ref_picker_3d: Reference frame-id column name (sidecar only),
                the column its rows are paired with the table's frames on.
            unused_vistable_trigger: Visibility trigger (unused).
            unused_left_hide_trigger: Left panel trigger (unused).
            unused_right_hide_trigger: Right panel trigger (unused).
            unused_file_loaded: File loaded trigger (unused).
            c_key: Color mapping column name.
            ispaused: Animation pause state.
            slider_arg: Current frame position.
            decay: Historical frames in overlay mode.
            overlay_enable: Overlay state (empty=disabled).
            colormap: Selected colormap name.
            size_vary: Size variation enable state.
            darkmode: Dark theme state (empty=disabled).
            session_id: Session identifier.
            file: Primary file path (JSON string).
            file_list: List of all loaded file paths.
            trigger_val: Background task trigger counter.
            data_path: Configuration file base path.
            case: Test case/project name.

        Returns:
            Dictionary with updated figure, incremented trigger, and reset buffer index.

        Raises:
            PreventUpdate: If configuration is unavailable.

        Side Effects:
            Updates cache, persists config to JSON, triggers background processing.
        """
        # invoke task
        cache_set(-1, session_id, CACHE_KEYS["figure_idx"])

        # save filter key word arguments to Redis
        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            filter_kwargs = {}
        filter_kwargs["num_values"] = num_values
        filter_kwargs["cat_values"] = cat_values
        cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

        if file not in file_list:
            file_list.append(file)

        # get config from Redis
        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None:
            raise PreventUpdate
        config["slider"] = slider_picker_3d
        config["x_3d"] = x_picker_3d
        config["y_3d"] = y_picker_3d
        config["z_3d"] = z_picker_3d

        # The reference pickers map the columns of this log's pose sidecar, and
        # exist only for a log that has one -- the panel hides them otherwise,
        # and there is nothing to write.
        manifest = get_manifest(session_id)
        stem = get_log_stem(session_id)
        maps_sidecar = manifest is not None and manifest.has_reference_pose(stem)

        if maps_sidecar:
            reference_columns = {
                "x": x_ref_picker_3d,
                "y": y_ref_picker_3d,
                "z": z_ref_picker_3d,
                "yaw": yaw_ref_picker_3d,
                "pitch": pitch_ref_picker_3d,
                "roll": roll_ref_picker_3d,
                # Which column pairs the sidecar's rows with the table's frames.
                # Wrong, and every lookup misses and the reference vanishes --
                # so it is picked here rather than left to the name-guessing
                # fallback, which a file calling it `t` or `sample_idx` defeats.
                "frame": frame_ref_picker_3d,
            }

        # Persist the axis selections back to the dataset. This goes through the
        # manifest rather than dumping `config` straight over info.json: config
        # is only the flat radar projection, so writing it verbatim would wipe
        # the cloud / curve / image blocks of a v2 manifest.
        if manifest is not None:
            manifest.update_table_view(config)
            if maps_sidecar:
                manifest.update_reference_columns(reference_columns)
                # The renderer reads the reference block off the cached config,
                # so it has to carry the mapping the manifest just took.
                config["reference"] = manifest.reference
            manifest.save()
            cache_manifest(manifest, session_id)

        cache_set(config, session_id, CACHE_KEYS["config"])

        if overlay_enable:
            fig = process_overlay_frame(
                slider_arg,
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                size_vary,
                session_id,
                file,
                file_list,
            )
        else:
            fig = process_single_frame(
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                size_vary,
                decay,
                session_id,
                slider_arg,
                ispaused,
            )

        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {
            "scatter3d": fig,
            "trigger": trigger_val + 1,
            "local_buffer_idx": -1,
            "buffer_color": "warning",
            "buffer_value": 0,
            "buffer_tooltip": "Restarting ...",
        }

    @app.callback(
        output={"filter_trigger": Output("filter-trigger", "data")},
        inputs={
            "unused_cat_values": Input(
                {"type": "filter-dropdown", "index": ALL}, "value"
            ),
            "unused_num_values": Input(
                {"type": "filter-slider", "index": ALL}, "value"
            ),
            "unused_visible_list": Input("visible-picker", "value"),
            "unused_vistable_trigger": Input("visible-table-change-trigger", "data"),
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
        },
        state={
            "trigger_idx": State("filter-trigger", "data"),
        },
    )
    def invoke_filter_trigger(
        unused_cat_values: list,
        unused_num_values: list,
        unused_visible_list: list,
        unused_vistable_trigger: int,
        unused_file_loaded: int,
        trigger_idx: int,
    ) -> dict:
        """
        Increment the filter trigger counter for filter change events.

        Args:
            unused_cat_values: Categorical filter values (unused).
            unused_num_values: Numerical filter values (unused).
            unused_visible_list: Visible elements list (unused).
            unused_vistable_trigger: Visibility table trigger (unused).
            unused_file_loaded: File loaded trigger (unused).
            trigger_idx: Current trigger value.

        Returns:
            Dictionary with incremented trigger value.
        """
        filter_trig = trigger_idx + 1

        return {"filter_trigger": filter_trig}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter3d-html", "n_clicks")},
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_3d_scatter_html(btn: int, fig: dict) -> dict:
        """
        Export current 3D scatter plot to interactive HTML file.

        Creates standalone HTML with full interactivity (zoom, rotation, hover).

        Args:
            btn: Button click count (must be > 0).
            fig: Current figure data and layout.

        Returns:
            Dictionary with download response for browser.

        Raises:
            PreventUpdate: If button not clicked.
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = "temp/" + timestamp + "_3dscatter.html"

        temp_fig = go.Figure(fig)
        temp_fig.write_html(file_name)

        return {"download": send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter3d-png", "n_clicks")},
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_3d_scatter_png(btn: int, fig: dict) -> dict:
        """
        Export current 3D scatter plot to high-resolution PNG image.

        Generates static PNG at 2x scale for high-quality output.

        Args:
            btn: Button click count (must be > 0).
            fig: Current figure data and layout.

        Returns:
            Dictionary with download response containing PNG file.

        Raises:
            PreventUpdate: If button not clicked.

        Note:
            Requires plotly kaleido for image export.
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = "temp/" + timestamp + "_3dscatter.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-data-all", "n_clicks")},
        state={
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        prevent_initial_call=True,
    )
    def export_all_frame_data(
        btn: int, session_id: str, visible_list: list, file: str, file_list: list
    ) -> dict:
        """
        Export filtered data from all frames to a Parquet file.

        Args:
            btn: Button click count (must be > 0).
            session_id: Session identifier.
            visible_list: List of visible elements for filtering.
            file: Current file path as JSON string.
            file_list: List of all file paths.

        Returns:
            Dictionary with download data for the Parquet file.

        Raises:
            PreventUpdate: If button not clicked or filter configuration unavailable.
        """
        if btn == 0:
            raise PreventUpdate

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            raise PreventUpdate
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        data = load_data(file_list, file)
        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list,
        )
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = (
            "temp/" + log_stem(json.loads(file)["name"]) + "_" + timestamp + ".parquet"
        )

        # Exported in the same format the app reads, so an export is a log the
        # app can open again -- the row index is an artifact of filtering, not
        # data, so it is dropped rather than written as a column.
        filtered_table.to_parquet(file_name, index=False)

        return {"download": send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-data-current", "n_clicks")},
        state={
            "slider_arg": State("slider-frame", "value"),
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
        },
        prevent_initial_call=True,
    )
    def export_current_frame_data(
        btn: int, slider_arg: int, session_id: str, visible_list: list, file: str
    ) -> dict:
        """
        Export filtered data from current frame to a Parquet file.

        Args:
            btn: Button click count (must be > 0).
            slider_arg: Current slider position/frame index.
            session_id: Session identifier.
            visible_list: List of visible elements for filtering.
            file: Current file path as JSON string.

        Returns:
            Dictionary with download data for the Parquet file.

        Raises:
            PreventUpdate: If button not clicked or required data unavailable.
        """
        if btn == 0:
            raise PreventUpdate

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            raise PreventUpdate
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
        frame_pos = clamp_frame_index(frame_list, slider_arg)
        if frame_pos is None:
            raise PreventUpdate
        data = cache_get(
            session_id, CACHE_KEYS["frame_data"], str(frame_list[frame_pos])
        )
        if data is None:
            raise PreventUpdate
        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list,
        )
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = (
            "temp/" + log_stem(json.loads(file)["name"]) + "_" + timestamp + ".parquet"
        )

        # Exported in the same format the app reads, so an export is a log the
        # app can open again -- the row index is an artifact of filtering, not
        # data, so it is dropped rather than written as a column.
        filtered_table.to_parquet(file_name, index=False)

        return {"download": send_file(file_name)}
