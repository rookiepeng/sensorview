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
    """_summary_

    :param data_frame: _description_
    :type data_frame: _type_
    :param c_key: _description_
    :type c_key: _type_
    :param c_type: _description_
    :type c_type: _type_
    :param hover: _description_
    :type hover: _type_
    :return: _description_
    :rtype: _type_
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
    """_summary_

    :param data_frame: _description_
    :type data_frame: _type_
    :param x_key: _description_
    :type x_key: _type_
    :param y_key: _description_
    :type y_key: _type_
    :param z_key: _description_
    :type z_key: _type_
    :param c_key: _description_
    :type c_key: _type_
    :return: _description_
    :rtype: _type_
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
    """_summary_

    :param data_frame: _description_
    :type data_frame: _type_
    :param x_key: _description_
    :type x_key: _type_
    :param y_key: _description_
    :type y_key: _type_
    :param z_key: _description_, defaults to None
    :type z_key: _type_, optional
    :param name: _description_, defaults to "Origin"
    :type name: str, optional
    :return: _description_
    :rtype: _type_
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
