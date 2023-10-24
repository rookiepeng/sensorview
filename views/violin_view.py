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

import plotly.express as px
import plotly.graph_objs as go

from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from maindash import app

from tasks import filter_all

from utils import cache_get, CACHE_KEYS
from utils import load_data
from utils import background_callback_manager


@app.callback(
    background=True,
    output={
        "violin": Output("violin", "figure"),
    },
    inputs={
        "filter_trigger": Input("filter-trigger", "data"),
        "left_hide_trigger": Input("left-hide-trigger", "data"),
        "violin_sw": Input("violin-switch", "value"),
        "x_violin": Input("x-picker-violin", "value"),
        "y_violin": Input("y-picker-violin", "value"),
        "c_violin": Input("c-picker-violin", "value"),
    },
    state={
        "session_id": State("session-id", "data"),
        "visible_list": State("visible-picker", "value"),
        "case": State("case-picker", "value"),
        "file": State("file-picker", "value"),
        "file_list": State("file-add", "value"),
    },
    manager=background_callback_manager,
)
def regenerate_violin_callback(
    filter_trigger,
    left_hide_trigger,
    violin_sw,
    x_violin,
    y_violin,
    c_violin,
    session_id,
    visible_list,
    case,
    file,
    file_list,
):
    """
    Update violin plot

    :param int unused1
        unused trigger data
    :param int unused2
        unused trigger data
    :param boolean violin_sw
        flag to indicate if this graph is enabled or disabled
    :param str x_violin
        key for the x-axis
    :param str y_violin
        key for the y-axis
    :param str c_violin
        key for the color
    :param str session_id
        session id
    :param list visible_list
        visibility list
    :param str case
        case name
    :param json file
        selected file

    :return: [
        Violin graph,
        X axis picker enable/disable,
        Y axis picker enable/disable,
        Color picker enable/disable,
    ]
    :rtype: list
    """
    if not violin_sw:
        violin_fig = {"data": [{"type": "histogram", "x": []}], "layout": {}}

        return {"violin": violin_fig}

    config = cache_get(session_id, CACHE_KEYS["config"])

    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs["cat_keys"]
    num_keys = filter_kwargs["num_keys"]
    cat_values = filter_kwargs["cat_values"]
    num_values = filter_kwargs["num_values"]

    x_key = x_violin
    if x_violin is None:
        raise PreventUpdate

    x_label = config["keys"][x_violin].get("description", x_key)
    y_key = y_violin
    y_label = config["keys"][y_violin].get("description", y_key)

    data = load_data(file, file_list, case)
    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
    filtered_table = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )

    if c_violin == "None":
        violin_fig = px.violin(
            filtered_table,
            x=x_key,
            y=y_key,
            box=True,
            violinmode="group",
            labels={x_key: x_label, y_key: y_label},
        )
    else:
        violin_fig = px.violin(
            filtered_table,
            x=x_key,
            y=y_key,
            color=c_violin,
            box=True,
            violinmode="group",
            labels={x_key: x_label, y_key: y_label},
        )

    return {"violin": violin_fig}


@app.callback(
    output={
        "collapse": Output("collapse-violin", "is_open"),
    },
    inputs={
        "violin_sw": Input("violin-switch", "value"),
    },
)
def enable_violin_callback(
    violin_sw,
):
    """
    Update violin plot

    :rtype: list
    """
    collapse = False
    if violin_sw:
        collapse = True

    return {"collapse": collapse}


@app.callback(
    output={"dummy": Output("dummy-export-violin", "data")},
    inputs={"btn": Input("export-violin", "n_clicks")},
    state={"fig": State("violin", "figure"), "case": State("case-picker", "value")},
)
def export_violin(btn, fig, case):
    """
    Export violin plot into a png

    :param int btn
        number of clicks
    :param graph fig
        violin plot
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
        "data/" + case + "/images/" + timestamp + "_violin.png", scale=2
    )
    return {"dummy": 0}
