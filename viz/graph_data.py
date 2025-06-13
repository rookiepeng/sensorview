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
    if hover is None or not hover:
        return []

    def format_series(series, hover_config):
        if "format" in hover_config:
            return series.map(hover_config["format"].format)
        if "decimal" in hover_config:
            format_str = "{:,." + str(hover_config["decimal"]) + "f}"
            return series.map(format_str.format)
        return series.astype(str)

    def process_dataframe(df, hover_dict):
        hover_parts = []
        for key, config in hover_dict.items():
            if key in df.columns:
                formatted_values = format_series(df[key], config)
                hover_parts.append(
                    config["description"] + ": " + formatted_values + "<br>"
                )
        return np.sum(hover_parts, axis=0) if hover_parts else np.full(len(df), "")

    if c_type == "numerical":
        return [process_dataframe(data_frame, hover).tolist()]

    if c_type == "categorical":
        # More efficient groupby implementation
        return [
            process_dataframe(group, hover).tolist()
            for _, group in data_frame.groupby(c_key)
        ]

    return []


def get_scatter3d_data(data_frame, x_key, y_key, z_key, c_key, **kwargs):
    """
    Generate the 3D scatter plot data with improved performance.
    """
    if data_frame.empty:
        return [{"mode": "markers", "type": "scatter3d", "x": [], "y": [], "z": []}]

    # Extract kwargs with defaults
    plot_config = {
        "c_label": kwargs.get("c_label", c_key),
        "name": kwargs.get("name", None),
        "c_type": kwargs.get("c_type", "numerical"),
        "opacity": kwargs.get("opacity", 0.8),
        "showlegend": kwargs.get("showlegend", True),
        "marker_size": 3,
        "line_color": "#757575",
        "line_width": 0,
    }

    def create_base_scatter(df, name=None):
        """Helper function to create base scatter dictionary"""
        return {
            "type": "scatter3d",
            "ids": df.index.tolist(),  # Using numpy arrays directly
            "x": df[x_key].tolist(),
            "y": df[y_key].tolist(),
            "z": df[z_key].tolist(),
            "mode": "markers",
            "name": name,
            "showlegend": plot_config["showlegend"],
        }

    if plot_config["c_type"] == "numerical":
        color_values = data_frame[c_key].tolist()
        c_range = kwargs.get("c_range", None) or [
            np.min(color_values),
            np.max(color_values),
        ]

        scatter_data = create_base_scatter(data_frame, plot_config["name"])
        scatter_data["marker"] = {
            "size": plot_config["marker_size"],
            "color": color_values,
            "opacity": plot_config["opacity"],
            "colorbar": {"title": plot_config["c_label"]},
            "cmin": c_range[0],
            "cmax": c_range[1],
            "line": {
                "color": plot_config["line_color"],
                "width": plot_config["line_width"],
            },
        }
        return [scatter_data]

    else:  # categorical
        # Use pandas groupby for more efficient categorical processing
        grouped = data_frame.groupby(c_key)
        return [
            {
                **create_base_scatter(group, str(name)),
                "marker": {
                    "size": plot_config["marker_size"],
                    "opacity": plot_config["opacity"],
                    "line": {
                        "color": plot_config["line_color"],
                        "width": plot_config["line_width"],
                    },
                },
            }
            for name, group in grouped
        ]


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
        z_data = [data_frame[z_key].iloc[0].tolist()]

    fig_data = dict(
        type="scatter3d",
        x=[data_frame[x_key].iloc[0].tolist()],
        y=[data_frame[y_key].iloc[0].tolist()],
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


def get_scatter3d_data_with_hover(
    data_frame, x_key, y_key, z_key, c_key, hover=None, **kwargs
):
    """
    Generate both 3D scatter plot data and hover strings in one pass.

    Parameters:
    - data_frame (pd.DataFrame): The data frame containing the data
    - x_key (str): The key for x-axis data
    - y_key (str): The key for y-axis data
    - z_key (str): The key for z-axis data
    - c_key (str): The key for color data
    - hover (dict): Hover configuration dictionary
    - **kwargs: Additional configuration parameters

    Returns:
    - dict: Dictionary containing scatter data and hover strings
    """
    if data_frame.empty:
        return {
            "scatter_data": [
                {"mode": "markers", "type": "scatter3d", "x": [], "y": [], "z": []}
            ],
            "hover_strings": [],
        }

    plot_config = {
        "c_label": hover[c_key]["description"] if hover and c_key in hover else c_key,
        "name": kwargs.get("name", None),
        "c_type": (
            hover[c_key]["type"]
            if hover and c_key in hover
            else kwargs.get("c_type", "numerical")
        ),
        "opacity": kwargs.get("opacity", 0.8),
        "showlegend": kwargs.get("showlegend", True),
        "marker_size": 3,
        "line_color": "#757575",
        "line_width": 0,
    }

    def format_hover(series, config):
        if "format" in config:
            return series.map(config["format"].format)
        if "decimal" in config:
            format_str = "{:,." + str(config["decimal"]) + "f}"
            return series.map(format_str.format)
        return series.astype(str)

    def process_hover(df):
        if not hover:
            return np.full(len(df), "")
        hover_parts = []
        for key, config in hover.items():
            if key in df.columns:
                formatted_values = format_hover(df[key], config)
                hover_parts.append(
                    config.get("description", key) + ": " + formatted_values + "<br>"
                )
        return np.sum(hover_parts, axis=0) if hover_parts else np.full(len(df), "")

    def create_scatter(df, name=None, color=None):
        scatter = {
            "type": "scatter3d",
            "ids": df.index.tolist(),
            "x": df[x_key].tolist(),
            "y": df[y_key].tolist(),
            "z": df[z_key].tolist(),
            "mode": "markers",
            "name": name,
            "showlegend": plot_config["showlegend"],
        }

        marker = {
            "size": plot_config["marker_size"],
            "opacity": plot_config["opacity"],
            "line": {
                "color": plot_config["line_color"],
                "width": plot_config["line_width"],
            },
        }

        if color is not None:
            marker.update(
                {
                    "color": color,
                    "colorbar": {"title": plot_config["c_label"]},
                    "cmin": kwargs.get("c_range", [np.min(color), np.max(color)])[0],
                    "cmax": kwargs.get("c_range", [np.min(color), np.max(color)])[1],
                }
            )

        scatter["marker"] = marker
        return scatter

    result = {"scatter_data": [], "hover_strings": []}

    if plot_config["c_type"] == "numerical":
        hover_text = process_hover(data_frame)
        color_values = data_frame[c_key].tolist()
        result["scatter_data"] = [
            create_scatter(data_frame, plot_config["name"], color_values)
        ]
        result["hover_strings"] = [hover_text.tolist()]
    else:
        grouped = data_frame.groupby(c_key)
        for name, group in grouped:
            hover_text = process_hover(group)
            result["scatter_data"].append(create_scatter(group, str(name)))
            result["hover_strings"].append(hover_text.tolist())

    return result
