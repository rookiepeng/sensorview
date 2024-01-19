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

import base64

import numpy as np
import pandas as pd

from .graph_data import get_scatter3d_data, get_ref_scatter3d_data
from .graph_layout import get_scatter3d_layout

from .graph_data import get_hover_strings


def get_scatter3d(
    data_frame, x_key, y_key, z_key, c_key, x_ref=None, y_ref=None, z_ref=None, **kwargs
):
    """
    Generate the scatter 3D plot data and layout.

    Parameters:
    - data_frame (pd.DataFrame): The data frame containing the data.
    - x_key (str): The key for the x-axis data.
    - y_key (str): The key for the y-axis data.
    - z_key (str): The key for the z-axis data.
    - c_key (str): The key for the color data.
    - x_ref (str): The key for the x-axis reference data.
    - y_ref (str): The key for the y-axis reference data.
    - z_ref (str): The key for the z-axis reference data.
    - **kwargs: Additional keyword arguments for customization.

    Returns:
    - dict: The scatter 3D plot data and layout.
    """
    ref_name = kwargs.get("ref_name", None)

    if x_ref is None or y_ref is None:
        data = get_scatter3d_data(data_frame, x_key, y_key, z_key, c_key, **kwargs)
    else:
        data = get_scatter3d_data(data_frame, x_key, y_key, z_key, c_key, **kwargs) + [
            get_ref_scatter3d_data(
                data_frame=data_frame,
                x_key=x_ref,
                y_key=y_ref,
                z_key=z_ref,
                name=ref_name,
            )
        ]

    return {"data": data, "layout": get_scatter3d_layout(**kwargs)}


def get_heatmap(data_frame, x_key, y_key, x_label=None, y_label=None):
    """
    Generate the heatmap plot data and layout.

    Parameters:
    - data_frame (pd.DataFrame): The data frame containing the data.
    - x_key (str): The key for the x-axis data.
    - y_key (str): The key for the y-axis data.
    - x_label (str): The label for the x-axis.
    - y_label (str): The label for the y-axis.

    Returns:
    - dict: The heatmap plot data and layout.
    """
    if x_label is None:
        x_label = x_key

    if y_label is None:
        y_label = y_key

    return {
        "data": [
            {
                "type": "histogram2dcontour",
                "x": data_frame[x_key],
                "y": data_frame[y_key],
                "colorscale": "Jet",
            }
        ],
        "layout": {
            "xaxis": {"title": x_label},
            "yaxis": {"title": y_label},
        },
    }


def get_scatter2d(
    data_frame,
    x_key,
    y_key,
    c_key,
    x_label=None,
    y_label=None,
    uirevision="no_change",
    colormap="Jet",
    margin={"l": 40, "r": 40, "b": 40, "t": 60},
    **kwargs
):
    """
    Generate the 2D scatter plot data and layout.

    Parameters:
    - data_frame (pd.DataFrame): The data frame containing the data.
    - x_key (str): The key for the x-axis data.
    - y_key (str): The key for the y-axis data.
    - c_key (str): The key for the color data.
    - x_label (str): The label for the x-axis.
    - y_label (str): The label for the y-axis.
    - uirevision (str): The revision id for updating the plot.
    - colormap (str): The name of the colormap for the color data.
    - margin (dict): The margin settings for the plot.
    - **kwargs: Additional keyword arguments for customization.

    Returns:
    - dict: The 2D scatter plot data and layout.
    """
    linewidth = kwargs.get("linewidth", 0)

    if x_label is None:
        x_label = x_key

    if y_label is None:
        y_label = y_key

    c_label = kwargs.get("c_label", c_key)
    c_type = kwargs.get("c_type", "numerical")

    if c_type == "numerical":
        return {
            "data": [
                {
                    "type": "scattergl",
                    "ids": data_frame.index,
                    "x": data_frame[x_key],
                    "y": data_frame[y_key],
                    "mode": "markers",
                    "marker": {
                        "size": 6,
                        "color": data_frame[c_key],
                        "colorscale": colormap,
                        "opacity": 0.8,
                        "colorbar": {
                            "title": c_label,
                        },
                        "line": {
                            "color": "#FFFFFF",
                            "width": linewidth,
                        },
                    },
                }
            ],
            "layout": {
                "xaxis": {"title": x_label},
                "yaxis": {"title": y_label},
                "margin": margin,
                "uirevision": uirevision,
            },
        }

    if c_type == "categorical":
        data = []
        color_list = pd.unique(data_frame[c_key])
        for c_item in color_list:
            new_list = data_frame[data_frame[c_key] == c_item]
            data.append(
                {
                    "type": "scattergl",
                    "ids": new_list.index,
                    "x": new_list[x_key],
                    "y": new_list[y_key],
                    "mode": "markers",
                    "marker": {
                        "size": 6,
                        "opacity": 0.8,
                        "line": {
                            "color": "#FFFFFF",
                            "width": linewidth,
                        },
                    },
                    "name": c_item,
                }
            )
        return {
            "data": data,
            "layout": {
                "xaxis": {"title": x_label},
                "yaxis": {"title": y_label},
                "margin": margin,
                "uirevision": uirevision,
            },
        }


def frame_args(duration):
    """
    Generate the frame arguments for animation.

    Parameters:
    - duration (int): The duration of each frame in milliseconds.

    Returns:
    - dict: The frame arguments for animation.
    """
    return {
        "frame": {"duration": duration},
        "mode": "immediate",
        "fromcurrent": True,
        "transition": {"duration": duration, "easing": "quadratic-in-out"},
    }


