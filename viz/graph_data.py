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


def get_scatter3d_data(data_frame,
                       x_key,
                       y_key,
                       z_key,
                       c_key,
                       **kwargs):

    if data_frame.shape[0] == 0:
        return [{'mode': 'markers', 'type': 'scatter3d',
                'x': [], 'y': [], 'z': []}]

    linewidth = kwargs.get('linewidth', 0)
    c_label = kwargs.get('c_label', c_key)
    colormap = kwargs.get('colormap', 'Jet')
    name = kwargs.get('name', None)
    hover = kwargs.get('hover', None)
    c_type = kwargs.get('c_type', 'numerical')

    if c_type == 'numerical':
        color = data_frame[c_key]
        c_range = kwargs.get('c_range', [np.min(color), np.max(color)])
        if c_range is None:
            c_range = [np.min(color), np.max(color)]

        if hover is not None:
            rows = len(data_frame.index)
            hover_str = np.full(rows, '', dtype=object)
            for _, key in enumerate(hover):
                if 'format' in hover[key]:
                    hover_str = hover_str + hover[key]['description'] + \
                        ': ' + data_frame[key].map(
                        hover[key]['format'].format)+'<br>'
                else:
                    hover_str = hover_str + hover[key]['description'] + \
                        ': ' + data_frame[key].apply(str)+'<br>'
            hovertemplate = '%{text}'
        else:
            hover_str = None
            hovertemplate = None

        fig_data = [
            dict(
                type='scatter3d',
                ids=data_frame.index,
                x=data_frame[x_key],
                y=data_frame[y_key],
                z=data_frame[z_key],
                text=hover_str,
                hovertemplate=hovertemplate,
                mode='markers',
                name=name,
                marker=dict(
                    size=3,
                    color=color,
                    colorscale=colormap,
                    opacity=0.8,
                    colorbar=dict(
                        title=c_label,
                    ),
                    cmin=c_range[0],
                    cmax=c_range[1],
                    line=dict(
                        color="#757575",
                        width=linewidth,
                    )
                ),
            )]
    elif c_type == 'categorical':
        fig_data = []
        color_list = pd.unique(data_frame[c_key])

        for c_item in color_list:
            new_list = data_frame[data_frame[c_key] == c_item]

            if hover is not None:
                rows = len(new_list.index)
                hover_str = np.full(rows, '', dtype=object)
                for _, key in enumerate(hover):
                    if 'format' in hover[key]:
                        hover_str = hover_str + hover[key]['description'] + \
                            ': ' + new_list[key].map(
                                hover[key]['format'].format)+'<br>'
                    else:
                        hover_str = hover_str + hover[key]['description'] + \
                            ': ' + new_list[key].apply(str)+'<br>'
                hovertemplate = '%{text}'
            else:
                hover_str = None
                hovertemplate = None

            fig_data.append(
                dict(
                    type='scatter3d',
                    ids=new_list.index,
                    x=new_list[x_key],
                    y=new_list[y_key],
                    z=new_list[z_key],
                    text=hover_str,
                    hovertemplate='%{text}',
                    mode='markers',
                    name=c_item,
                    marker=dict(
                        size=3,
                        opacity=0.8,
                        line=dict(
                            color="#757575",
                            width=linewidth,
                        )
                    ),
                )
            )

    return fig_data


def get_ref_scatter3d_data(data_frame,
                           x_key,
                           y_key,
                           z_key=None,
                           name=None):

    if data_frame.shape[0] == 0:
        return {'mode': 'markers', 'type': 'scatter3d',
                'x': [], 'y': [], 'z': []}

    if z_key is None:
        z_data = [0]
    else:
        z_data = [data_frame[z_key].iloc[0]]

    fig_data = dict(
        type='scatter3d',
        x=[data_frame[x_key].iloc[0]],
        y=[data_frame[y_key].iloc[0]],
        z=z_data,
        hovertemplate='Lateral: %{x:.2f} m<br>' +
        'Longitudinal: %{y:.2f} m<br>',
        mode='markers',
        name=name,
        marker=dict(color='rgb(0, 0, 0)', size=6, opacity=0.8,
                    symbol='circle')
    )

    return fig_data
