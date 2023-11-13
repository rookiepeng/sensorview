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
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
import plotly.io as pio
import plotly.graph_objs as go

from maindash import app

from tasks import filter_all
from tasks import celery_filtering_data

from utils import cache_set, cache_get, CACHE_KEYS, KEY_TYPES
from utils import load_data
from utils import load_data_list
from utils import load_image
from utils import prepare_figure_kwargs
from utils import background_callback_manager

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
    case,
    file,
    frame_idx=0,
    load_hover=False,
):
    """_summary_

    :param config: _description_
    :type config: _type_
    :param cat_values: _description_
    :type cat_values: _type_
    :param num_values: _description_
    :type num_values: _type_
    :param colormap: _description_
    :type colormap: _type_
    :param visible_list: _description_
    :type visible_list: _type_
    :param c_key: _description_
    :type c_key: _type_
    :param decay: _description_
    :type decay: _type_
    :param session_id: _description_
    :type session_id: _type_
    :param case: _description_
    :type case: _type_
    :param file: _description_
    :type file: _type_
    :param frame_idx: _description_, defaults to 0
    :type frame_idx: int, optional
    :param load_hover: _description_, defaults to False
    :type load_hover: bool, optional
    :return: _description_
    :rtype: _type_
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
    img_path = (
        "./data/"
        + case
        + file["path"]
        + "/"
        + file["name"][0:-4]
        + "/"
        + str(frame_idx)
        + ".jpg"
    )

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
    case,
    file,
    file_list,
    load_hover=False,
):
    """_summary_

    :param frame_idx: _description_
    :type frame_idx: _type_
    :param config: _description_
    :type config: _type_
    :param cat_values: _description_
    :type cat_values: _type_
    :param num_values: _description_
    :type num_values: _type_
    :param colormap: _description_
    :type colormap: _type_
    :param visible_list: _description_
    :type visible_list: _type_
    :param c_key: _description_
    :type c_key: _type_
    :param session_id: _description_
    :type session_id: _type_
    :param case: _description_
    :type case: _type_
    :param file: _description_
    :type file: _type_
    :param file_list: _description_
    :type file_list: _type_
    :param load_hover: _description_, defaults to False
    :type load_hover: bool, optional
    :return: _description_
    :rtype: _type_
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
    data = load_data(file, file_list, case)
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
        "case": State("case-picker", "value"),
        "file": State("file-picker", "value"),
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
    case,
    file,
    file_list,
):
    """_summary_

    :param slider_arg: _description_
    :type slider_arg: _type_
    :param cat_values: _description_
    :type cat_values: _type_
    :param num_values: _description_
    :type num_values: _type_
    :param unused_stop_click: _description_
    :type unused_stop_click: _type_
    :param ispaused: _description_
    :type ispaused: bool
    :param colormap: _description_
    :type colormap: _type_
    :param visible_list: _description_
    :type visible_list: _type_
    :param c_key: _description_
    :type c_key: _type_
    :param overlay_enable: _description_
    :type overlay_enable: _type_
    :param decay: _description_
    :type decay: _type_
    :param darkmode: _description_
    :type darkmode: _type_
    :param session_id: _description_
    :type session_id: _type_
    :param case: _description_
    :type case: _type_
    :param file: _description_
    :type file: _type_
    :param file_list: _description_
    :type file_list: _type_
    :return: _description_
    :rtype: _type_
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
            case,
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
                                session_id, CACHE_KEYS["figure"], str(slider_arg - val)
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
            case,
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
    """_summary_

    :param colormap: _description_
    :type colormap: _type_
    :param fig: _description_
    :type fig: _type_
    :return: _description_
    :rtype: _type_
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
    """_summary_

    :param darkmode: _description_
    :type darkmode: _type_
    :param fig: _description_
    :type fig: _type_
    :return: _description_
    :rtype: _type_
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
    """_summary_

    :param click_data: _description_
    :type click_data: _type_
    :param trigger_input: _description_
    :type trigger_input: _type_
    :param click_hide: _description_
    :type click_hide: _type_
    :param session_id: _description_
    :type session_id: _type_
    :raises PreventUpdate: _description_
    :return: _description_
    :rtype: _type_
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
        "case": State("case-picker", "value"),
        "file": State("file-picker", "value"),
        "file_list": State("file-add", "value"),
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
    case,
    file,
    file_list,
):
    """
    Callback when filter changed

    :param int slider_arg
        slider position
    :param list cat_values
        selected categorical keys
    :param list num_values
        sliders range
    :param str colormap
        colormap name
    :param list visible_list
        visibility list
    :param str c_key
        key for color
    :param boolean overlay_enable
        flag to overlay all frames
    :param json click_data
        properties of the clicked data point
    _
    :param int decay
        number of decay frames
    :param boolean click_hide
        flag to hide the data when clicked
    :param int trigger_idx
        current trigger value
    :param str session_id
        session id
    :param str case
        case name
    :param json file
        selected file

    :return: [
        Scatter 3D graph,
        Filter trigger value (to trigger other graphs)
    ]
    :rtype: list
    """

    # invoke task
    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    filter_kwargs["num_values"] = num_values
    filter_kwargs["cat_values"] = cat_values
    cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

    # invoke celery task
    cache_set(0, session_id, CACHE_KEYS["task_id"])
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
            case,
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
            case,
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
        "trigger_val": State("background-trigger", "data"),
    },
)
def regenerate_figure_background_trigger(
    cat_values,
    num_values,
    visible_list,
    unused_vistable_trigger,
    c_key,
    unused_left_hide_trigger,
    unused_file_loaded,
    trigger_val,
):
    return {"trigger": trigger_val + 1}


