import numpy as np
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio


def get_figure_data(det_frame, color_assign='Speed', c_range=[-30, 30], db=False):
    if det_frame.shape[0] > 0:
        color = det_frame[color_assign]
        if db:
            color = 20*np.log10(color)

        frame_list = det_frame['Frame'].to_list()

        hover = []
        for idx, var in enumerate(frame_list):
            hover.append(
                'Frame: '+str(int(var))+'<br>' +
                'Amp: '+'{:.2f}'.format(det_frame['Amplitude'][idx])+'dB<br>' +
                'RCS: ' + '{:.2f}'.format(det_frame['RCS'][idx])+'dB<br>' +
                'SNR: ' + '{:.2f}'.format(20*np.log10(det_frame['SNR'])[idx])+'dB<br>' +
                'Az: ' + '{:.2f}'.format(det_frame['Azimuth'][idx])+'deg<br>' +
                'El: ' + '{:.2f}'.format(det_frame['Elevation'][idx])+'deg<br>' +
                'Range: ' + '{:.2f}'.format(det_frame['Range'][idx])+'m<br>' +
                'Speed: ' + '{:.2f}'.format(det_frame['Speed'][idx])+'m/s<br>' +
                'LookType: ' + det_frame['LookName'][idx] + '<br>'
            )

        det_map = go.Scatter3d(
            x=det_frame['Latitude'],
            y=det_frame['Longitude'],
            z=det_frame['Height'],
            text=hover,
            hovertemplate='%{text}'+'Lateral: %{x:.2f} m<br>' +
            'Longitudinal: %{y:.2f} m<br>'+'Height: %{z:.2f} m<br>',
            mode='markers',
            name='Frame: '+str(int(frame_list[0])),
            marker=dict(
                size=3,
                color=color,                # set color to an array/list of desired values
                colorscale='Rainbow',   # choose a colorscale
                opacity=0.8,
                colorbar=dict(
                    title=color_assign,
                ),
                cmin=c_range[0],
                cmax=c_range[1],
            ),
        )

        vel_map = go.Scatter3d(
            x=[det_frame['VehLat'][0]],
            y=[det_frame['VehLong'][0]],
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
                 'x': [], 'y': [], 'z': []}
                ]


def get_figure_layout(x_range, y_range, z_range=[-20, 20], height=650):
    scale = np.min([x_range[1]-x_range[0], y_range[1] -
                    y_range[0], z_range[1]-z_range[0]])
    return dict(
        # title=file_name[:-4],
        template=pio.templates['plotly_dark'],
        height=height,
        scene=dict(xaxis=dict(range=x_range, title='Lateral (m)', autorange=False),
                   yaxis=dict(range=y_range,
                              title='Longitudinal (m)', autorange=False),
                   zaxis=dict(range=z_range,
                              title='Height (m)', autorange=False),
                   aspectmode='manual',
                   aspectratio=dict(x=(x_range[1]-x_range[0])/scale,
                                    y=(y_range[1]-y_range[0])/scale,
                                    z=(z_range[1]-z_range[0])/scale),
                   ),
        margin=dict(l=0, r=0, b=0, t=20),
        legend=dict(x=0, y=0),
        uirevision='no_change',
    )


def gen_figure(det_frame, min_x, max_x, min_y, max_y):
    data = get_figure_data(det_frame, min_x, max_x, min_y, max_y)
    layout = get_figure_layout()

    return go.Figure(data=[det_map, vel_map], layout=plot_layout)


