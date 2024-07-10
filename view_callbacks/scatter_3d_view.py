"""

    Copyright (C) 2019 - PRESENT  Zhengyu Peng
    E-mail: zpeng.me@gmail.com
    Website: https://zpeng.me

    `                      `
    -:.                  -#:
    -//:.              -###:
    -////:.          -#####:
    -/:.://:.      -###++##:
    ..   `://:-  -###+. :##:
           `:/+####+.   :##:
    .::::::::/+###.     :##:
    .////-----+##:    `:###:
     `-//:.   :##:  `:###/.
       `-//:. :##:`:###/.
         `-//:+######/.
           `-/+####/.
             `+##+.
              :##:
              :##:
              :##:
              :##:
              :##:
               .+:

"""

import json
import os
import datetime

import numpy as np

import dash
from dash import dcc
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
import plotly.io as pio
import plotly.graph_objs as go

from app_config import background_callback_manager
from app_config import CACHE_KEYS, KEY_TYPES

from utils import filter_all
from utils import cache_set, cache_get, cache_expire
from utils import load_data
from utils import load_data_list
from utils import load_image
from utils import prepare_figure_kwargs

from viz.viz import get_scatter3d
from viz.viz import get_animation_data
from viz.graph_data import get_scatter3d_data, get_ref_scatter3d_data
from viz.graph_data import get_hover_strings
from viz.graph_layout import get_scatter3d_layout


def process_single_frame(
    config,
    cat_values,
    num_values,
    colormap,
    visible_list,
    c_key,
    decay,
    session_id,
    file,
    frame_idx=0,
    load_hover=False,
):
    """
    Function to process a single frame of data and generate the 3D scatter plot figure.

    Parameters:
    - config (dict): The configuration dictionary.
    - cat_values (dict): The selected categorical values for filtering.
    - num_values (dict): The selected numerical values for filtering.
    - colormap (str): The selected colormap.
    - visible_list (list): The list of visible items.
    - c_key (str): The selected color key.
    - decay (int): The number of past frames to include in the figure.
    - session_id (str): The ID of the current session.
    - case (str): The selected case.
    - file (str): The selected file.
    - frame_idx (int): The index of the frame to process.
    - load_hover (bool): Whether to load hover strings or not.

    Returns:
    - dict: A dictionary containing the 3D scatter plot figure.

    Output Properties:
    - figure (dict): The 3D scatter plot figure.
    """
    keys_dict = config["keys"]

    opacity = np.linspace(1, 0.2, decay + 1)

    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs["cat_keys"]
    num_keys = filter_kwargs["num_keys"]

    # get visibility table from Redis
    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

    # get frame list from Redis
    frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

    # prepare figure key word arguments
    fig_kwargs = prepare_figure_kwargs(
        config,
        frame_list,
        c_key,
        num_keys,
        num_values,
        frame_idx,
    )

    file = json.loads(file)
    img_path = os.path.join(file["path"], file["name"][0:-4], str(frame_idx) + ".jpg")

    # encode image frame
    fig_kwargs["image"] = load_image(img_path)

    # get a single frame data from Redis
    data = cache_get(session_id, CACHE_KEYS["frame_data"], str(frame_list[frame_idx]))

    filterd_frame = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )
    fig = get_scatter3d_data(filterd_frame, **fig_kwargs)
    c_type = keys_dict[c_key].get("type", KEY_TYPES["NUM"])
    if load_hover:
        hover_list = get_hover_strings(
            filterd_frame, fig_kwargs["c_key"], c_type, keys_dict
        )

        if hover_list:
            for idx, hover_str in enumerate(hover_list):
                fig[idx]["text"] = hover_str
                fig[idx]["hovertemplate"] = "%{text}"

    if c_type == "numerical":
        if "marker" in fig[0]:
            fig[0]["marker"]["colorscale"] = colormap

    if decay > 0:
        for val in range(1, decay + 1):
            if (frame_idx - val) >= 0:
                # filter the data
                frame_temp = filter_all(
                    cache_get(
                        session_id,
                        CACHE_KEYS["frame_data"],
                        str(frame_list[frame_idx - val]),
                    ),
                    num_keys,
                    num_values,
                    cat_keys,
                    cat_values,
                    visible_table,
                    visible_list,
                )
                fig_kwargs["opacity"] = opacity[val]
                fig_kwargs["name"] = (
                    "Index: "
                    + str(frame_idx - val)
                    + " ("
                    + keys_dict[config["slider"]]["description"]
                    + ": "
                    + str(frame_list[frame_idx - val])
                    + ")"
                )
                new_fig = get_scatter3d_data(frame_temp, **fig_kwargs)
                if load_hover:
                    hover_list = get_hover_strings(
                        frame_temp, fig_kwargs["c_key"], c_type, keys_dict
                    )

                    if hover_list:
                        for idx, hover_str in enumerate(hover_list):
                            new_fig[idx]["text"] = hover_str
                            new_fig[idx]["hovertemplate"] = "%{text}"

                if c_type == "numerical":
                    if "marker" in new_fig[0]:
                        new_fig[0]["marker"]["colorscale"] = colormap

                fig = fig + new_fig

            else:
                break

    if fig_kwargs["x_ref"] is not None and fig_kwargs["y_ref"] is not None:
        fig_ref = [
            get_ref_scatter3d_data(
                data_frame=filterd_frame,
                x_key=fig_kwargs["x_ref"],
                y_key=fig_kwargs["y_ref"],
                z_key=None,
                name=fig_kwargs.get("ref_name", None),
            )
        ]
    else:
        fig_ref = []

    layout = get_scatter3d_layout(**fig_kwargs)

    fig = {"data": fig_ref + fig, "layout": layout}

    return fig


