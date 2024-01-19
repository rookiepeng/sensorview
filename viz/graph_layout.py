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

import plotly.io as pio


def get_scatter3d_layout(x_range, y_range, z_range=[-20, 20], **kwargs):
    """
    Generate the layout for the 3D scatter plot.

    Parameters:
    - x_range (list): The range of the x-axis.
    - y_range (list): The range of the y-axis.
    - z_range (list): The range of the z-axis.
    - **kwargs: Additional keyword arguments for customization.

    Returns:
    - dict: The layout for the 3D scatter plot.
    """
    scale = np.min(
        [x_range[1] - x_range[0], y_range[1] - y_range[0], z_range[1] - z_range[0]]
    )

    # height = kwargs.get('height', 650)
    image = kwargs.get("image", None)
    title = kwargs.get("title", None)
    template = kwargs.get("template", "plotly")

    x_label = kwargs.get("x_label", None)
    y_label = kwargs.get("y_label", None)
    z_label = kwargs.get("z_label", None)

    if image is not None:
        img_dict = [
            dict(
                source=image,
                xref="x domain",
                yref="y domain",
                x=0,
                y=1,
                xanchor="left",
                yanchor="top",
                sizex=0.3,
                sizey=0.3,
            )
        ]
    else:
        img_dict = None

    return dict(
        title=title,
        template=pio.templates[template],
        # height=height,
        scene=dict(
            xaxis=dict(range=x_range, title=x_label, autorange=False),
            yaxis=dict(range=y_range, title=y_label, autorange=False),
            zaxis=dict(range=z_range, title=z_label, autorange=False),
            aspectmode="manual",
            aspectratio=dict(
                x=(x_range[1] - x_range[0]) / scale,
                y=(y_range[1] - y_range[0]) / scale,
                z=(z_range[1] - z_range[0]) / scale,
            ),
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        legend=dict(x=0, y=0),
        images=img_dict,
        uirevision="no_change",
    )