def gen_animation():

    min_x = np.min([np.min(det_list['Latitude']),
                    np.min(det_list['VehLat'])])
    max_x = np.max([np.max(det_list['Latitude']),
                    np.max(det_list['VehLat'])])

    min_y = np.min([np.min(det_list['Longitude']),
                    np.min(det_list['VehLong'])])
    max_y = np.max([np.max(det_list['Longitude']),
                    np.max(det_list['VehLong'])])

    ani_frames = []
    frame_list = det_list['Frame'].unique()

    for frame_idx in frame_list:
        filtered_list = det_list[det_list['Frame'] == frame_idx]
        filtered_list = filtered_list.reset_index()
        fx = filtered_list['Latitude']
        fy = filtered_list['Longitude']
        fz = filtered_list['Height']
        famp = filtered_list['Amplitude']
        frcs = filtered_list['RCS']
        fframe = filtered_list['Frame']
        fsnr = 20*np.log10(filtered_list['SNR'])
        faz = filtered_list['Azimuth']
        fel = filtered_list['Elevation']
        frng = filtered_list['Range']
        fspeed = filtered_list['Speed']
        fl_type = filtered_list['LookName']

        vx = filtered_list['VehLat']
        vy = filtered_list['VehLong']

        hover = []
        for idx, var in enumerate(fframe.to_list()):
            hover.append('Frame: '+str(int(var))+'<br>' +
                         'Amp: '+'{:.2f}'.format(famp[idx])+'dB<br>' +
                         'RCS: ' + '{:.2f}'.format(frcs[idx])+'dB<br>' +
                         'SNR: ' + '{:.2f}'.format(fsnr[idx])+'dB<br>' +
                         'Az: ' + '{:.2f}'.format(faz[idx])+'deg<br>' +
                         'El: ' + '{:.2f}'.format(fel[idx])+'deg<br>' +
                         'Range: ' + '{:.2f}'.format(frng[idx])+'m<br>' +
                         'Speed: ' + '{:.2f}'.format(fspeed[idx])+'m/s<br>' +
                         'LookType: ' + fl_type[idx] + '<br>')

        det_map = go.Scatter3d(
            x=fx,
            y=fy,
            z=fz,
            text=hover,
            hovertemplate='%{text}'+'Lateral: %{x:.2f} m<br>' +
            'Longitudinal: %{y:.2f} m<br>'+'Height: %{z:.2f} m<br>',
            mode='markers',
            name='Frame: '+str(int(frame_idx)),
            marker=dict(
                size=3,
                color=fspeed,                # set color to an array/list of desired values
                colorscale='Rainbow',   # choose a colorscale
                opacity=0.8,
                colorbar=dict(
                    title='Speed',
                ),
                cmin=-35,
                cmax=35,
            ),
        )

        vel_map = go.Scatter3d(
            x=[vx[0]],
            y=[vy[0]],
            z=[0],
            hovertemplate='Lateral: %{x:.2f} m<br>' +
            'Longitudinal: %{y:.2f} m<br>',
            mode='markers',
            name='Vehicle',
            marker=dict(color='rgb(255, 255, 255)', size=6, opacity=0.8,
                        symbol='circle')
        )

        ani_frames.append(go.Frame(data=[det_map, vel_map],
                                   # you need to name the frame for the animation to behave properly
                                   name=str(frame_idx)
                                   ))

    def frame_args(duration):
        return {
            "frame": {"duration": duration},
            "mode": "immediate",
            "fromcurrent": True,
            "transition": {"duration": duration, "easing": "quadratic-in-out"},
        }

    sliders = [
        {
            "pad": {"b": 10, "t": 40},
            "len": 0.9,
            "x": 0.1,
            "y": 0,
            "steps": [
                {
                    "args": [[f.name], frame_args(0)],
                    "label": str(k),
                    "method": "animate",
                }
                for k, f in enumerate(ani_frames)
            ],
        }
    ]

    camera = dict(
        up=dict(x=0, y=0, z=1),
        center=dict(x=0, y=0, z=0),
        eye=dict(x=0, y=-1.5, z=10),
    )

    # Layout
    figure_layout = go.Layout(
        title=file_name[:-4],
        template="plotly_dark",
        #     template="ggplot2",
        height=730,
        scene=dict(xaxis=dict(range=[min_x, max_x], title='Lateral (m)', autorange=False),
                   yaxis=dict(range=[min_y, max_y],
                              title='Longitudinal (m)', autorange=False),
                   zaxis=dict(range=[-20, 20],
                              title='Height (m)', autorange=False),
                   #                camera=camera,
                   aspectmode='manual',
                   aspectratio=dict(x=(max_x-min_x)/40,
                                    y=(max_y-min_y)/40, z=1),
                   ),
        margin=dict(l=0, r=0, b=0, t=40),
        legend=dict(x=0, y=0),
        updatemenus=[
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
        ],
        sliders=sliders)

    fig = go.Figure(data=[ani_frames[0]['data'][0], ani_frames[0]
                          ['data'][1]], frames=ani_frames, layout=figure_layout)

    fig.show()
    # fig.write_html(file_name[:-4]+'.html')