def get_animation_data(
    data_frame,
    x_key,
    y_key,
    z_key,
    x_ref=None,
    y_ref=None,
    frame_key="Frame",
    img_list=None,
    colormap=None,
    decay=0,
    **kwargs
):
    """
    Generate the animation data, frames, and layout.

    Parameters:
    - data_frame (pd.DataFrame): The data frame containing the data.
    - x_key (str): The key for the x-axis data.
    - y_key (str): The key for the y-axis data.
    - z_key (str): The key for the z-axis data.
    - x_ref (str): The key for the x-axis reference data.
    - y_ref (str): The key for the y-axis reference data.
    - frame_key (str): The key for the frame data.
    - img_list (list): The list of image file paths for each frame.
    - colormap (str): The name of the colormap for the color data.
    - decay (int): The number of frames to decay the opacity.
    - **kwargs: Additional keyword arguments for customization.

    Returns:
    - dict: The animation data, frames, and layout.
    """
    ani_frames = []
    frame_list = data_frame[frame_key].unique()
    opacity = np.linspace(1, 0.2, decay + 1)

    for idx, frame_idx in enumerate(frame_list):
        if idx < decay:
            continue

        filtered_list = data_frame[data_frame[frame_key] == frame_idx]
        filtered_list = filtered_list.reset_index()

        if img_list is not None:
            try:
                with open(img_list[idx], "rb") as img_file:
                    encoded_image = base64.b64encode(img_file.read())
                kwargs["image"] = "data:image/jpeg;base64," + encoded_image.decode()
            except FileNotFoundError:
                kwargs["image"] = None
            except NotADirectoryError:
                kwargs["image"] = None
        else:
            kwargs["image"] = None

        kwargs["name"] = "Frame: " + str(frame_idx)
        fig = get_scatter3d_data(
            filtered_list,
            x_key,
            y_key,
            z_key,
            x_ref=x_ref,
            y_ref=y_ref,
            opacity=opacity[0],
            **kwargs
        )
        hover_list = get_hover_strings(
            filtered_list, kwargs["c_key"], kwargs["c_type"], kwargs["keys_dict"]
        )

        if hover_list:
            for hover_idx, hover_str in enumerate(hover_list):
                fig[hover_idx]["text"] = hover_str
                fig[hover_idx]["hovertemplate"] = "%{text}"

        if colormap is not None and "marker" in fig[0]:
            fig[0]["marker"]["colorscale"] = colormap

        if decay > 0:
            for val in range(1, decay + 1):
                if (idx - val) >= 0:
                    # filter the data
                    frame_temp = data_frame[
                        data_frame[frame_key] == frame_list[idx - val]
                    ]
                    frame_temp = frame_temp.reset_index()

                    kwargs["name"] = "Frame: " + str(frame_list[idx - val])
                    new_fig = get_scatter3d_data(
                        frame_temp,
                        x_key,
                        y_key,
                        z_key,
                        x_ref=x_ref,
                        y_ref=y_ref,
                        opacity=opacity[val],
                        **kwargs
                    )
                    hover_list = get_hover_strings(
                        frame_temp,
                        kwargs["c_key"],
                        kwargs["c_type"],
                        kwargs["keys_dict"],
                    )

                    if hover_list:
                        for hover_idx, hover_str in enumerate(hover_list):
                            new_fig[hover_idx]["text"] = hover_str
                            new_fig[hover_idx]["hovertemplate"] = "%{text}"

                    if colormap is not None and "marker" in new_fig[0]:
                        new_fig[0]["marker"]["colorscale"] = colormap

                    fig = fig + new_fig

                else:
                    break

        if x_ref is not None and y_ref is not None:
            fig_ref = [
                get_ref_scatter3d_data(
                    data_frame=filtered_list,
                    x_key=x_ref,
                    y_key=y_ref,
                    z_key=None,
                    name="Host Vehicle",
                )
            ]
        else:
            fig_ref = []
        layout = get_scatter3d_layout(**kwargs)

        new_frame = {"data": fig_ref + fig, "layout": layout}

        # need 'name' to make sure animation works properly
        new_frame["name"] = str(frame_idx)
        ani_frames.append(new_frame)

    sliders = [
        {
            "pad": {"b": 10, "t": 10},
            "len": 0.9,
            "x": 0.1,
            "y": 0,
            "steps": [
                {
                    "args": [[f["name"]], frame_args(0)],
                    "label": str(k),
                    "method": "animate",
                }
                for k, f in enumerate(ani_frames)
            ],
        }
    ]

    if img_list is not None:
        try:
            encoded_image = base64.b64encode(open(img_list[0], "rb").read())
            kwargs["image"] = "data:image/jpeg;base64," + encoded_image.decode()
        except FileNotFoundError:
            kwargs["image"] = None
        except NotADirectoryError:
            kwargs["image"] = None
    else:
        kwargs["image"] = None

    # Layout
    figure_layout = get_scatter3d_layout(**kwargs)
    figure_layout["updatemenus"] = [
        {
            "bgcolor": "#9E9E9E",
            "font": {"size": 10, "color": "#455A64"},
            "buttons": [
                {
                    "args": [None, frame_args(5)],
                    "label": "Play",  # play symbol
                    "method": "animate",
                },
                {
                    "args": [[None], frame_args(0)],
                    "label": "Stop",  # pause symbol
                    "method": "animate",
                },
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 30, "l": 20, "b": 10},
            "type": "buttons",
            "x": 0.1,
            "xanchor": "right",
            "y": 0,
            "yanchor": "top",
        }
    ]
    figure_layout["sliders"] = sliders

    return {
        "data": ani_frames[0]["data"],
        "frames": ani_frames,
        "layout": figure_layout,
    }