@app.callback(
    background=True,
    output={
        "dummy": Output("dummy-background", "data"),
    },
    inputs={
        "trigger": Input("background-trigger", "data"),
    },
    state={
        "cat_values": State({"type": "filter-dropdown", "index": ALL}, "value"),
        "num_values": State({"type": "filter-slider", "index": ALL}, "value"),
        "visible_list": State("visible-picker", "value"),
        "unused_vistable_trigger": State("visible-table-change-trigger", "data"),
        "c_key": State("c-picker-3d", "value"),
        "unused_left_hide_trigger": State("left-hide-trigger", "data"),
        "unused_file_loaded": State("file-loaded-trigger", "data"),
        "ispaused": State("interval-component", "disabled"),
        "slider_arg": State("slider-frame", "value"),
        "overlay_enable": State("overlay-switch", "value"),
        "decay": State("decay-slider", "value"),
        "colormap": State("colormap-3d", "value"),
        "darkmode": State("darkmode-switch", "value"),
        "session_id": State("session-id", "data"),
        "case": State("case-picker", "value"),
        "file": State("file-picker", "value"),
        "file_list": State("file-add", "value"),
    },
    cancel=[Input("background-trigger", "data")],
    manager=background_callback_manager,
)
def regenerate_figure_background_callback(
    trigger,
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
    case,
    file,
    file_list,
):
    # invoke task
    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    filter_kwargs["num_values"] = num_values
    filter_kwargs["cat_values"] = cat_values
    cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

    task_kwargs = {}
    task_kwargs["c_key"] = c_key

    # invoke celery task
    cache_set(0, session_id, CACHE_KEYS["task_id"])
    cache_set(-1, session_id, CACHE_KEYS["figure_idx"])
    if file not in file_list:
        file_list.append(file)
    celery_filtering_data(session_id, case, file_list, visible_list, **task_kwargs)

    return {"dummy": 0}


