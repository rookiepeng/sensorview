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

import os

import datetime

import plotly.graph_objs as go

from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from maindash import app

from tasks import filter_all

from viz.viz import get_scatter2d

from utils import cache_get, CACHE_KEYS, KEY_TYPES
from utils import background_callback_manager
from utils import load_data


@app.callback(
    background=True,
    output={
        "figure": Output("scatter2d-right", "figure", allow_duplicate=True),
    },
    inputs={
        "unused_filter_trigger": Input("filter-trigger", "data"),
        "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
        "right_sw": Input("right-switch", "value"),
        "x_right": Input("x-picker-2d-right", "value"),
        "y_right": Input("y-picker-2d-right", "value"),
        "color_right": Input("c-picker-2d-right", "value"),
    },
    state={
        "colormap": State("colormap-scatter2d-right", "value"),
        "session_id": State("session-id", "data"),
        "visible_list": State("visible-picker", "value"),
        "case": State("case-picker", "value"),
        "file": State("file-picker", "value"),
        "file_list": State("file-add", "value"),
    },
    manager=background_callback_manager,
    prevent_initial_call=True,
)
def regenerate_scatter2d_right_callback(
    unused_filter_trigger,
    unused_left_hide_trigger,
    right_sw,
    x_right,
    y_right,
    color_right,
    colormap,
    session_id,
    visible_list,
    case,
    file,
    file_list,
):
    """
    Update right 2D scatter graph

    :param int unused1
        unused trigger data
    :param int unused2
        unused trigger data
    :param boolean left_sw
        flag to indicate if this graph is enabled or disabled
    :param str x_left
        key for the x-axis
    :param str y_left
        key for the y-axis
    :param str color_left
        key for the color
    :param str colormap
        colormap name
    :param str session_id
        session id
    :param list visible_list
        visibility list
    :param str case
        case name
    :param json file
        selected file

    :return: [
        2D Scatter graph,
        X axis picker enable/disable,
        Y axis picker enable/disable,
        Color picker enable/disable,
        Colormap picker enable/disable
    ]
    :rtype: list
    """
    if not right_sw:
        right_fig = {
            "data": [{"mode": "markers", "type": "scattergl", "x": [], "y": []}],
            "layout": {},
        }

        return {
            "figure": right_fig,
        }

    config = cache_get(session_id, CACHE_KEYS["config"])
    keys_dict = config["keys"]

    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs["cat_keys"]
    num_keys = filter_kwargs["num_keys"]
    cat_values = filter_kwargs["cat_values"]
    num_values = filter_kwargs["num_values"]

    x_key = x_right
    y_key = y_right
    c_key = color_right
    x_label = keys_dict[x_right]["description"]
    y_label = keys_dict[y_right]["description"]
    c_label = keys_dict[color_right]["description"]

    data = load_data(file, file_list, case)
    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
    filtered_table = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )

    right_fig = get_scatter2d(
        filtered_table,
        x_key,
        y_key,
        c_key,
        x_label,
        y_label,
        c_label,
        colormap=colormap,
        c_type=keys_dict[c_key].get("type", KEY_TYPES["NUM"]),
    )

    return {
        "figure": right_fig,
    }


@app.callback(
    output={
        "figure": Output("scatter2d-right", "figure", allow_duplicate=True),
    },
    inputs={
        "colormap": Input("colormap-scatter2d-right", "value"),
    },
    state={
        "fig_in": State("scatter2d-right", "figure"),
        "right_sw": State("right-switch", "value"),
    },
    prevent_initial_call=True,
)
def scatter2d_right_colormap_change_callback(
    colormap,
    fig_in,
    right_sw,
):
    """
    Update right 2D scatter graph
    """

    if not right_sw:
        right_fig = {
            "data": [{"mode": "markers", "type": "scattergl", "x": [], "y": []}],
            "layout": {},
        }

        return {
            "figure": right_fig,
        }

    for idx in range(0, len(fig_in["data"])):
        fig_in["data"][idx]["marker"]["colorscale"] = colormap

    return {
        "figure": fig_in,
    }


@app.callback(
    output={
        "collapse": Output("collapse-right2d", "is_open"),
    },
    inputs={
        "right_sw": Input("right-switch", "value"),
    },
)
def enable_scatter2d_right_callback(
    right_sw,
):
    """ """

    collapse = False
    if right_sw:
        collapse = True

    return {"collapse": collapse}


@app.callback(
    output={"dummy": Output("dummy-export-scatter2d-right", "data")},
    inputs={"btn": Input("export-scatter2d-right", "n_clicks")},
    state={
        "fig": State("scatter2d-right", "figure"),
        "case": State("case-picker", "value"),
    },
)
def export_right_2d_scatter(btn, fig, case):
    """
    Export 2D scatter into a png

    :param int btn
        number of clicks
    :param graph fig
        2D figure
    :param str case
        case name

    :return: dummy
    :rtype: int
    """
    if btn == 0:
        raise PreventUpdate

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    if not os.path.exists("data/" + case + "/images"):
        os.makedirs("data/" + case + "/images")

    temp_fig = go.Figure(fig)
    temp_fig.write_image(
        "data/" + case + "/images/" + timestamp + "_fig_right.png", scale=2
    )
    return {"dummy": 0}
