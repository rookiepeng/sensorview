import dash
import dash_core_components as dcc
import dash_html_components as html
import numpy as np
import pandas as pd
import os
import plotly.graph_objs as go

app = dash.Dash(__name__,
                meta_tags=[{
                    "name": "viewport",
                    "content": "width=device-width,initial-scale=1"
                }])

data_files = []
for r, d, f in os.walk('./data'):
    for file in f:
        if '.pkl' in file:
            data_files.append(file)


app.layout = html.Div([
    html.Div([
        html.H4("Radar Viz"),
        html.P("Radar detections visualization"),
        dcc.Graph(
            id='det_grid',
            hoverData={'points': [{'customdata': 'Japan'}]}
        ),
        dcc.Slider(
            id='crossfilter-year--slider',
            # min=df['Year'].min(),
            # max=df['Year'].max(),
            # value=df['Year'].max(),
            # marks={str(year): str(year) for year in df['Year'].unique()}
        )
    ], style={'box-sizing': 'border-box',
              'width': '66%',
              'display': 'inline-block',
              'padding': '2rem 8rem'}),

    html.Div([
        dcc.Dropdown(
            id='data_file_picker',
            options=[{'label': i, 'value': i} for i in data_files],
            value=data_files[0]
        ),
        html.Label('Look types'),
        dcc.Dropdown(
            id='look_typy_picker',
            multi=True
        ),
        html.Label('Color assignment'),
        dcc.Dropdown(
            options=[
                {'label': 'Speed', 'value': 'Speed'},
                {'label': 'RCS', 'value': 'RCS'},
                {'label': 'SNR', 'value': 'SNR'}
            ],
            value='Speed'
        ),

        # Hidden div inside the app that stores the intermediate value
        html.Div(id='det_list', style={'display': 'none'})
    ], style={'box-sizing': 'border-box',
              'width': '34%',
              'display': 'inline-block',
              'vertical-align': 'top',
              'padding': '4rem 4rem',
              'margin': '0 0',
              'background-color': '#EEEEEE',
              'min-height': '100vh',
              'max-height': '100vh',
              'overflow-y': 'scroll',
              'overflow': 'scroll'})
], style={'border-width': '0',
          'box-sizing': 'border-box',
          'display': 'flex',
          'padding': '0rem 0rem',
          'background-color': '#F5F5F5'})


@app.callback(
    [dash.dependencies.Output('det_list', 'children'),
     dash.dependencies.Output('det_grid', 'figure'),
     dash.dependencies.Output('look_typy_picker', 'options'),
     dash.dependencies.Output('look_typy_picker', 'value')
     ],
    [dash.dependencies.Input('data_file_picker', 'value')
     ])
def update_data(data_file_name):
    look_options = []
    look_selection = []
    if data_file_name is not None:
        det_list = pd.read_pickle('./data/'+data_file_name)
        look_types = det_list['LookName'].unique()
        for look_name in look_types:
            look_options.append({'label': look_name, 'value': look_name})
            look_selection.append(look_name)
        print(det_list[0:10])
    else:
        det_list = pd.DataFrame()
    return det_list.to_json(),\
        update_det_graph(det_list),\
        look_options,\
        look_selection


def update_det_graph(det_list):
    min_x = np.min([np.min(det_list['Target_loc_x']),
                    np.min(det_list['vel_x'])])
    max_x = np.max([np.max(det_list['Target_loc_x']),
                    np.max(det_list['vel_x'])])

    min_y = np.min([np.min(det_list['Target_loc_y']),
                    np.min(det_list['vel_y'])])
    max_y = np.max([np.max(det_list['Target_loc_y']),
                    np.max(det_list['vel_y'])])

    fx = det_list['Target_loc_x']
    fy = det_list['Target_loc_y']
    fz = det_list['Target_loc_z']
    famp = det_list['Amp']
    frcs = det_list['RCS']
    fframe = det_list['Frame']
    fsnr = 20*np.log10(det_list['SNR'])
    faz = det_list['Azimuth']
    fel = det_list['Elevation']
    frng = det_list['Range']
    fspeed = det_list['Speed']
    fl_type = det_list['LookName']

    vx = det_list['vel_x']
    vy = det_list['vel_y']

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
        z=-fz,
        text=hover,
        hovertemplate='%{text}'+'Lateral: %{x:.2f} m<br>' +
        'Longitudinal: %{y:.2f} m<br>'+'Height: %{z:.2f} m<br>',
        mode='markers',
        # name='Frame: '+str(int(frame_idx)),
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
    camera = dict(
        up=dict(x=0, y=0, z=1),
        center=dict(x=0, y=0, z=0),
        eye=dict(x=0, y=-1.5, z=10),
    )
    plot_layout = dict(
        # title=file_name[:-4],
        template="plotly_dark",
        height=730,
        scene=dict(xaxis=dict(range=[min_x, max_x], title='Lateral (m)', autorange=False),
                   yaxis=dict(range=[min_y, max_y],
                              title='Longitudinal (m)', autorange=False),
                   zaxis=dict(range=[-20, 20],
                              title='Height (m)', autorange=False),
                   camera=camera,
                   aspectmode='manual',
                   aspectratio=dict(x=(max_x-min_x)/40,
                                    y=(max_y-min_y)/40, z=1),
                   ),
        margin=dict(l=0, r=0, b=0, t=0),
        legend=dict(x=0, y=0),
    )
    return go.Figure(data=[det_map, vel_map], layout=plot_layout
                     # you need to name the frame for the animation to behave properly
                     #    name=str(frame_idx)
                     )


if __name__ == '__main__':
    app.run_server(debug=True)