def process_overlay_frame(
    frame_idx,
    config,
    cat_values,
    num_values,
    colormap,
    visible_list,
    c_key,
    session_id,
    file,
    file_list,
    load_hover=False,
):
    """
    Function to process an overlay frame of data and generate the 3D scatter plot figure.

    Parameters:
    - frame_idx (int): The index of the frame to process.
    - config (dict): The configuration dictionary.
    - cat_values (dict): The selected categorical values for filtering.
    - num_values (dict): The selected numerical values for filtering.
    - colormap (str): The selected colormap.
    - visible_list (list): The list of visible items.
    - c_key (str): The selected color key.
    - session_id (str): The ID of the current session.
    - case (str): The selected case.
    - file (str): The selected file.
    - file_list (list): The list of selected files.
    - load_hover (bool): Whether to load hover strings or not.

    Returns:
    - dict: A dictionary containing the 3D scatter plot figure.

    Output Properties:
    - figure (dict): The 3D scatter plot figure.
    """
    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs["cat_keys"]
    num_keys = filter_kwargs["num_keys"]

    # get visibility table from Redis
    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

    # get frame list from Redis
    frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

    # prepare figure key word arguments
    fig_kwargs = prepare_figure_kwargs(
        config,
        frame_list,
        c_key,
        num_keys,
        num_values,
        frame_idx,
    )

    # overlay all the frames
    # get data from .feather file on the disk
    data = load_data(file, file_list)
    filterd_frame = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )
    fig_kwargs["image"] = None

    # generate the graph
    fig = get_scatter3d(filterd_frame, **fig_kwargs)

    keys_dict = config["keys"]
    c_type = keys_dict[c_key].get("type", KEY_TYPES["NUM"])

    if load_hover:
        hover_list = get_hover_strings(
            filterd_frame, fig_kwargs["c_key"], c_type, keys_dict
        )

        if hover_list:
            for idx, hover_str in enumerate(hover_list):
                fig["data"][idx]["text"] = hover_str
                fig["data"][idx]["hovertemplate"] = "%{text}"

    if c_type == "numerical":
        if "marker" in fig["data"][0]:
            fig["data"][0]["marker"]["colorscale"] = colormap

    return fig


