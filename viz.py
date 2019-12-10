import numpy as np
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio


def get_figure_data(det_list,
                    color_assign='Speed',
                    c_range=[-30, 30],
                    db=False, colormap='Rainbow'):
    if det_list.shape[0] > 0:
        color = det_list[color_assign]
        if db:
            color = 20*np.log10(color)

        frame_list = det_list['Frame']

        hover = np.zeros_like(frame_list, dtype=object)
        hover = 'Frame: ' +\
            det_list['Frame'].map('{:,.0f}'.format) +\
                '<br>Amp: ' +\
            det_list['Amplitude'].map('{:,.2f}'.format) +\
                ' dB<br>RCS: ' +\
            det_list['RCS'].map('{:,.2f}'.format) +\
                ' dB<br>SNR: ' +\
            det_list['SNR'].map('{:,.2f}'.format) +\
                ' dB<br>Az: ' +\
            det_list['Azimuth'].map('{:,.2f}'.format) +\
                ' deg<br>El: ' +\
            det_list['Elevation'].map('{:,.2f}'.format) +\
                ' deg<br>Range: ' +\
            det_list['Range'].map('{:,.2f}'.format) +\
                ' m<br>Speed: ' +\
            det_list['Speed'].map('{:,.2f}'.format) +\
                ' m/s<br>LookType: ' +\
            det_list['LookName']+'<br>'

        det_map = dict(
            type='scatter3d',
            x=det_list['Latitude'],
            y=det_list['Longitude'],
            z=det_list['Height'],
            text=hover,
            hovertemplate='%{text}'+'Lateral: %{x:.2f} m<br>' +
            'Longitudinal: %{y:.2f} m<br>'+'Height: %{z:.2f} m<br>',
            mode='markers',
            name='Frame: '+str(int(frame_list[0])),
            marker=dict(
                size=3,
                color=color,
                colorscale=colormap,
                opacity=0.8,
                colorbar=dict(
                    title=color_assign,
                ),
                cmin=c_range[0],
                cmax=c_range[1],
            ),
        )

        vel_map = dict(
            type='scatter3d',
            x=[det_list['VehLat'][0]],
            y=[det_list['VehLong'][0]],
            z=[0],
            hovertemplate='Lateral: %{x:.2f} m<br>' +
            'Longitudinal: %{y:.2f} m<br>',
            mode='markers',
            name='Vehicle',
            marker=dict(color='rgb(255, 255, 255)', size=6, opacity=0.8,
                        symbol='circle')
        )

        return [det_map, vel_map]
    else:
        return [{'mode': 'markers', 'type': 'scatter3d',
                 'x': [], 'y': [], 'z': []}]


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
        template=pio.templates['plotly_dark'],
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


def get_figure(det_list,
               x_range,
               y_range,
               z_range=[-20, 20],
               color_assign='Speed',
               c_range=[-30, 30],
               db=False,
               height=650):
    data = get_figure_data(
        det_list=det_list,
        color_assign=color_assign,
        c_range=c_range,
        db=db
    )
    layout = get_figure_layout(
        x_range=x_range, y_range=y_range, z_range=z_range, height=height)

    return dict(data=data, layout=layout)


def frame_args(duration):
    return {
        "frame": {"duration": duration},
        "mode": "immediate",
        "fromcurrent": True,
        "transition": {"duration": duration, "easing": "quadratic-in-out"},
    }


def get_animation_data(det_list,
                       color_assign='Speed',
                       db=False,
                       colormap='Rainbow',
                       title=None,
                       height=650):

    x_range = [np.min([np.min(det_list['Latitude']),
                       np.min(det_list['VehLat'])]),
               np.max([np.max(det_list['Latitude']),
                       np.max(det_list['VehLat'])])]
    y_range = [np.min([np.min(det_list['Longitude']),
                       np.min(det_list['VehLong'])]),
               np.max([np.max(det_list['Longitude']),
                       np.max(det_list['VehLong'])])]
    z_range = [np.min(det_list['Height']),
               np.max(det_list['Height'])]
    # layout_params['color_assign'] = color_assign
    c_range = [np.min(det_list[color_assign]),
               np.max(det_list[color_assign])]

    ani_frames = []
    frame_list = det_list['Frame'].unique()

    for frame_idx in frame_list:
        filtered_list = det_list[det_list['Frame'] == frame_idx]
        filtered_list = filtered_list.reset_index()

        ani_frames.append(
            dict(
                data=get_figure_data(
                    filtered_list,
                    color_assign=color_assign,
                    c_range=c_range,
                    db=db, colormap=colormap
                ),
                # need to name the frame for the animation to behave properly
                name=str(frame_idx)
            )
        )

    sliders = [
        {
            "pad": {"b": 10, "t": 40},
            "len": 0.9,
            "x": 0.1,
            "y": 0,
            "steps": [
                {
                    "args": [[f['name']], frame_args(0)],
                    "label": str(k),
                    "method": "animate",
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
            "buttons": [
                {
                    "args": [None, frame_args(50)],
                    "label": "&#9654;",  # play symbol
                    "method": "animate",
                },
                {
                    "args": [[None], frame_args(0)],
                    "label": "&#9208;",  # pause symbol
                    "method": "animate",
                },
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 50, "l": 20},
            "type": "buttons",
            "x": 0.1,
            "xanchor": "right",
            "y": 0,
            "yanchor": "top"
        }
    ]
    figure_layout['sliders'] = sliders

    return dict(data=[ani_frames[0]['data'][0], ani_frames[0]['data'][1]],
                frames=ani_frames,
                layout=figure_layout)
    # fig.show()
    # fig.write_html(file_name[:-4]+'.html')
