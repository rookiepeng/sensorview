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

import numpy as np
import pandas as pd


def get_hover_strings(data_frame, c_key, c_type, hover):
    """
    Generate the hover strings for the data frame.

    Parameters:
    - data_frame (pd.DataFrame): The data frame containing the data.
    - c_key (str): The key for the color data.
    - c_type (str): The type of the color data.
    - hover (dict): The dictionary specifying the hover descriptions and formats.

    Returns:
    - list: The list of hover strings.
    """
    hover_str_list = []
    if hover is None:
        return hover_str_list

    if c_type == "numerical":
        rows = len(data_frame.index)
        hover_str = np.full(rows, "", dtype=object)
        for _, key in enumerate(hover):
            if key not in data_frame.columns:
                continue

            if "format" in hover[key]:
                hover_str = (
                    hover_str
                    + hover[key]["description"]
                    + ": "
                    + data_frame[key].map(hover[key]["format"].format)
                    + "<br>"
                )
            elif "decimal" in hover[key]:
                format_str = "{:,."+str(hover[key]["decimal"])+"f}"
                hover_str = (
                    hover_str
                    + hover[key]["description"]
                    + ": "
                    + data_frame[key].map(format_str.format)
                    + "<br>"
                )
            else:
                hover_str = (
                    hover_str
                    + hover[key]["description"]
                    + ": "
                    + data_frame[key].apply(str)
                    + "<br>"
                )
        hover_str_list.append(hover_str)

    elif c_type == "categorical":
        color_list = pd.unique(data_frame[c_key])

        for c_item in color_list:
            new_list = data_frame[data_frame[c_key] == c_item]

            rows = len(new_list.index)
            hover_str = np.full(rows, "", dtype=object)
            for _, key in enumerate(hover):
                if "format" in hover[key]:
                    hover_str = (
                        hover_str
                        + hover[key]["description"]
                        + ": "
                        + new_list[key].map(hover[key]["format"].format)
                        + "<br>"
                    )
                elif "decimal" in hover[key]:
                    format_str = "{:,."+str(hover[key]["decimal"])+"f}"
                    hover_str = (
                        hover_str
                        + hover[key]["description"]
                        + ": "
                        + new_list[key].map(format_str.format)
                        + "<br>"
                    )
                else:
                    hover_str = (
                        hover_str
                        + hover[key]["description"]
                        + ": "
                        + new_list[key].apply(str)
                        + "<br>"
                    )

            hover_str_list.append(hover_str)

    return hover_str_list


def get_scatter3d_data(data_frame, x_key, y_key, z_key, c_key, **kwargs):
    """
    Generate the 3D scatter plot data.

    Parameters:
    - data_frame (pd.DataFrame): The data frame containing the data.
    - x_key (str): The key for the x-axis data.
    - y_key (str): The key for the y-axis data.
    - z_key (str): The key for the z-axis data.
    - c_key (str): The key for the color data.
    - **kwargs: Additional keyword arguments for customization.

    Returns:
    - list: The 3D scatter plot data.
    """
    if data_frame.shape[0] == 0:
        return [{"mode": "markers", "type": "scatter3d", "x": [], "y": [], "z": []}]

    c_label = kwargs.get("c_label", c_key)
    name = kwargs.get("name", None)
    c_type = kwargs.get("c_type", "numerical")
    opacity = kwargs.get("opacity", 0.8)
    showlegend = kwargs.get("showlegend", True)

    linewidth = 0

    if c_type == "numerical":
        color = data_frame[c_key]
        c_range = kwargs.get("c_range", [np.min(color), np.max(color)])
        if c_range is None:
            c_range = [np.min(color), np.max(color)]

        fig_data = [
            dict(
                type="scatter3d",
                ids=data_frame.index,
                x=data_frame[x_key],
                y=data_frame[y_key],
                z=data_frame[z_key],
                #  text=hover_str,
                #  hovertemplate=hovertemplate,
                mode="markers",
                name=name,
                showlegend=showlegend,
                marker=dict(
                    size=3,
                    color=color,
                    opacity=opacity,
                    colorbar=dict(title=c_label),
                    cmin=c_range[0],
                    cmax=c_range[1],
                    line=dict(color="#757575", width=linewidth),
                ),
            )
        ]
    elif c_type == "categorical":
        fig_data = []
        color_list = pd.unique(data_frame[c_key])

        for c_item in color_list:
            new_list = data_frame[data_frame[c_key] == c_item]

            fig_data.append(
                dict(
                    type="scatter3d",
                    ids=new_list.index,
                    x=new_list[x_key],
                    y=new_list[y_key],
                    z=new_list[z_key],
                    # text=hover_str,
                    # hovertemplate='%{text}',
                    mode="markers",
                    name=str(c_item),
                    showlegend=showlegend,
                    marker=dict(
                        size=3,
                        opacity=opacity,
                        line=dict(
                            color="#757575",
                            width=linewidth,
                        ),
                    ),
                )
            )

    return fig_data


def get_ref_scatter3d_data(
    data_frame, x_key, y_key, z_key=None, name="Origin", **kwargs
):
    """
    Generate the reference scatter plot data.

    Parameters:
    - data_frame (pd.DataFrame): The data frame containing the data.
    - x_key (str): The key for the x-axis data.
    - y_key (str): The key for the y-axis data.
    - z_key (str): The key for the z-axis data.
    - name (str): The name of the reference data.
    - **kwargs: Additional keyword arguments for customization.

    Returns:
    - dict: The reference scatter plot data.
    """
    if data_frame.shape[0] == 0:
        return {"mode": "markers", "type": "scatter3d", "x": [], "y": [], "z": []}

    if z_key is None:
        z_data = [0]
    else:
        z_data = [data_frame[z_key].iloc[0]]

    fig_data = dict(
        type="scatter3d",
        x=[data_frame[x_key].iloc[0]],
        y=[data_frame[y_key].iloc[0]],
        z=z_data,
        hovertemplate="Lateral: %{x:.2f} m<br>" + "Longitudinal: %{y:.2f} m<br>",
        mode="markers",
        name=name,
        marker=dict(
            color="rgb(255, 255, 255)",
            size=6,
            opacity=1,
            symbol="circle",
            line=dict(
                color="#000000",
                width=2,
            ),
        ),
    )

    return fig_data
