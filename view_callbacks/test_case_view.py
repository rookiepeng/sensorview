"""SensorView Test Case View Callbacks

Callback functions for test case selection and configuration including case loading,
file validation, UI controls, modal management, and configuration persistence.

Usage:
    from view_callbacks.test_case_view import get_test_case_view_callbacks
    get_test_case_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

import json
import os

import pandas as pd
import numpy as np

import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from app_config import (
    DROPDOWN_OPTIONS_ALL,
    DROPDOWN_VALUES_ALL,
    DROPDOWN_VALUES_ALL_STATE,
)
from app_config import DROPDOWN_OPTIONS_CAT, DROPDOWN_VALUES_CAT
from app_config import DROPDOWN_OPTIONS_CAT_COLOR, DROPDOWN_VALUES_CAT_COLOR
from app_config import DROPDOWN_OPTIONS_3D_XYZ, DROPDOWN_OPTIONS_3D_XYZ_REF
from app_config import DROPDOWN_VALUES_3D_XYZ, DROPDOWN_VALUES_3D_XYZ_REF
from app_config import REFERENCE_POSE_ORDER
from app_config import background_callback_manager
from app_config import CACHE_KEYS, KEY_TYPES, THEME

from dataio.frames import build_frame_index
from dataio.manifest import Manifest, ManifestError
from dataio.radar_store import frame_ids_by_file

from frame_sources import (
    build_frame_owner_sets,
    cache_log_info,
    cache_manifest,
    get_reference_mapping,
)

from layouts.layout_constants import HIDE_LOADING, SHOW_LOADING

from utils import cache_set, cache_get
from utils import load_data


def get_test_case_view_callbacks(app: dash.Dash) -> None:
    """
    Register the callback functions for the test case selection view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    def _extract_keys_by_type(config: dict) -> tuple[list, list]:
        """Extract numerical and categorical keys from config."""
        num_keys = []
        cat_keys = []

        for item in config["keys"]:
            key_type = config["keys"][item].get("type", KEY_TYPES["NUM"])
            if key_type == KEY_TYPES["NUM"]:
                num_keys.append(item)
            else:
                cat_keys.append(item)

        return num_keys, cat_keys

    def _create_dropdown_options(
        config: dict, keys: list, target_length: int, include_none: bool = False
    ) -> list:
        """Create dropdown options from config keys with correct length."""
        base_options = [
            {"label": config["keys"][item].get("description", item), "value": item}
            for item in keys
        ]

        if include_none:
            base_options.insert(0, {"label": "None", "value": "None"})

        return [base_options] * target_length

    def _get_default_values(
        keys: list,
        length: int,
        config: dict | None = None,
        config_keys: list | None = None,
    ) -> list:
        """Get default values for dropdowns based on available keys."""
        if not keys:
            return [None] * length

        # Use round-robin assignment for default values
        default_values = [keys[x % len(keys)] for x in range(length)]

        # Override with config values if provided. A manifest choice the loaded
        # log has no column for is ignored, so the round-robin default stands.
        if config and config_keys:
            for i, config_key in enumerate(config_keys):
                if i < len(default_values) and config.get(config_key) in keys:
                    default_values[i] = config[config_key]

        return default_values

    def _reference_pickers(
        config: dict, num_keys: list, reference: dict | None
    ) -> tuple[list, list, dict, str]:
        """
        Build the options and values for the six reference pickers.

        Args:
            config: Flat config projected from the manifest.
            num_keys: Numerical table columns the loaded log actually has.
            reference: Sidecar description from
                :func:`frame_sources.get_reference_mapping`, or None.

        Returns:
            ``(options, values, pose_row_style, note)`` -- one options list and
            one value per picker, the style hiding or showing the orientation
            row, and the label naming where the columns come from.
        """
        none_option = {"label": "None", "value": "None"}
        count = len(DROPDOWN_OPTIONS_3D_XYZ_REF)

        if reference is not None:
            # A sidecar carries the reference outright, so the pickers map its
            # columns; the table's own ref columns are irrelevant to it.
            columns = [{"label": name, "value": name} for name in reference["columns"]]
            options = [[none_option] + columns] * count
            mapping = reference["mapping"]
            values = [mapping.get(field) or "None" for field in REFERENCE_POSE_ORDER]
            return options, values, {}, f"from {reference['file']}"

        options = _create_dropdown_options(config, num_keys, count, include_none=True)
        values = ["None"] * count
        for index, config_key in enumerate(("x_ref", "y_ref", "z_ref")):
            values[index] = config.get(config_key, "None")
        return options, values, {"display": "none"}, ""

    def _create_filter_components(
        data: pd.DataFrame, cat_keys: list, num_keys: list, keys_dict: dict
    ) -> tuple[list, list, list, list]:
        """Create dropdown and slider components for filtering."""
        cat_values = []
        num_values = []
        new_dropdown = []
        new_slider = []

        # Create categorical dropdowns
        for idx, d_item in enumerate(cat_keys):
            if d_item in data.columns:
                var_list = data[d_item].unique().tolist()
                value_list = var_list
            else:
                var_list = []
                value_list = []

            new_dropdown.append(
                html.Div(
                    [
                        dbc.Label(
                            keys_dict[d_item]["description"],
                            className="mb-1 fw-bold",
                            style={"fontSize": "0.85rem"},
                        ),
                        html.Div(
                            dcc.Dropdown(
                                id={"type": "filter-dropdown", "index": idx},
                                options=[{"label": i, "value": i} for i in var_list],
                                value=value_list,
                                multi=True,
                            ),
                            className=f"{THEME} mb-0",
                        ),
                    ],
                    className="mb-3",
                )
            )
            cat_values.append(value_list)

        # Create numerical sliders
        for idx, item in enumerate(num_keys):
            if item in data.columns and data[item].notna().any():
                var_min = np.floor(np.nanmin(data[item])).tolist()
                var_max = np.ceil(np.nanmax(data[item])).tolist()
            else:
                var_min = var_max = 0

            new_slider.append(
                html.Div(
                    [
                        dbc.Label(
                            keys_dict[item]["description"],
                            className="mb-1 fw-bold",
                            style={"fontSize": "0.85rem"},
                        ),
                        html.Div(
                            dcc.RangeSlider(
                                id={"type": "filter-slider", "index": idx},
                                min=var_min,
                                max=var_max,
                                marks=None,
                                step=(
                                    round((var_max - var_min) / 100, 3)
                                    if var_max != var_min
                                    else 1
                                ),
                                value=[var_min, var_max],
                                tooltip={"always_visible": False},
                                className="px-0 py-0",
                            ),
                            className="mt-1",
                        ),
                    ],
                    className="mb-3",
                )
            )
            num_values.append([var_min, var_max])

        return new_dropdown, new_slider, cat_values, num_values

    def _frame_owners(
        manifest: Manifest, add_file_value: list, file: str
    ) -> dict[str, list[str]]:
        """
        Map each frame id to every log that recorded it.

        Combining logs concatenates their rows, so a frame id is the only thing
        left tying a slider position back to the log whose sidecars hold its
        cloud, pose, curves, and video. Logs are free to share ids, and an id
        two of them claim collects both stems rather than resolving to one: the
        camera and curve panels draw a subplot per log, and only the views with
        room for a single answer fall back to the primary.

        Args:
            manifest: Dataset manifest.
            add_file_value: Additional combined files, as the picker emits them.
            file: Primary selected file.

        Returns:
            ``{str(frame_id): [stem, ...]}`` in :func:`resolve_paths` order, so
            the primary log comes last. Keyed on the string form because the ids
            come back from Polars as Python scalars but are compared against
            NumPy ones derived from the loaded table.
        """
        owners: dict[str, list[str]] = {}
        for path, frame_ids in frame_ids_by_file(
            add_file_value, file, manifest.frame_key
        ):
            stem = manifest.stem_of(os.path.basename(path))
            for frame_id in frame_ids:
                owners.setdefault(str(frame_id), []).append(stem)
        return owners

    def _setup_data_cache(
        data: pd.DataFrame,
        config: dict,
        session_id: str,
        stem: str,
        time_scale: float = 1.0,
        frame_owners: dict[str, list[str]] | None = None,
    ) -> np.ndarray:
        """Setup data caching for frames and visibility."""
        # The frame index is derived from the data itself, never declared in the
        # manifest, so it can never drift out of sync with the log. Only the
        # *unit* of those timestamps comes from the manifest.
        frame_list, timestamps, _ = build_frame_index(
            data, config["slider"], time_scale=time_scale
        )
        cache_set(frame_list, session_id, CACHE_KEYS["frame_list"])
        # Which logs each slider position belongs to, so per-frame sidecars
        # resolve against the logs that actually recorded that frame.
        owner_sets, frame_stems = build_frame_owner_sets(frame_list, frame_owners, stem)
        cache_log_info(session_id, stem, timestamps, frame_stems, owner_sets)

        # Create and cache visibility table
        visible_table = pd.DataFrame({"_IDS_": data.index, "_VIS_": "visible"})
        cache_set(visible_table, session_id, CACHE_KEYS["visible_table"])

        # Cache grouped frame data
        frame_group = data.groupby(config["slider"])
        for frame_idx, frame_data in frame_group:
            cache_set(frame_data, session_id, CACHE_KEYS["frame_data"], str(frame_idx))

        return frame_list

    @app.callback(
        background=True,
        output={
            "key_dict": Output("key-dict", "data"),
            "file_load_trigger": Output("file-loaded-trigger", "data"),
            "stored_file": Output("local-file-selection", "data"),
            "frame_min": Output("slider-frame", "min"),
            "frame_max": Output("slider-frame", "max"),
            "dropdown_container": Output("dropdown-container", "children"),
            "slider_container": Output("slider-container", "children"),
            "dim_picker_opt": Output("dim-picker-parallel", "options"),
            "dim_picker_val": Output("dim-picker-parallel", "value"),
            "dp_opts_all": DROPDOWN_OPTIONS_ALL,
            "dp_vals_all": DROPDOWN_VALUES_ALL,
            "dp_opts_cat_color": DROPDOWN_OPTIONS_CAT_COLOR,
            "dp_vals_cat_color": DROPDOWN_VALUES_CAT_COLOR,
            "dp_opts_cat": DROPDOWN_OPTIONS_CAT,
            "dp_vals_cat": DROPDOWN_VALUES_CAT,
            "dp_opts_num": DROPDOWN_OPTIONS_3D_XYZ,
            "dp_vals_num": DROPDOWN_VALUES_3D_XYZ,
            "dp_opts_num_with_none": DROPDOWN_OPTIONS_3D_XYZ_REF,
            "dp_vals_num_with_none": DROPDOWN_VALUES_3D_XYZ_REF,
            "ref_pose_style": Output("ref-pose-controls", "style"),
            "ref_source_note": Output("ref-source-note", "children"),
            "error_modal_open": Output("error-modal", "is_open"),
            "error_message": Output("error-modal-message", "children"),
        },
        inputs={
            "file": Input("current-file", "data"),
            "add_file_value": Input("file-add", "value"),
        },
        state={
            "data_path": State("data-path", "value"),
            "case": State("test-case", "value"),
            "file_loaded": State("file-loaded-trigger", "data"),
            "session_id": State("session-id", "data"),
            "all_state": DROPDOWN_VALUES_ALL_STATE,
        },
        # The overlay is tied to the job's lifetime rather than being raised by
        # one callback and lowered by another: every way out of this function --
        # returning, PreventUpdate, or an unhandled exception -- ends the job,
        # and Dash lowers it then. Hiding it from inside the body meant an early
        # exit left it up over a live app with no way to dismiss it.
        running=[
            (Output("loading-view", "style"), SHOW_LOADING, HIDE_LOADING),
        ],
        manager=background_callback_manager,
        # Nothing is selected on the first render, so the initial call could only
        # ever bail out -- and now that the overlay follows the job, running it
        # would flash a full-screen spinner over the empty app while the worker
        # process spawns just to raise.
        prevent_initial_call=True,
    )
    def file_select_changed(
        file: str,
        add_file_value: list,
        data_path: str,
        case: str,
        file_loaded: int,
        session_id: str,
        all_state: list,
    ) -> dict:
        """
        Callback when a file selection is changed.

        Args:
            file (str): Selected file value
            add_file_value (list): List containing additional file values
            data_path (str): Path to data directory
            case (str): Test case value
            file_loaded (int): Number of times the file has been loaded
            session_id (str): Session identifier
            all_state (list): State of all dropdown components

        Returns:
            dict: Configuration data for all UI components

        Raises:
            PreventUpdate: If no file is selected or config doesn't exist
        """
        if not file:
            raise PreventUpdate

        # Initialize figure index
        cache_set(-1, session_id, CACHE_KEYS["figure_idx"])

        # Load the dataset manifest. A v1 info.json is upgraded in memory, so
        # both old and new datasets take this same path.
        case_dir = os.path.join(data_path, case)
        if not os.path.exists(os.path.join(case_dir, "info.json")):
            raise PreventUpdate

        try:
            manifest = Manifest.load(case_dir)
        except ManifestError as exc:
            raise PreventUpdate from exc

        cache_manifest(manifest, session_id)

        # Existing filter / 3D / 2D / stats callbacks read the flat v1 config
        # shape; project the manifest down so they keep working unchanged.
        config = manifest.legacy_config()
        cache_set(config, session_id, CACHE_KEYS["config"])

        # Extract keys by type
        num_keys, cat_keys = _extract_keys_by_type(config)
        all_keys = num_keys + cat_keys
        keys_dict = config["keys"]

        # Load and process data
        try:
            new_data = load_data(add_file_value, file)
        except Exception as exc:
            return {
                "key_dict": dash.no_update,
                "file_load_trigger": dash.no_update,
                "stored_file": dash.no_update,
                "frame_min": dash.no_update,
                "frame_max": dash.no_update,
                "dropdown_container": dash.no_update,
                "slider_container": dash.no_update,
                "dim_picker_opt": dash.no_update,
                "dim_picker_val": dash.no_update,
                "dp_opts_all": dash.no_update,
                "dp_vals_all": dash.no_update,
                "dp_opts_cat_color": dash.no_update,
                "dp_vals_cat_color": dash.no_update,
                "dp_opts_cat": dash.no_update,
                "dp_vals_cat": dash.no_update,
                "dp_opts_num": dash.no_update,
                "dp_vals_num": dash.no_update,
                "dp_opts_num_with_none": dash.no_update,
                "dp_vals_num_with_none": dash.no_update,
                "ref_pose_style": dash.no_update,
                "ref_source_note": dash.no_update,
                "error_modal_open": True,
                "error_message": str(exc),
            }
        # A manifest describes a whole case, so it can name columns a given log
        # never exported. Drop those now rather than offering a filter, an axis,
        # or a color scale that resolves to a missing column later.
        num_keys = [key for key in num_keys if key in new_data.columns]
        cat_keys = [key for key in cat_keys if key in new_data.columns]
        all_keys = num_keys + cat_keys

        # Sidecars are keyed on a log's basename. The primary log owns the
        # per-load choices -- which streams and curve sources the pickers offer
        # -- while per-frame data resolves against whichever log recorded that
        # frame, so combining logs keeps each one's cloud, pose, and curves.
        stem = manifest.stem_of(json.loads(file)["name"])
        frame_list = _setup_data_cache(
            new_data,
            config,
            session_id,
            stem,
            manifest.time_scale,
            _frame_owners(manifest, add_file_value, file),
        )

        # Create filter components
        new_dropdown, new_slider, cat_values, num_values = _create_filter_components(
            new_data, cat_keys, num_keys, keys_dict
        )

        # Save filter configuration to cache
        filter_kwargs = {
            "num_keys": num_keys,
            "cat_keys": cat_keys,
            "num_values": num_values,
            "cat_values": cat_values,
        }
        cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

        # Generate dropdown options and values
        options_all = _create_dropdown_options(
            config, all_keys, len(DROPDOWN_OPTIONS_ALL)
        )
        options_cat_color = _create_dropdown_options(
            config, cat_keys, len(DROPDOWN_OPTIONS_CAT_COLOR), include_none=True
        )
        options_cat = _create_dropdown_options(
            config, cat_keys, len(DROPDOWN_OPTIONS_CAT)
        )
        options_num = _create_dropdown_options(
            config, num_keys, len(DROPDOWN_OPTIONS_3D_XYZ)
        )
        (
            options_num_with_none,
            xyz_ref_all,
            ref_pose_style,
            ref_source_note,
        ) = _reference_pickers(config, num_keys, get_reference_mapping(manifest, stem))

        # Generate default values with state preservation
        values_all = _get_default_values(all_keys, len(DROPDOWN_VALUES_ALL))
        for idx, item in enumerate(all_state):
            if idx < len(values_all) and item in all_keys:
                values_all[idx] = item

        values_cat_color = ["None"] * len(DROPDOWN_VALUES_CAT_COLOR)
        values_cat = (
            [cat_keys[0]] * len(DROPDOWN_VALUES_CAT)
            if cat_keys
            else [None] * len(DROPDOWN_VALUES_CAT)
        )

        # 3D picker values with config defaults
        xyz_config_keys = ["slider", "x_3d", "y_3d", "z_3d"]
        xyz_all = _get_default_values(
            num_keys, len(DROPDOWN_VALUES_3D_XYZ), config, xyz_config_keys
        )

        # Dimension picker settings
        dim_picker_val = [cat_keys[0]] if cat_keys else [None]

        return {
            "key_dict": keys_dict,
            "file_load_trigger": file_loaded + 1,
            "stored_file": file,
            "frame_min": 0,
            "frame_max": len(frame_list) - 1,
            "dropdown_container": new_dropdown,
            "slider_container": new_slider,
            "dim_picker_opt": [{"label": ck, "value": ck} for ck in cat_keys],
            "dim_picker_val": dim_picker_val,
            "dp_opts_all": options_all,
            "dp_vals_all": values_all,
            "dp_opts_cat_color": options_cat_color,
            "dp_vals_cat_color": values_cat_color,
            "dp_opts_cat": options_cat,
            "dp_vals_cat": values_cat,
            "dp_opts_num": options_num,
            "dp_vals_num": xyz_all,
            "dp_opts_num_with_none": options_num_with_none,
            "dp_vals_num_with_none": xyz_ref_all,
            "ref_pose_style": ref_pose_style,
            "ref_source_note": ref_source_note,
            "error_modal_open": False,
            "error_message": "",
        }

    @app.callback(
        output={"slider_value": Output("slider-frame", "value")},
        inputs={
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
            "left_btn": Input("previous-button", "n_clicks"),
            "right_btn": Input("next-button", "n_clicks"),
            "interval": Input("interval-component", "n_intervals"),
        },
        state={
            "file": State("current-file", "data"),
            "slider_max": State("slider-frame", "max"),
            "slider_state": State("slider-frame", "value"),
            "session_id": State("session-id", "data"),
        },
    )
    def update_slider(
        unused_file_loaded: int,
        left_btn: int,
        right_btn: int,
        interval: int,
        file: str,
        slider_max: int,
        slider_state: int,
        session_id: str,
    ) -> dict:
        """
        Update the slider position based on user interactions.

        Args:
            unused_file_loaded (int): File load trigger count
            left_btn (int): Number of clicks on the previous button
            right_btn (int): Number of clicks on the next button
            interval (int): Number of intervals
            file (str): Selected file information
            slider_max (int): Maximum slider value
            slider_state (int): Current slider position
            session_id (str): Session identifier

        Returns:
            dict: Contains:
                - slider_value (int): New slider position

        Raises:
            PreventUpdate: If file is None or no valid trigger is detected
        """
        if file is None:
            raise PreventUpdate

        ctx = dash.callback_context
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "file-loaded-trigger":
            return {"slider_value": 0}

        if trigger_id == "previous-button":
            if left_btn == 0:
                raise PreventUpdate

            # previous button is clicked
            return {"slider_value": (slider_state - 1) % (slider_max + 1)}

        if trigger_id == "next-button":
            if right_btn == 0:
                raise PreventUpdate

            # next button is clicked
            return {"slider_value": (slider_state + 1) % (slider_max + 1)}

        if trigger_id == "interval-component":
            if interval == 0:
                raise PreventUpdate

            fig_idx = cache_get(session_id, CACHE_KEYS["figure_idx"])
            if fig_idx is not None:
                if slider_state > fig_idx:
                    return {"slider_value": dash.no_update}

                return {"slider_value": (slider_state + 1) % (slider_max + 1)}

            return {"slider_value": dash.no_update}

        # Default fallback - should not reach here normally
        raise PreventUpdate

    @app.callback(
        output={"state": Output("collapse-add", "is_open")},
        inputs={"click": Input("button-add", "n_clicks")},
        state={"open_state": State("collapse-add", "is_open")},
    )
    def add_data(click: int, open_state: bool) -> dict:
        """
        Toggle the state of the add data collapse element.

        The panel closes whether or not logs are picked: it floats over the
        canvas, so refusing to close it while a selection stands would leave no
        way to get it off the screen. What is combined stays visible instead
        through the trigger button, which is lit while the selection is not
        empty (see the clientside callback in ``app.py``).

        Args:
            click (int): Number of button clicks
            open_state (bool): Current state of the collapse element

        Returns:
            dict: Contains:
                - state (bool): New state of the collapse element

        Raises:
            PreventUpdate: If button has not been clicked
        """
        if click == 0:
            raise PreventUpdate

        return {"state": not open_state}

    # The six analysis enable switches are no longer reset here. They are driven
    # by the active dock tab (see the clientside gate in app.py), which already
    # re-fires on `file-loaded-trigger` -- so a newly loaded log refreshes the
    # view being looked at instead of switching it off.

    @app.callback(
        output={"is_open": Output("error-modal", "is_open")},
        inputs={"_close": Input("close-error-modal", "n_clicks")},
        prevent_initial_call=True,
    )
    def close_error_modal(_close: int) -> dict:
        """Close the error modal when the user clicks the Close button."""
        return {"is_open": False}
