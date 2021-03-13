"""

    Copyright (C) 2019 - 2020  Zhengyu Peng
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


def get_figure_data(det_list,
                    x_key,
                    y_key,
                    z_key,
                    color_key,
                    color_label=None,
                    name=None,
                    hover_dict=None,
                    c_range=[-30, 30],
                    db=False,
                    colormap='Jet',):

    if det_list.shape[0] > 0:
        color = det_list[color_key]
        if db:
            color = 20*np.log10(color)

        rows = len(det_list.index)

        hover = np.full(rows, '', dtype=object)

        for idx, key in enumerate(hover_dict):
            if 'format' in hover_dict[key]:
                hover = hover + hover_dict[key]['description'] + ': ' + \
                    det_list[hover_dict[key]['key']].map(
                        hover_dict[key]['format'].format)+'<br>'
            else:
                hover = hover + hover_dict[key]['description'] + \
                    ': ' + det_list[hover_dict[key]['key']]+'<br>'

        if '_IDS_' in det_list.columns:
            ids = det_list['_IDS_']
        else:
            ids = None

        det_map = dict(
            type='scatter3d',
            ids=ids,
            x=det_list[x_key],
            y=det_list[y_key],
            z=det_list[z_key],
            text=hover,
            hovertemplate='%{text}',
            # +'Lateral: %{x:.2f} m<br>' +
            # 'Longitudinal: %{y:.2f} m<br>'+'Height: %{z:.2f} m<br>',
            mode='markers',
            name=name,
            marker=dict(
                size=3,
                color=color,
                colorscale=colormap,
                opacity=0.8,
                colorbar=dict(
                    title=color_label,
                ),
                cmin=c_range[0],
                cmax=c_range[1],
            ),
        )

        return det_map
    else:
        return {'mode': 'markers', 'type': 'scatter3d',
                'x': [], 'y': [], 'z': []}


def get_host_data(det_list,
                  x_key,
                  y_key,
                  name='Host'):

    if det_list.shape[0] > 0:

        vel_map = dict(
            type='scatter3d',
            x=[det_list[x_key][0]],
            y=[det_list[y_key][0]],
            z=[0],
            hovertemplate='Lateral: %{x:.2f} m<br>' +
            'Longitudinal: %{y:.2f} m<br>',
            mode='markers',
            name=name,
            marker=dict(color='rgb(255, 255, 255)', size=6, opacity=0.8,
                        symbol='circle')
        )

        return vel_map
    else:
        return {'mode': 'markers', 'type': 'scatter3d',
                'x': [], 'y': [], 'z': []}


def get_figure_layout(
    x_range,
    y_range,
    z_range=[-20, 20],
    height=650,
    title=None,
    margin=dict(l=0, r=0, b=0, t=20)
):
    scale = np.min([x_range[1]-x_range[0], y_range[1] -
                    y_range[0], z_range[1]-z_range[0]])
    return dict(
        title=title,
        # template=pio.templates['plotly_dark'],
        template=pio.templates['plotly'],
        height=height,
        scene=dict(xaxis=dict(range=x_range,
                              title='Lateral (m)',
                              autorange=False),
                   yaxis=dict(range=y_range,
                              title='Longitudinal (m)', autorange=False),
                   zaxis=dict(range=z_range,
                              title='Height (m)', autorange=False),
                   aspectmode='manual',
                   aspectratio=dict(x=(x_range[1]-x_range[0])/scale,
                                    y=(y_range[1]-y_range[0])/scale,
                                    z=(z_range[1]-z_range[0])/scale),
                   ),
        margin=margin,
        legend=dict(x=0, y=0),
        uirevision='no_change',
    )


def get_histogram(det_list,
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
            x=det_list[x_key],
            histnorm=histnorm,
            opacity=0.75,
        )],
        layout=dict(
            barmode='overlay',
            xaxis=dict(title=x_label),
            yaxis=dict(title=y_label),
            margin=margin,
            # xaxis_title_text=x_label,  # xaxis label
            # yaxis_title_text=y_label,  # yaxis label
            uirevision='no_change',
        )
    )


def get_heatmap(det_list,
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
            x=det_list[x_key],
            y=det_list[y_key],
            colorscale='Jet'
        )],
        layout=dict(
            xaxis=dict(title=x_label),
            yaxis=dict(title=y_label),
            margin=margin,
            # xaxis_title_text=x_label,  # xaxis label
            # yaxis_title_text=y_label,  # yaxis label
            uirevision='no_change',
        )
    )


def get_2d_scatter(det_list,
                   x_key,
                   y_key,
                   color_key,
                   x_label=None,
                   y_label=None,
                   color_label=None,
                   uirevision='no_change',
                   colormap='Rainbow',
                   margin=dict(l=40, r=40, b=40, t=60)):

    if x_label is None:
        x_label = x_key

    if y_label is None:
        y_label = y_key

    if color_label is None:
        color_label = color_key

    return dict(
        data=[dict(
            type='scattergl',
            ids=det_list['_IDS_'],
            x=det_list[x_key],
            y=det_list[y_key],
            mode='markers',
            marker=dict(
                size=5,
                color=det_list[color_key],
                colorscale=colormap,
                opacity=0.8,
                colorbar=dict(
                    title=color_label,
                ),
                # cmin=c_range[0],
                # cmax=c_range[1],
            )
        )],
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


def get_animation_data(det_list,
                       x_key,
                       y_key,
                       z_key,
                       host_x_key,
                       host_y_key,
                       color_key=None,
                       hover_dict=None,
                       c_range=[-30, 30],
                       db=False,
                       colormap='Rainbow',
                       title=None,
                       height=650):

    x_range = [np.min([np.min(det_list[x_key]),
                       np.min(det_list[host_x_key])]),
               np.max([np.max(det_list[x_key]),
                       np.max(det_list[host_x_key])])]
    y_range = [np.min([np.min(det_list[y_key]),
                       np.min(det_list[host_y_key])]),
               np.max([np.max(det_list[y_key]),
                       np.max(det_list[host_y_key])])]
    z_range = [np.min(det_list[z_key]),
               np.max(det_list[z_key])]

    if color_key is not None:
        c_range = [np.min(det_list[color_key]),
                   np.max(det_list[color_key])]

    ani_frames = []
    frame_list = det_list['Frame'].unique()

    for frame_idx in frame_list:
        filtered_list = det_list[det_list['Frame'] == frame_idx]
        filtered_list = filtered_list.reset_index()

        ani_frames.append(
            dict(
                data=[
                    get_figure_data(
                        filtered_list,
                        x_key,
                        y_key,
                        z_key,
                        color_key,
                        color_label=color_key,
                        name='Frame: '+str(frame_idx),
                        hover_dict=hover_dict,
                        c_range=c_range,
                        db=db,
                        colormap=colormap),
                    get_host_data(
                        filtered_list,
                        host_x_key,
                        host_y_key)
                ],
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

    # camera = dict(
    #     up=dict(x=0, y=0, z=1),
    #     center=dict(x=0, y=0, z=0),
    #     eye=dict(x=0, y=-1.5, z=10),
    # )

    # Layout
    figure_layout = get_figure_layout(
        x_range,
        y_range,
        z_range,
        height=height,
        title=title,
        margin=dict(l=0, r=0, b=0, t=40)
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
    # fig.show()
    # fig.write_html(file_name[:-4]+'.html')
