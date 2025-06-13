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

from typing import List, Dict, Union, Any, Optional
import numpy as np
import pandas as pd


def get_ref_scatter3d_data(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: Optional[str] = None,
    name: str = "Origin",
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Generate the reference scatter plot data with improved performance.

    Parameters:
    - data_frame (pd.DataFrame): The data frame containing the data.
    - x_key (str): The key for the x-axis data.
    - y_key (str): The key for the y-axis data.
    - z_key (str): The key for the z-axis data (optional).
    - name (str): The name of the reference data.
    - **kwargs: Additional keyword arguments for customization.

    Returns:
    - dict: The reference scatter plot data.
    """
    if data_frame.empty:
        return {"mode": "markers", "type": "scatter3d", "x": [], "y": [], "z": []}

    # Direct value access for first row
    x_val = float(data_frame[x_key].iloc[0])
    y_val = float(data_frame[y_key].iloc[0])
    z_val = 0 if z_key is None else float(data_frame[z_key].iloc[0])

    # Create marker configuration once
    marker_config = {
        "color": "rgb(255, 255, 255)",
        "size": 6,
        "opacity": 1,
        "symbol": "circle",
        "line": {
            "color": "#000000",
            "width": 2,
        },
    }

    # Construct the figure data directly
    fig_data = {
        "type": "scatter3d",
        "x": [x_val],
        "y": [y_val],
        "z": [z_val],
        "hovertemplate": "Lateral: %{x:.2f} m<br>Longitudinal: %{y:.2f} m<br>",
        "mode": "markers",
        "name": name,
        "marker": marker_config,
    }

    return fig_data


def get_scatter3d_data(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: str,
    c_key: str,
    hover: Optional[Dict[str, Dict[str, Any]]] = None,
    **kwargs: Any
) -> Dict[str, Union[List[Dict[str, Any]], List[List[str]]]]:
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

    def format_hover(series: pd.Series, config: Dict[str, Any]) -> pd.Series:
        if "format" in config:
            return series.map(config["format"].format)
        if "decimal" in config:
            format_str = "{:,." + str(config["decimal"]) + "f}"
            return series.map(format_str.format)
        return series.astype(str)

    def process_hover(df: pd.DataFrame) -> np.ndarray:
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

    def create_scatter(
        df: pd.DataFrame,
        name: Optional[str] = None,
        color: Optional[Union[List[float], np.ndarray]] = None,
    ) -> Dict[str, Any]:
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
