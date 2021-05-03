"""

    Copyright (C) 2019 - 2021  Zhengyu Peng
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

from .graph_data import get_scatter3d_data, get_ref_scatter3d_data
from .graph_layout import get_scatter3d_layout

import base64


def get_scatter3d(data_frame,
                  x_key,
                  y_key,
                  z_key,
                  c_key,
                  x_ref=None,
                  y_ref=None,
                  z_ref=None,
                  **kwargs):
    """
    Get scatter 3D data

    :param pandas.DataFrame data_frame:
        DataFrame
    :param str x_key:
        Key name for x axis
    :param str y_key:
        Key name for y axis
    :param str z_key:
        Key name for z axis
    :param str c_key:
        Key name for color
    :param str x_ref:
        Key name for x reference point
    :param str y_ref:
        Key name for y reference point
    :param str z_ref:
        Key name for z reference point

    :return: plotly Scatter 3D
    :rtype: dict
    """
    ref_name = kwargs.get('ref_name', None)

    if x_ref is None or y_ref is None:
        data = get_scatter3d_data(
            data_frame,
            x_key,
            y_key,
            z_key,
            c_key,
            **kwargs
        )
    else:
        data = get_scatter3d_data(
            data_frame,
            x_key,
            y_key,
            z_key,
            c_key,
            **kwargs
        )+[get_ref_scatter3d_data(
            data_frame=data_frame,
            x_key=x_ref,
            y_key=y_ref,
            z_key=z_ref,
            name=ref_name
        )]

    return dict(
        data=data,
        layout=get_scatter3d_layout(**kwargs)
    )


def get_histogram(data_frame,
                  x_key,
                  x_label=None,
                  histnorm='probability',
                  margin={'l': 40, 'r': 40, 'b': 40, 't': 60}
                  ):
    if x_label is None:
        x_label = x_key

    if histnorm == 'probability':
        y_label = 'Probability'
    else:
        y_label = 'Count'

    return dict(
        data=[dict(
            type='histogram',
            x=data_frame[x_key],
            histnorm=histnorm,
            opacity=0.75,
        )],
        layout=dict(
            barmode='overlay',
            xaxis=dict(title=x_label),
            yaxis=dict(title=y_label),
            margin=margin,
            uirevision='no_change',
        )
    )


def get_heatmap(data_frame,
                x_key,
                y_key,
                x_label=None,
                y_label=None,
                margin={'l': 40, 'r': 40, 'b': 40, 't': 60}
                ):
    if x_label is None:
        x_label = x_key

    if y_label is None:
        y_label = y_key

    return dict(
        data=[dict(
            type='histogram2dcontour',
            x=data_frame[x_key],
            y=data_frame[y_key],
            colorscale='Jet'
        )],
        layout=dict(
            xaxis=dict(title=x_label),
            yaxis=dict(title=y_label),
            margin=margin,
            uirevision='no_change',
        )
    )


def get_scatter2d(data_frame,
                  x_key,
                  y_key,
                  c_key,
                  x_label=None,
                  y_label=None,
                  uirevision='no_change',
                  colormap='Jet',
                  margin={'l': 40, 'r': 40, 'b': 40, 't': 60},
                  is_discrete_color=False,
                  **kwargs):

    linewidth = kwargs.get('linewidth', 0)

    if x_label is None:
        x_label = x_key

    if y_label is None:
        y_label = y_key

    c_label = kwargs.get('c_label', c_key)

    if not is_discrete_color:
        return dict(
            data=[dict(
                type='scattergl',
                ids=data_frame.index,
                x=data_frame[x_key],
                y=data_frame[y_key],
                mode='markers',
                marker=dict(
                    size=6,
                    color=data_frame[c_key],
                    colorscale=colormap,
                    opacity=0.8,
                    colorbar=dict(
                        title=c_label,
                    ),
                    line=dict(
                        color="#FFFFFF",
                        width=linewidth,
                    )
                )
            )],
            layout=dict(
                xaxis=dict(title=x_label),
                yaxis=dict(title=y_label),
                margin=margin,
                uirevision=uirevision,
            )
        )
    else:
        data = []
        color_list = pd.unique(data_frame[c_key])
        for c_item in color_list:
            new_list = data_frame[data_frame[c_key] == c_item]
            data.append(
                dict(
                    type='scattergl',
                    ids=new_list.index,
                    x=new_list[x_key],
                    y=new_list[y_key],
                    mode='markers',
                    marker=dict(
                        size=6,
                        opacity=0.8,
                        line=dict(
                            color="#FFFFFF",
                            width=linewidth,
                        )
                    ),
                    name=c_item
                )
            )
        return dict(
            data=data,
            layout=dict(
                xaxis=dict(title=x_label),
                yaxis=dict(title=y_label),
                margin=margin,
                uirevision=uirevision,
            )
        )


def frame_args(duration):
    return {
        'frame': {'duration': duration},
        'mode': 'immediate',
        'fromcurrent': True,
        'transition': {'duration': duration, 'easing': 'quadratic-in-out'},
    }


def get_animation_data(data_frame,
                       x_key,
                       y_key,
                       z_key,
                       host_x_key,
                       host_y_key,
                       img_list=None,
                       **kwargs):

    x_range = [np.min([np.min(data_frame[x_key]),
                       np.min(data_frame[host_x_key])]),
               np.max([np.max(data_frame[x_key]),
                       np.max(data_frame[host_x_key])])]
    y_range = [np.min([np.min(data_frame[y_key]),
                       np.min(data_frame[host_y_key])]),
               np.max([np.max(data_frame[y_key]),
                       np.max(data_frame[host_y_key])])]
    z_range = [np.min(data_frame[z_key]),
               np.max(data_frame[z_key])]
    c_range = [np.min(data_frame[kwargs.get('c_key')]),
               np.max(data_frame[kwargs.get('c_key')])]

    ani_frames = []
    frame_list = data_frame['Frame'].unique()

    for idx, frame_idx in enumerate(frame_list):
        filtered_list = data_frame[data_frame['Frame'] == frame_idx]
        filtered_list = filtered_list.reset_index()

        if img_list is not None:
            try:
                encoded_image = base64.b64encode(
                    open(img_list[idx], 'rb').read())
                img = 'data:image/jpeg;base64,{}'.format(
                    encoded_image.decode())
            except FileNotFoundError:
                img = None
        else:
            img = None

        new_frame = get_scatter3d(
            filtered_list,
            x_key,
            y_key,
            z_key,
            x_ref=host_x_key,
            y_ref=host_y_key,
            name='Frame: '+str(frame_idx),
            ref_name='Host Vehicle',
            x_range=x_range,
            y_range=y_range,
            z_range=z_range,
            c_range=c_range,
            image=img,
            **kwargs)
        # need 'name' to make sure animation works properly
        new_frame['name'] = str(frame_idx)
        ani_frames.append(new_frame)

    sliders = [
        {
            'pad': {'b': 10, 't': 10},
            'len': 0.9,
            'x': 0.1,
            'y': 0,
            'steps': [
                {
                    'args': [[f['name']], frame_args(0)],
                    'label': str(k),
                    'method': 'animate',
                }
                for k, f in enumerate(ani_frames)
            ],
        }
    ]

    if img_list is not None:
        try:
            encoded_image = base64.b64encode(open(img_list[0], 'rb').read())
            img = 'data:image/jpeg;base64,{}'.format(
                encoded_image.decode())
        except FileNotFoundError:
            img = None
    else:
        img = None

    # Layout
    figure_layout = get_scatter3d_layout(
        x_range,
        y_range,
        z_range,
        image=img,
        **kwargs
    )
    figure_layout['updatemenus'] = [
        {
            'bgcolor': '#9E9E9E',
            'font': {'size': 10, 'color': '#455A64'},
            'buttons': [
                {
                    'args': [None, frame_args(50)],
                    'label': '&#9654;',  # play symbol
                    'method': 'animate',
                },
                {
                    'args': [[None], frame_args(0)],
                    'label': '&#9208;',  # pause symbol
                    'method': 'animate',
                },
            ],
            'direction': 'left',
            'pad': {'r': 10, 't': 30, 'l': 20, 'b': 10},
            'type': 'buttons',
            'x': 0.1,
            'xanchor': 'right',
            'y': 0,
            'yanchor': 'top'
        }
    ]
    figure_layout['sliders'] = sliders

    return dict(data=[ani_frames[0]['data'][0], ani_frames[0]['data'][1]],
                frames=ani_frames,
                layout=figure_layout)