def get_scatter_3d_view_callbacks(app):
    """
    Register the callback functions for the 3D view.

    Parameters:
    - app (Dash app): The Dash app.

    Returns:
    - None
    """

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "slider_arg": Input("slider-frame", "value"),
            "overlay_enable": Input("overlay-switch", "value"),
            "decay": Input("decay-slider", "value"),
            "unused_stop_click": Input("stop-button", "n_clicks"),
        },
        state={
            "ispaused": State("interval-component", "disabled"),
            "cat_values": State({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": State({"type": "filter-slider", "index": ALL}, "value"),
            "colormap": State("colormap-3d", "value"),
            "visible_list": State("visible-picker", "value"),
            "c_key": State("c-picker-3d", "value"),
            "darkmode": State("darkmode-switch", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        prevent_initial_call=True,
    )
    def slider_change_callback(
        slider_arg,
        cat_values,
        num_values,
        unused_stop_click,
        ispaused,
        colormap,
        visible_list,
        c_key,
        overlay_enable,
        decay,
        darkmode,
        session_id,
        file,
        file_list,
    ):
        """
        Callback function for the slider change event.

        Parameters:
        - slider_arg (int): The value of the slider.
        - cat_values (dict): The selected categorical values for filtering.
        - num_values (dict): The selected numerical values for filtering.
        - unused_stop_click (int): The number of times the stop button has been clicked.
        - ispaused (bool): Whether the animation is paused or not.
        - colormap (str): The selected colormap.
        - visible_list (list): The list of visible items.
        - c_key (str): The selected color key.
        - overlay_enable (bool): Whether overlay mode is enabled or not.
        - decay (int): The number of past frames to include in the figure.
        - darkmode (bool): Whether dark mode is enabled or not.
        - session_id (str): The ID of the current session.
        - file (str): The selected file.
        - file_list (list): The list of selected files.

        Returns:
        - dict: A dictionary containing the updated 3D scatter plot figure.

        Output Properties:
        - scatter3d (dict): The updated 3D scatter plot figure.
        """
        ctx = dash.callback_context
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "stop-button":
            ispaused = True

        config = cache_get(session_id, CACHE_KEYS["config"])
        keys_dict = config["keys"]
        c_type = keys_dict[c_key].get("type", KEY_TYPES["NUM"])

        if overlay_enable:
            fig = process_overlay_frame(
                slider_arg,
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                session_id,
                file,
                file_list,
                ispaused,
            )
        else:
            fig_idx = cache_get(session_id, CACHE_KEYS["figure_idx"])

            opacity = np.linspace(1, 0.2, decay + 1)

            # if slider value changed
            #   - if Redis `figure` buffer ready, return figure from Redis
            if fig_idx is not None:
                if slider_arg <= fig_idx:
                    fig = cache_get(session_id, CACHE_KEYS["figure"], str(slider_arg))
                    if ispaused:
                        hover_list = cache_get(
                            session_id, CACHE_KEYS["hover"], str(slider_arg)
                        )

                        if hover_list:
                            for idx, hover_str in enumerate(hover_list):
                                fig[idx]["text"] = hover_str
                                fig[idx]["hovertemplate"] = "%{text}"

                    if c_type == "numerical":
                        if "marker" in fig[0]:
                            fig[0]["marker"]["colorscale"] = colormap

                    if decay > 0:
                        for val in range(1, decay + 1):
                            if (slider_arg - val) >= 0:
                                new_fig = cache_get(
                                    session_id,
                                    CACHE_KEYS["figure"],
                                    str(slider_arg - val),
                                )
                                new_fig[0]["marker"]["opacity"] = opacity[val]
                                if ispaused:
                                    hover_list = cache_get(
                                        session_id,
                                        CACHE_KEYS["hover"],
                                        str(slider_arg - val),
                                    )

                                    if hover_list:
                                        for idx, hover_str in enumerate(hover_list):
                                            new_fig[idx]["text"] = hover_str
                                            new_fig[idx]["hovertemplate"] = "%{text}"

                                if c_type == "numerical":
                                    if "marker" in new_fig[0]:
                                        new_fig[0]["marker"]["colorscale"] = colormap

                                fig = fig + new_fig

                    fig_ref = cache_get(
                        session_id, CACHE_KEYS["figure_ref"], str(slider_arg)
                    )
                    layout = cache_get(
                        session_id, CACHE_KEYS["figure_layout"], str(slider_arg)
                    )

                    if darkmode:
                        layout["template"] = pio.templates["plotly_dark"]
                    else:
                        layout["template"] = pio.templates["plotly"]

                    return {"scatter3d": {"data": fig_ref + fig, "layout": layout}}
            fig = process_single_frame(
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                decay,
                session_id,
                file,
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
    def colormap_change_callback(colormap, fig):
        """
        Callback function for the colormap change event.

        Parameters:
        - colormap (str): The selected colormap.
        - fig (dict): The current 3D scatter plot figure.

        Returns:
        - dict: A dictionary containing the updated 3D scatter plot figure.

        Output Properties:
        - scatter3d (dict): The updated 3D scatter plot figure.
        """
        for idx in range(0, len(fig["data"])):
            fig["data"][idx]["marker"]["colorscale"] = colormap

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
    def darkmode_change_callback(darkmode, fig):
        """
        Callback function for the dark mode change event.

        Parameters:
        - darkmode (bool): Whether dark mode is enabled or not.
        - fig (dict): The current 3D scatter plot figure.

        Returns:
        - dict: A dictionary containing the updated 3D scatter plot figure.

        Output Properties:
        - scatter3d (dict): The updated 3D scatter plot figure.
        """
        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

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
        click_data,
        trigger_input,
        click_hide,
        session_id,
    ):
        """
        Callback function for the visible table change event.

        Parameters:
        - click_data (dict): The click data from the 3D scatter plot.
        - trigger_input (int): The input trigger value.
        - click_hide (bool): Whether click hide mode is enabled or not.
        - session_id (str): The ID of the current session.

        Returns:
        - dict: A dictionary containing the updated trigger value.

        Output Properties:
        - trigger (int): The updated trigger value.
        """
        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
        if click_hide:
            if visible_table["_VIS_"][click_data["points"][0]["id"]] == "visible":
                visible_table.at[click_data["points"][0]["id"], "_VIS_"] = "hidden"
            else:
                visible_table.at[click_data["points"][0]["id"], "_VIS_"] = "visible"

            cache_set(visible_table, session_id, CACHE_KEYS["visible_table"])

            return {"trigger": trigger_input + 1}

        raise PreventUpdate

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
            "trigger": Output("background-trigger", "data"),
        },
        inputs={
            "cat_values": Input({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": Input({"type": "filter-slider", "index": ALL}, "value"),
            "visible_list": Input("visible-picker", "value"),
            "unused_vistable_trigger": Input("visible-table-change-trigger", "data"),
            "c_key": Input("c-picker-3d", "value"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
        },
        state={
            "ispaused": State("interval-component", "disabled"),
            "slider_arg": State("slider-frame", "value"),
            "overlay_enable": State("overlay-switch", "value"),
            "decay": State("decay-slider", "value"),
            "colormap": State("colormap-3d", "value"),
            "darkmode": State("darkmode-switch", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
            "trigger_val": State("background-trigger", "data"),
        },
        prevent_initial_call=True,
    )
    def regenerate_figure_callback(
        cat_values,
        num_values,
        visible_list,
        unused_vistable_trigger,
        ispaused,
        slider_arg,
        c_key,
        overlay_enable,
        unused_left_hide_trigger,
        unused_file_loaded,
        decay,
        colormap,
        darkmode,
        session_id,
        file,
        file_list,
        trigger_val,
    ):
        """
        Callback function for regenerating the figure.

        Parameters:
        - cat_values (dict): The selected categorical values for filtering.
        - num_values (dict): The selected numerical values for filtering.
        - visible_list (list): The list of visible items.
        - unused_vistable_trigger (int): The trigger value for visible table change event.
        - ispaused (bool): Whether the animation is paused or not.
        - slider_arg (int): The value of the slider.
        - c_key (str): The selected color key.
        - overlay_enable (bool): Whether overlay mode is enabled or not.
        - unused_left_hide_trigger (int): The trigger value for left hide event.
        - unused_file_loaded (int): The trigger value for file loaded event.
        - decay (int): The number of past frames to include in the figure.
        - colormap (str): The selected colormap.
        - darkmode (bool): Whether dark mode is enabled or not.
        - session_id (str): The ID of the current session.
        - file (str): The selected file.
        - file_list (list): The list of selected files.
        - trigger_val (int): The trigger value.

        Returns:
        - dict: A dictionary containing the updated 3D scatter plot figure and trigger value.

        Output Properties:
        - scatter3d (dict): The updated 3D scatter plot figure.
        """
        # invoke task
        cache_set(-1, session_id, CACHE_KEYS["task_id"])
        # save filter key word arguments to Redis
        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        filter_kwargs["num_values"] = num_values
        filter_kwargs["cat_values"] = cat_values
        cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

        # cache_set(0, session_id, CACHE_KEYS["task_id"])
        cache_set(-1, session_id, CACHE_KEYS["figure_idx"])
        if file not in file_list:
            file_list.append(file)

        # get config from Redis
        config = cache_get(session_id, CACHE_KEYS["config"])

        if overlay_enable:
            fig = process_overlay_frame(
                slider_arg,
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                session_id,
                file,
                file_list,
                ispaused,
            )
        else:
            fig = process_single_frame(
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                decay,
                session_id,
                file,
                slider_arg,
                ispaused,
            )

        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {"scatter3d": fig, "trigger": trigger_val + 1}

    @app.callback(
        background=True,
        output={
            "dummy": Output("dummy-background", "data"),
        },
        inputs={
            "trigger_idx": Input("background-trigger", "data"),
        },
        state={
            "cat_values": State({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": State({"type": "filter-slider", "index": ALL}, "value"),
            "visible_list": State("visible-picker", "value"),
            "c_key": State("c-picker-3d", "value"),
            "session_id": State("session-id", "data"),
            "case": State("test-case", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        cancel=[Input("background-trigger", "data")],
        progress=[
            Output("buffer", "value"),
            Output("buffer-tooltip", "children"),
        ],
        manager=background_callback_manager,
    )
    def regenerate_figure_background_callback(
        set_progress,
        trigger_idx,
        cat_values,
        num_values,
        visible_list,
        c_key,
        session_id,
        case,
        file,
        file_list,
    ):
        """
        Background callback function for regenerating the figure.

        Parameters:
        - set_progress (function): The function to set the progress of the background task.
        - trigger_idx (int): The trigger value for the background task.
        - cat_values (dict): The selected categorical values for filtering.
        - num_values (dict): The selected numerical values for filtering.
        - visible_list (list): The list of visible items.
        - c_key (str): The selected color key.
        - session_id (str): The ID of the current session.
        - case (str): The selected case.
        - file (str): The selected file.
        - file_list (list): The list of selected files.

        Returns:
        - dict: A dictionary containing a dummy output.

        Output Properties:
        - dummy (any): A dummy output value.
        """
        cache_set(trigger_idx, session_id, CACHE_KEYS["task_id"])
        print("start new task (" + str(trigger_idx) + ")")

        set_progress([0, "Buffering ... (0 %)"])

        cache_expire()

        if file not in file_list:
            file_list.append(file)

        # set figure index to -1 (no buffer is ready)
        cache_set(-1, session_id, CACHE_KEYS["figure_idx"])

        config = cache_get(session_id, CACHE_KEYS["config"])
        keys_dict = config["keys"]

        slider_label = keys_dict[config["slider"]]["description"]

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

        dataset = load_data_list(file_list, case)
        frame_group = dataset.groupby(config["slider"])

        # prepare figure key word arguments
        fig_kwargs = prepare_figure_kwargs(
            config,
            frame_list,
            c_key,
            num_keys,
            num_values,
        )

        for slider_arg, frame_idx in enumerate(frame_list):
            file = json.loads(file_list[0])
            img_path = os.path.join(
                file["path"], file["name"][0:-4], str(slider_arg) + ".jpg"
            )

            # encode image frame
            fig_kwargs["image"] = load_image(img_path)

            fig_kwargs["name"] = (
                "Index: "
                + str(slider_arg)
                + " ("
                + slider_label
                + ": "
                + str(frame_idx)
                + ")"
            )

            data = frame_group.get_group(frame_idx)
            filterd_frame = filter_all(
                data,
                num_keys,
                num_values,
                cat_keys,
                cat_values,
                visible_table,
                visible_list,
            )

            fig = get_scatter3d_data(filterd_frame, **fig_kwargs)

            hover_strings = get_hover_strings(
                filterd_frame, fig_kwargs["c_key"], fig_kwargs["c_type"], keys_dict
            )
            if fig_kwargs["x_ref"] is not None and fig_kwargs["y_ref"] is not None:
                ref_fig = [
                    get_ref_scatter3d_data(
                        data_frame=filterd_frame,
                        x_key=fig_kwargs["x_ref"],
                        y_key=fig_kwargs["y_ref"],
                        z_key=None,
                        name=fig_kwargs.get("ref_name", None),
                    )
                ]
            else:
                ref_fig = []

            fig_layout = get_scatter3d_layout(**fig_kwargs)

            if trigger_idx != cache_get(session_id, CACHE_KEYS["task_id"]):
                print("task (" + str(trigger_idx) + ") cancelled")
                set_progress([0, "Buffering ... (0 %)"])
                return {"dummy": 0}

            cache_set(slider_arg, session_id, CACHE_KEYS["figure_idx"])
            cache_set(fig, session_id, CACHE_KEYS["figure"], str(slider_arg))
            cache_set(hover_strings, session_id, CACHE_KEYS["hover"], str(slider_arg))
            cache_set(ref_fig, session_id, CACHE_KEYS["figure_ref"], str(slider_arg))
            cache_set(
                fig_layout, session_id, CACHE_KEYS["figure_layout"], str(slider_arg)
            )

            percent = slider_arg / len(frame_list) * 100
            set_progress(
                [
                    percent,
                    "Buffering ... (" + str(round(percent, 2)) + " %)",
                ]
            )

        set_progress([100, "Buffer ready (100 %)"])

        print("task (" + str(trigger_idx) + ") completed")

        return {"dummy": 0}

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
        unused_cat_values,
        unused_num_values,
        unused_visible_list,
        unused_vistable_trigger,
        unused_file_loaded,
        trigger_idx,
    ):
        """
        Callback function to invoke the filter trigger.

        Parameters:
        - unused_cat_values (dict): The unused selected categorical values for filtering.
        - unused_num_values (dict): The unused selected numerical values for filtering.
        - unused_visible_list (list): The unused list of visible items.
        - unused_vistable_trigger (int): The unused trigger value for visible table change event.
        - unused_file_loaded (int): The unused trigger value for file loaded event.
        - trigger_idx (int): The current value of the filter trigger.

        Returns:
        - dict: A dictionary containing the updated filter trigger value.

        Output Properties:
        - filter_trigger (int): The updated filter trigger value.
        """
        filter_trig = trigger_idx + 1

        return {"filter_trigger": filter_trig}

    @app.callback(
        background=True,
        output={"dummy": Output("hidden-scatter3d", "children")},
        inputs={"btn": Input("export-scatter3d", "n_clicks")},
        state={
            "case": State("test-case", "value"),
            "session_id": State("session-id", "data"),
            "c_key": State("c-picker-3d", "value"),
            "colormap": State("colormap-3d", "value"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
            "decay": State("decay-slider", "value"),
            "darkmode": State("darkmode-switch", "value"),
        },
        manager=background_callback_manager,
    )
    def export_3d_scatter_animation(
        btn,
        case,
        session_id,
        c_key,
        colormap,
        visible_list,
        file,
        file_list,
        decay,
        darkmode,
    ):
        """
        Background callback function for exporting 3D scatter animation.

        Parameters:
        - btn (int): The number of clicks on the export button.
        - case (str): The selected case.
        - session_id (str): The ID of the current session.
        - c_key (str): The selected color key.
        - colormap (str): The selected colormap.
        - visible_list (list): The list of visible items.
        - file (str): The selected file.
        - file_list (list): The list of selected files.
        - decay (int): The number of past frames to include in the animation.
        - darkmode (bool): Whether dark mode is enabled or not.

        Returns:
        - dict: A dictionary containing a dummy output.

        Output Properties:
        - dummy (any): A dummy output value.
        """
        if btn == 0:
            raise PreventUpdate

        if not os.path.exists("data/" + case + "/images"):
            os.makedirs("data/" + case + "/images")

        config = cache_get(session_id, CACHE_KEYS["config"])
        keys_dict = config["keys"]
        c_type = keys_dict[c_key].get("type", KEY_TYPES["NUM"])

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        num_values = filter_kwargs["num_values"]
        cat_values = filter_kwargs["cat_values"]

        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

        fig_kwargs = prepare_figure_kwargs(
            config,
            frame_list,
            c_key,
            num_keys,
            num_values,
        )

        if darkmode:
            fig_kwargs["template"] = "plotly_dark"
        else:
            fig_kwargs["template"] = "plotly"

        if file not in file_list:
            file_list.append(file)

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        dataset = load_data_list(file_list, case)
        filtered_table = filter_all(
            dataset,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list,
        )

        img_list = []

        for _, f_val in enumerate(frame_list):
            file = json.loads(file_list[0])
            img_idx = np.where(frame_list == f_val)[0][0]
            img_list.append(
                os.path.join(file["path"], file["name"][0:-4], str(img_idx) + ".jpg")
            )

        fig_kwargs["title"] = file["name"][0:-4]

        fig_kwargs["height"] = 750

        fig_kwargs["decay"] = decay
        fig_kwargs["c_type"] = c_type
        fig_kwargs["keys_dict"] = keys_dict

        fig = go.Figure(
            get_animation_data(
                filtered_table,
                frame_key=config["slider"],
                img_list=img_list,
                colormap=colormap,
                **fig_kwargs
            )
        )

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        fig.write_html(
            "data/"
            + case
            + "/images/"
            + timestamp
            + "_"
            + file["name"][0:-4]
            + "_3dview.html"
        )

        return {"dummy": 0}

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
    def export_all_frame_data(btn, session_id, visible_list, file, file_list):
        """
        Callback function for exporting filtered data.

        Parameters:
        - btn (int): The number of clicks on the export button.
        - session_id (str): The ID of the current session.
        - visible_list (list): The list of visible items.
        - file (str): The selected file.
        - file_list (list): The list of selected files.

        Returns:
        - dict: A dictionary containing a dummy output.

        Output Properties:
        - dummy (any): A dummy output value.
        """
        if btn == 0:
            raise PreventUpdate

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        # file = json.loads(file)
        data = load_data(file, file_list)
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
        file = json.loads(file)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + file["name"][0:-4] + "_" + timestamp + ".csv"

        filtered_table.to_csv(
            file_name,
            index=False,
        )

        return {"download": dcc.send_file(file_name)}

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
    def export_current_frame_data(btn, slider_arg, session_id, visible_list, file):
        """
        Callback function for exporting filtered data.

        Parameters:
        - btn (int): The number of clicks on the export button.
        - session_id (str): The ID of the current session.
        - visible_list (list): The list of visible items.
        - file (str): The selected file.

        Returns:
        - dict: A dictionary containing a dummy output.

        Output Properties:
        - dummy (any): A dummy output value.
        """
        if btn == 0:
            raise PreventUpdate

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        # file = json.loads(file)
        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
        data = cache_get(
            session_id, CACHE_KEYS["frame_data"], str(frame_list[slider_arg])
        )
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
        file = json.loads(file)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + file["name"][0:-4] + "_" + timestamp + ".csv"

        filtered_table.to_csv(
            file_name,
            index=False,
        )

        return {"download": dcc.send_file(file_name)}
