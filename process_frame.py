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

import numpy as np

from utils import filter_all
from utils import cache_get
from utils import load_data
from utils import load_image
from utils import prepare_figure_kwargs

from viz.viz import get_scatter3d
from viz.graph_data import get_ref_scatter3d_data
from viz.graph_data import get_scatter3d_data
from viz.graph_layout import get_scatter3d_layout

from app_config import CACHE_KEYS

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
    img_path = os.path.join(
        file["path"], file["name"][0:-4], str(frame_list[frame_idx]) + ".jpg"
    )

    # encode image frame
    fig_kwargs["image"] = load_image(img_path)

    # get a single frame data from Redis
    data = cache_get(session_id, CACHE_KEYS["frame_data"], str(frame_list[frame_idx]))

    filterd_frame = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )

    result = get_scatter3d_data(filterd_frame, hover=keys_dict, **fig_kwargs)
    fig = result["scatter_data"]
    hover_list = result["hover_strings"]

    if load_hover and hover_list:
        for idx, hover_str in enumerate(hover_list):
            fig[idx]["text"] = hover_str
            fig[idx]["hovertemplate"] = "%{text}"

    if fig_kwargs["c_type"] == "numerical":
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

                result = get_scatter3d_data(frame_temp, hover=keys_dict, **fig_kwargs)
                new_fig = result["scatter_data"]
                hover_list = result["hover_strings"]

                if load_hover and hover_list:
                    for idx, hover_str in enumerate(hover_list):
                        new_fig[idx]["text"] = hover_str
                        new_fig[idx]["hovertemplate"] = "%{text}"

                if fig_kwargs["c_type"] == "numerical":
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
    data = load_data(file_list, file)
    filterd_frame = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )
    fig_kwargs["image"] = None

    # generate the graph
    fig = get_scatter3d(filterd_frame, hover=config["keys"], **fig_kwargs)

    if fig_kwargs["c_type"] == "numerical":
        if "marker" in fig["data"][0]:
            fig["data"][0]["marker"]["colorscale"] = colormap

    return fig
