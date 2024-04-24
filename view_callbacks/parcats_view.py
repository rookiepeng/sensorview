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

import numpy as np

import plotly.graph_objs as go

from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from app_config import background_callback_manager
from app_config import CACHE_KEYS

from utils import filter_all
from utils import cache_get
from utils import load_data


def get_parcats_view_callbacks(app):
    """
    Register the callback functions for the parallel coordinates view.

    Parameters:
    - app (Dash app): The Dash app.

    Returns:
    - None
    """

    @app.callback(
        background=True,
        output={
            "parallel": Output("parallel", "figure"),
        },
        inputs={
            "unused_filter_trigger": Input("filter-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "parallel_sw": Input("parallel-switch", "value"),
            "dim_parallel": Input("dim-picker-parallel", "value"),
            "c_key": Input("c-picker-parallel", "value"),
        },
        state={
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("file-picker", "value"),
            "file_list": State("file-add", "value"),
        },
        manager=background_callback_manager,
    )
    def regenerate_parallel_callback(
        unused_filter_trigger,
        unused_left_hide_trigger,
        parallel_sw,
        dim_parallel,
        c_key,
        session_id,
        visible_list,
        file,
        file_list,
    ):
        """
        Background callback function to regenerate the parallel coordinates figure
        based on the input values.

        Parameters:
        - unused_filter_trigger (any): Unused input trigger for filtering data.
        - unused_left_hide_trigger (any): Unused input trigger for hiding left panel.
        - parallel_sw (bool): The value of the parallel coordinates switch.
        - dim_parallel (list): The selected dimensions for the parallel coordinates.
        - c_key (str): The selected color key for the parallel coordinates.
        - session_id (str): The ID of the current session.
        - visible_list (list): The list of visible items.
        - file (str): The selected file.
        - file_list (list): The list of selected files.

        Returns:
        - dict: A dictionary containing the updated parallel coordinates figure.

        Output Properties:
        - parallel (dict): The updated parallel coordinates figure.
        """
        if not parallel_sw:
            parallel_fig = {"data": [{"type": "histogram", "x": []}], "layout": {}}

            return {
                "parallel": parallel_fig,
            }

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        if len(dim_parallel) > 0:
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

            dims = []
            for _, dim_key in enumerate(dim_parallel):
                dims.append(
                    go.parcats.Dimension(values=filtered_table[dim_key], label=dim_key)
                )

            if c_key != "None":
                unique_list = np.sort(filtered_table[c_key].unique())

                if np.issubdtype(unique_list.dtype, np.integer) or np.issubdtype(
                    unique_list.dtype, np.floating
                ):
                    parallel_fig = go.Figure(
                        data=[
                            go.Parcats(
                                dimensions=dims,
                                line={
                                    "color": filtered_table[c_key],
                                    "colorbar": dict(title=c_key),
                                },
                                hoveron="color",
                                hoverinfo="count+probability",
                                arrangement="freeform",
                            )
                        ]
                    )
                else:
                    filtered_table["_C_"] = np.zeros_like(filtered_table[c_key])
                    for idx, var in enumerate(unique_list):
                        filtered_table.loc[filtered_table[c_key] == var, "_C_"] = idx

                    parallel_fig = go.Figure(
                        data=[
                            go.Parcats(
                                dimensions=dims,
                                line={"color": filtered_table["_C_"]},
                                hoverinfo="count+probability",
                                arrangement="freeform",
                            )
                        ]
                    )
            else:
                parallel_fig = go.Figure(
                    data=[go.Parcats(dimensions=dims, arrangement="freeform")]
                )
        else:
            parallel_fig = {"data": [{"type": "histogram", "x": []}], "layout": {}}

        return {
            "parallel": parallel_fig,
        }

    @app.callback(
        output={
            "collapse": Output("collapse-parallel", "is_open"),
        },
        inputs={
            "parallel_sw": Input("parallel-switch", "value"),
        },
    )
    def enable_parallel_callback(
        parallel_sw,
    ):
        """
        Callback function to enable or disable the parallel coordinates collapse.

        Parameters:
        - parallel_sw (bool): The value of the parallel coordinates switch.

        Returns:
        - dict: A dictionary containing the updated value for the collapse property.

        Output Properties:
        - collapse (bool): Whether the parallel coordinates should be collapsed or not.
        """
        collapse = False
        if parallel_sw:
            collapse = True

        return {"collapse": collapse}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-parallel", "n_clicks")},
        state={
            "fig": State("parallel", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_parallel(btn, fig):
        """
        Callback function to export the parallel coordinates figure as an image.

        Parameters:
        - btn (int): The number of times the export button has been clicked.
        - fig (dict): The parallel coordinates figure.

        Returns:
        - dict: A dictionary containing a dummy value for the output property.

        Output Properties:
        - dummy (int): A dummy value to trigger the export.
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = "temp/" + timestamp + "_parallel.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": dcc.send_file(file_name)}
