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
import plotly.graph_objs as go
import plotly.io as pio

from .graph_data import get_scatter3d_data, get_ref_scatter3d_data
from .graph_layout import get_scatter3d_layout

import base64


def get_scatter3d(det_list,
                  x,
                  y,
                  z,
                  x_ref,
                  y_ref,
                  layout,
                  keys_dict,
                  name,
                  linewidth=0,
                  colormap='Jet',
                  is_discrete_color=False,
                  image=None):

    return dict(
        data=get_scatter3d_data(
            det_list,
            x,
            y,
            z,
            layout['c_key'],
            c_label=layout['c_label'],
            linewidth=linewidth,
            name=name,
            hover=keys_dict,
            c_range=layout['c_range'],
            colormap=colormap,
            is_discrete_color=is_discrete_color
        )+[get_ref_scatter3d_data(
            data_frame=det_list,
            x_key=x_ref,
            y_key=y_ref,
        )],
        layout=get_scatter3d_layout(
            x_range=layout['x_range'],
            y_range=layout['y_range'],
            z_range=layout['z_range'],
            image=image)
    )


def get_histogram(data_frame,
                  x_key,
                  x_label=None,
                  histnorm='probability',
                  margin=dict(l=40, r=40, b=40, t=60)
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
                margin=dict(l=40, r=40, b=40, t=60)
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
                  margin=dict(l=40, r=40, b=40, t=60),
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
                       c_key=None,
                       hover=None,
                       c_range=[-30, 30],
                       db=False,
                       colormap='Viridis',
                       title=None,
                       height=650,
                       template='plotly',
                       image_dir=None):

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

    if c_key is not None:
        c_range = [np.min(data_frame[c_key]),
                   np.max(data_frame[c_key])]

    ani_frames = []
    frame_list = data_frame['Frame'].unique()

    for idx, frame_idx in enumerate(frame_list):
        filtered_list = data_frame[data_frame['Frame'] == frame_idx]
        filtered_list = filtered_list.reset_index()

        if image_dir is not None:
            try:
                encoded_image = base64.b64encode(
                    open(image_dir[idx], 'rb').read())
                img = 'data:image/png;base64,{}'.format(
                    encoded_image.decode())
            except FileNotFoundError:
                img = None
        else:
            img = None

        ani_frames.append(
            dict(
                data=[
                    get_scatter3d_data(
                        filtered_list,
                        x_key,
                        y_key,
                        z_key,
                        c_key,
                        c_label=c_key,
                        name='Frame: '+str(frame_idx),
                        hover=hover,
                        c_range=c_range,
                        db=db,
                        colormap=colormap),
                    get_ref_scatter3d_data(
                        filtered_list,
                        host_x_key,
                        host_y_key)
                ],
                layout=get_scatter3d_layout(
                    x_range,
                    y_range,
                    z_range,
                    height=height,
                    title=title,
                    margin=dict(l=0, r=0, b=0, t=40),
                    template=template,
                    image=img
                ),
                # need to name the frame for the animation to behave properly
                name=str(frame_idx)
            )
        )

    sliders = [
        {
            'pad': {'b': 10, 't': 40},
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

    if image_dir is not None:
        try:
            encoded_image = base64.b64encode(open(image_dir[0], 'rb').read())
            img = 'data:image/png;base64,{}'.format(
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
        height=height,
        title=title,
        margin=dict(l=0, r=0, b=0, t=40),
        template=template,
        image=img
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
            'pad': {'r': 10, 't': 50, 'l': 20},
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