@app.callback(
    output={"filter_trigger": Output("filter-trigger", "data")},
    inputs={
        "unused_cat_values": Input({"type": "filter-dropdown", "index": ALL}, "value"),
        "unused_num_values": Input({"type": "filter-slider", "index": ALL}, "value"),
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
    """_summary_

    :param unused_cat_values: _description_
    :type unused_cat_values: _type_
    :param unused_num_values: _description_
    :type unused_num_values: _type_
    :param unused_visible_list: _description_
    :type unused_visible_list: _type_
    :param unused_vistable_trigger: _description_
    :type unused_vistable_trigger: _type_
    :param unused_file_loaded: _description_
    :type unused_file_loaded: _type_
    :param trigger_idx: _description_
    :type trigger_idx: _type_
    :return: _description_
    :rtype: _type_
    """
    filter_trig = trigger_idx + 1

    return {"filter_trigger": filter_trig}


@app.callback(
    background=True,
    output={"dummy": Output("hidden-scatter3d", "children")},
    inputs={"btn": Input("export-scatter3d", "n_clicks")},
    state={
        "case": State("case-picker", "value"),
        "session_id": State("session-id", "data"),
        "c_key": State("c-picker-3d", "value"),
        "colormap": State("colormap-3d", "value"),
        "visible_list": State("visible-picker", "value"),
        "file": State("file-picker", "value"),
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
    Export 3D scatter into an interactive animation file

    :param int btn
        number of clicks
    :param str case
        case name
    :param str session_id
        session id
    :param str c_key
        color key
    :param str colormap
        colormap name
    :param list visible_list
        visibility list
    :param json file
        selected file

    :return: dummy
    :rtype: int
    """
    if btn == 0:
        raise PreventUpdate

    if not os.path.exists("data/" + case + "/images"):
        os.makedirs("data/" + case + "/images")

    fig_kwargs = {}
    fig_kwargs["c_key"] = c_key
    fig_kwargs["colormap"] = colormap
    fig_kwargs["decay"] = decay

    if darkmode:
        fig_kwargs["template"] = "plotly_dark"
    else:
        fig_kwargs["template"] = "plotly"

    if file not in file_list:
        file_list.append(file)

    config = cache_get(session_id, CACHE_KEYS["config"])
    keys_dict = config["keys"]

    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs["cat_keys"]
    num_keys = filter_kwargs["num_keys"]
    num_values = filter_kwargs["num_values"]
    cat_values = filter_kwargs["cat_values"]

    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
    frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

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
            "./data/"
            + case
            + file["path"]
            + "/"
            + file["name"][0:-4]
            + "/"
            + str(img_idx)
            + ".jpg"
        )

    # prepare figure key word arguments
    fig_kwargs["hover"] = keys_dict

    fig_kwargs["x_key"] = config.get("x_3d", num_keys[0])
    fig_kwargs["x_label"] = keys_dict[fig_kwargs["x_key"]].get(
        "description", fig_kwargs["x_key"]
    )
    fig_kwargs["y_key"] = config.get("y_3d", num_keys[1])
    fig_kwargs["y_label"] = keys_dict[fig_kwargs["y_key"]].get(
        "description", fig_kwargs["y_key"]
    )
    fig_kwargs["z_key"] = config.get("z_3d", num_keys[2])
    fig_kwargs["z_label"] = keys_dict[fig_kwargs["z_key"]].get(
        "description", fig_kwargs["z_key"]
    )
    # c_key = fig_kwargs['c_key']
    fig_kwargs["c_label"] = keys_dict[fig_kwargs["c_key"]].get(
        "description", fig_kwargs["c_key"]
    )
    fig_kwargs["x_ref"] = config.get("x_ref", None)
    fig_kwargs["y_ref"] = config.get("y_ref", None)

    # set graph's range the same for all the frames
    if (fig_kwargs["x_ref"] is not None) and (fig_kwargs["y_ref"] is not None):
        fig_kwargs["x_range"] = [
            min(
                [
                    num_values[num_keys.index(fig_kwargs["x_key"])][0],
                    num_values[num_keys.index(fig_kwargs["x_ref"])][0],
                ]
            ),
            max(
                [
                    num_values[num_keys.index(fig_kwargs["x_key"])][1],
                    num_values[num_keys.index(fig_kwargs["x_ref"])][1],
                ]
            ),
        ]
        fig_kwargs["y_range"] = [
            min(
                [
                    num_values[num_keys.index(fig_kwargs["y_key"])][0],
                    num_values[num_keys.index(fig_kwargs["y_ref"])][0],
                ]
            ),
            max(
                [
                    num_values[num_keys.index(fig_kwargs["y_key"])][1],
                    num_values[num_keys.index(fig_kwargs["y_ref"])][1],
                ]
            ),
        ]
    else:
        fig_kwargs["x_range"] = [
            num_values[num_keys.index(fig_kwargs["x_key"])][0],
            num_values[num_keys.index(fig_kwargs["x_key"])][1],
        ]
        fig_kwargs["y_range"] = [
            num_values[num_keys.index(fig_kwargs["y_key"])][0],
            num_values[num_keys.index(fig_kwargs["y_key"])][1],
        ]
    fig_kwargs["z_range"] = [
        num_values[num_keys.index(fig_kwargs["z_key"])][0],
        num_values[num_keys.index(fig_kwargs["z_key"])][1],
    ]

    if keys_dict[fig_kwargs["c_key"]].get("type", KEY_TYPES["NUM"]) == KEY_TYPES["NUM"]:
        fig_kwargs["c_range"] = [
            num_values[num_keys.index(fig_kwargs["c_key"])][0],
            num_values[num_keys.index(fig_kwargs["c_key"])][1],
        ]
    else:
        fig_kwargs["c_range"] = [0, 0]

    fig_kwargs["c_type"] = keys_dict[fig_kwargs["c_key"]].get("type", KEY_TYPES["NUM"])
    fig_kwargs["ref_name"] = "Host Vehicle"
    fig_kwargs["hover"] = keys_dict

    fig_kwargs["title"] = file["name"][0:-4]

    fig_kwargs["height"] = 750

    fig = go.Figure(
        get_animation_data(
            filtered_table, frame_key=config["slider"], img_list=img_list, **fig_kwargs
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
    output={"dummy": Output("dummy-export-data", "data")},
    inputs={"btn": Input("export-data", "n_clicks")},
    state={
        "session_id": State("session-id", "data"),
        "visible_list": State("visible-picker", "value"),
        "case": State("case-picker", "value"),
        "file": State("file-picker", "value"),
        "file_list": State("file-add", "value"),
    },
)
def export_data(btn, session_id, visible_list, case, file, file_list):
    """
    Export filtered data

    :param int btn
        number of clicks
    :param str session_id
    :param list visible_list
        visibility list
    :param str case
        case name
    :param json file
        selected file

    :return: dummy
    :rtype: int
    """
    if btn == 0:
        raise PreventUpdate

    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs["cat_keys"]
    num_keys = filter_kwargs["num_keys"]
    cat_values = filter_kwargs["cat_values"]
    num_values = filter_kwargs["num_values"]

    # file = json.loads(file)
    data = load_data(file, file_list, case)
    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

    filtered_table = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )
    file = json.loads(file)
    filtered_table.to_pickle(
        "./data/" + case + file["path"] + "/" + file["name"][0:-4] + "_filtered.pkl"
    )

    return {"dummy": 0}
