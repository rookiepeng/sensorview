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
app.scripts.config.serve_locally = True
app.css.config.serve_locally = True

data_files = []
for r, d, f in os.walk('./data'):
    for file in f:
        if '.pkl' in file:
            data_files.append(file)

det_list = pd.DataFrame()
det_frames = []

app.layout = html.Div([
    html.Div([
        html.H4("Radar Viz"),
        html.P("Radar detections visualization"),
        dcc.Graph(
            id='det_grid',
            figure={
                'data': [{'mode': 'markers', 'type': 'scatter3d', 'x': [0], 'y': [0], 'z': [0]}
                         ],
                'layout': {'template': {
                    'data': {'bar': [{'error_x': {'color': '#f2f5fa'},
                                      'error_y': {'color': '#f2f5fa'},
                                      'marker': {'line': {'color': 'rgb(17,17,17)', 'width': 0.5}},
                                      'type': 'bar'}],
                             'barpolar': [{'marker': {'line': {'color': 'rgb(17,17,17)', 'width': 0.5}}, 'type': 'barpolar'}],
                             'carpet': [{'aaxis': {'endlinecolor': '#A2B1C6',
                                                   'gridcolor': '#506784',
                                                   'linecolor': '#506784',
                                                   'minorgridcolor': '#506784',
                                                   'startlinecolor': '#A2B1C6'},
                                         'baxis': {'endlinecolor': '#A2B1C6',
                                                   'gridcolor': '#506784',
                                                   'linecolor': '#506784',
                                                   'minorgridcolor': '#506784',
                                                   'startlinecolor': '#A2B1C6'},
                                         'type': 'carpet'}],
                             'choropleth': [{'colorbar': {'outlinewidth': 0, 'ticks': ''}, 'type': 'choropleth'}],
                             'contour': [{'colorbar': {'outlinewidth': 0, 'ticks': ''},
                                          'colorscale': [[0.0, '#0d0887'], [0.1111111111111111,
                                                                            '#46039f'], [0.2222222222222222,
                                                                                         '#7201a8'], [0.3333333333333333,
                                                                                                      '#9c179e'], [0.4444444444444444,
                                                                                                                   '#bd3786'], [0.5555555555555556,
                                                                                                                                '#d8576b'], [0.6666666666666666,
                                                                                                                                             '#ed7953'], [0.7777777777777778,
                                                                                                                                                          '#fb9f3a'], [0.8888888888888888,
                                                                                                                                                                       '#fdca26'], [1.0, '#f0f921']],
                                          'type': 'contour'}],
                             'contourcarpet': [{'colorbar': {'outlinewidth': 0, 'ticks': ''}, 'type': 'contourcarpet'}],
                             'heatmap': [{'colorbar': {'outlinewidth': 0, 'ticks': ''},
                                          'colorscale': [[0.0, '#0d0887'], [0.1111111111111111,
                                                                            '#46039f'], [0.2222222222222222,
                                                                                         '#7201a8'], [0.3333333333333333,
                                                                                                      '#9c179e'], [0.4444444444444444,
                                                                                                                   '#bd3786'], [0.5555555555555556,
                                                                                                                                '#d8576b'], [0.6666666666666666,
                                                                                                                                             '#ed7953'], [0.7777777777777778,
                                                                                                                                                          '#fb9f3a'], [0.8888888888888888,
                                                                                                                                                                       '#fdca26'], [1.0, '#f0f921']],
                                          'type': 'heatmap'}],
                             'heatmapgl': [{'colorbar': {'outlinewidth': 0, 'ticks': ''},
                                            'colorscale': [[0.0, '#0d0887'], [0.1111111111111111,
                                                                              '#46039f'], [0.2222222222222222,
                                                                                           '#7201a8'], [0.3333333333333333,
                                                                                                        '#9c179e'], [0.4444444444444444,
                                                                                                                     '#bd3786'], [0.5555555555555556,
                                                                                                                                  '#d8576b'], [0.6666666666666666,
                                                                                                                                               '#ed7953'], [0.7777777777777778,
                                                                                                                                                            '#fb9f3a'], [0.8888888888888888,
                                                                                                                                                                         '#fdca26'], [1.0, '#f0f921']],
                                            'type': 'heatmapgl'}],
                             'histogram': [{'marker': {'colorbar': {'outlinewidth': 0, 'ticks': ''}}, 'type': 'histogram'}],
                             'histogram2d': [{'colorbar': {'outlinewidth': 0, 'ticks': ''},
                                              'colorscale': [[0.0, '#0d0887'],
                                                             [0.1111111111111111,
                                                              '#46039f'],
                                                             [0.2222222222222222,
                                                                 '#7201a8'],
                                                             [0.3333333333333333,
                                                                 '#9c179e'],
                                                             [0.4444444444444444,
                                                                 '#bd3786'],
                                                             [0.5555555555555556,
                                                                 '#d8576b'],
                                                             [0.6666666666666666,
                                                                 '#ed7953'],
                                                             [0.7777777777777778,
                                                                 '#fb9f3a'],
                                                             [0.8888888888888888, '#fdca26'], [1.0,
                                                                                               '#f0f921']],
                                              'type': 'histogram2d'}],
                             'histogram2dcontour': [{'colorbar': {'outlinewidth': 0, 'ticks': ''},
                                                     'colorscale': [[0.0, '#0d0887'],
                                                                    [0.1111111111111111,
                                                                     '#46039f'],
                                                                    [0.2222222222222222,
                                                                     '#7201a8'],
                                                                    [0.3333333333333333,
                                                                     '#9c179e'],
                                                                    [0.4444444444444444,
                                                                     '#bd3786'],
                                                                    [0.5555555555555556,
                                                                     '#d8576b'],
                                                                    [0.6666666666666666,
                                                                     '#ed7953'],
                                                                    [0.7777777777777778,
                                                                     '#fb9f3a'],
                                                                    [0.8888888888888888,
                                                                     '#fdca26'], [1.0, '#f0f921']],
                                                     'type': 'histogram2dcontour'}],
                             'mesh3d': [{'colorbar': {'outlinewidth': 0, 'ticks': ''}, 'type': 'mesh3d'}],
                             'parcoords': [{'line': {'colorbar': {'outlinewidth': 0, 'ticks': ''}}, 'type': 'parcoords'}],
                             'pie': [{'automargin': True, 'type': 'pie'}],
                             'scatter': [{'marker': {'line': {'color': '#283442'}}, 'type': 'scatter'}],
                             'scatter3d': [{'line': {'colorbar': {'outlinewidth': 0, 'ticks': ''}},
                                            'marker': {'colorbar': {'outlinewidth': 0, 'ticks': ''}},
                                            'type': 'scatter3d'}],
                             'scattercarpet': [{'marker': {'colorbar': {'outlinewidth': 0, 'ticks': ''}}, 'type': 'scattercarpet'}],
                             'scattergeo': [{'marker': {'colorbar': {'outlinewidth': 0, 'ticks': ''}}, 'type': 'scattergeo'}],
                             'scattergl': [{'marker': {'line': {'color': '#283442'}}, 'type': 'scattergl'}],
                             'scattermapbox': [{'marker': {'colorbar': {'outlinewidth': 0, 'ticks': ''}}, 'type': 'scattermapbox'}],
                             'scatterpolar': [{'marker': {'colorbar': {'outlinewidth': 0, 'ticks': ''}}, 'type': 'scatterpolar'}],
                             'scatterpolargl': [{'marker': {'colorbar': {'outlinewidth': 0, 'ticks': ''}}, 'type': 'scatterpolargl'}],
                             'scatterternary': [{'marker': {'colorbar': {'outlinewidth': 0, 'ticks': ''}}, 'type': 'scatterternary'}],
                             'surface': [{'colorbar': {'outlinewidth': 0, 'ticks': ''},
                                          'colorscale': [[0.0, '#0d0887'], [0.1111111111111111,
                                                                            '#46039f'], [0.2222222222222222,
                                                                                         '#7201a8'], [0.3333333333333333,
                                                                                                      '#9c179e'], [0.4444444444444444,
                                                                                                                   '#bd3786'], [0.5555555555555556,
                                                                                                                                '#d8576b'], [0.6666666666666666,
                                                                                                                                             '#ed7953'], [0.7777777777777778,
                                                                                                                                                          '#fb9f3a'], [0.8888888888888888,
                                                                                                                                                                       '#fdca26'], [1.0, '#f0f921']],
                                          'type': 'surface'}],
                             'table': [{'cells': {'fill': {'color': '#506784'}, 'line': {'color': 'rgb(17,17,17)'}},
                                        'header': {'fill': {'color': '#2a3f5f'}, 'line': {'color': 'rgb(17,17,17)'}},
                                        'type': 'table'}]},
                    'layout': {'annotationdefaults': {'arrowcolor': '#f2f5fa', 'arrowhead': 0, 'arrowwidth': 1},
                               'coloraxis': {'colorbar': {'outlinewidth': 0, 'ticks': ''}},
                               'colorscale': {'diverging': [[0, '#8e0152'], [0.1, '#c51b7d'],
                                                            [0.2, '#de77ae'], [
                                                                0.3, '#f1b6da'],
                                                            [0.4, '#fde0ef'], [
                                                                0.5, '#f7f7f7'],
                                                            [0.6, '#e6f5d0'], [
                                                                0.7, '#b8e186'],
                                                            [0.8, '#7fbc41'], [0.9, '#4d9221'], [1,
                                                                                                 '#276419']],
                                              'sequential': [[0.0, '#0d0887'],
                                                             [0.1111111111111111,
                                                                 '#46039f'],
                                                             [0.2222222222222222,
                                                                 '#7201a8'],
                                                             [0.3333333333333333,
                                                                 '#9c179e'],
                                                             [0.4444444444444444,
                                                                 '#bd3786'],
                                                             [0.5555555555555556,
                                                                 '#d8576b'],
                                                             [0.6666666666666666,
                                                                 '#ed7953'],
                                                             [0.7777777777777778,
                                                                 '#fb9f3a'],
                                                             [0.8888888888888888, '#fdca26'], [1.0,
                                                                                               '#f0f921']],
                                              'sequentialminus': [[0.0, '#0d0887'],
                                                                  [0.1111111111111111,
                                                                   '#46039f'],
                                                                  [0.2222222222222222,
                                                                      '#7201a8'],
                                                                  [0.3333333333333333,
                                                                      '#9c179e'],
                                                                  [0.4444444444444444,
                                                                      '#bd3786'],
                                                                  [0.5555555555555556,
                                                                      '#d8576b'],
                                                                  [0.6666666666666666,
                                                                      '#ed7953'],
                                                                  [0.7777777777777778,
                                                                      '#fb9f3a'],
                                                                  [0.8888888888888888,
                                                                      '#fdca26'],
                                                                  [1.0, '#f0f921']]},
                               'colorway': ['#636efa', '#EF553B', '#00cc96', '#ab63fa', '#FFA15A', '#19d3f3',
                                            '#FF6692', '#B6E880', '#FF97FF', '#FECB52'],
                               'font': {'color': '#f2f5fa'},
                               'geo': {'bgcolor': 'rgb(17,17,17)',
                                       'lakecolor': 'rgb(17,17,17)',
                                       'landcolor': 'rgb(17,17,17)',
                                       'showlakes': True,
                                       'showland': True,
                                       'subunitcolor': '#506784'},
                               'hoverlabel': {'align': 'left'},
                               'hovermode': 'closest',
                               'mapbox': {'style': 'dark'},
                               'paper_bgcolor': 'rgb(17,17,17)',
                               'plot_bgcolor': 'rgb(17,17,17)',
                               'polar': {'angularaxis': {'gridcolor': '#506784', 'linecolor': '#506784', 'ticks': ''},
                                         'bgcolor': 'rgb(17,17,17)',
                                         'radialaxis': {'gridcolor': '#506784', 'linecolor': '#506784', 'ticks': ''}},
                               'scene': {'xaxis': {'backgroundcolor': 'rgb(17,17,17)',
                                                   'gridcolor': '#506784',
                                                   'gridwidth': 2,
                                                   'linecolor': '#506784',
                                                   'showbackground': True,
                                                   'ticks': '',
                                                   'zerolinecolor': '#C8D4E3'},
                                         'yaxis': {'backgroundcolor': 'rgb(17,17,17)',
                                                   'gridcolor': '#506784',
                                                   'gridwidth': 2,
                                                   'linecolor': '#506784',
                                                   'showbackground': True,
                                                   'ticks': '',
                                                   'zerolinecolor': '#C8D4E3'},
                                         'zaxis': {'backgroundcolor': 'rgb(17,17,17)',
                                                   'gridcolor': '#506784',
                                                   'gridwidth': 2,
                                                   'linecolor': '#506784',
                                                   'showbackground': True,
                                                   'ticks': '',
                                                   'zerolinecolor': '#C8D4E3'}},
                               'shapedefaults': {'line': {'color': '#f2f5fa'}},
                               'sliderdefaults': {'bgcolor': '#C8D4E3', 'bordercolor': 'rgb(17,17,17)', 'borderwidth': 1, 'tickwidth': 0},
                               'ternary': {'aaxis': {'gridcolor': '#506784', 'linecolor': '#506784', 'ticks': ''},
                                           'baxis': {'gridcolor': '#506784', 'linecolor': '#506784', 'ticks': ''},
                                           'bgcolor': 'rgb(17,17,17)',
                                           'caxis': {'gridcolor': '#506784', 'linecolor': '#506784', 'ticks': ''}},
                               'title': {'x': 0.05},
                               'updatemenudefaults': {'bgcolor': '#506784', 'borderwidth': 0},
                               'xaxis': {'automargin': True,
                                         'gridcolor': '#283442',
                                         'linecolor': '#506784',
                                         'ticks': '',
                                         'title': {'standoff': 15},
                                         'zerolinecolor': '#283442',
                                         'zerolinewidth': 2},
                               'yaxis': {'automargin': True,
                                         'gridcolor': '#283442',
                                         'linecolor': '#506784',
                                         'ticks': '',
                                         'title': {'standoff': 15},
                                         'zerolinecolor': '#283442',
                                         'zerolinewidth': 2}}
                },
                    'height': 700,
                    'scene': {'xaxis': {'range': [-100, 100],
                                        'title': 'Lateral (m)',
                                        'autorange': False},
                              'yaxis': {'range': [-100, 100],
                                        'title': 'Longitudinal (m)',
                                        'autorange': False},
                              'zaxis': {'range': [-20, 20], 'title': 'Height (m)', 'autorange': False},
                              'aspectmode': 'manual'},
                    'margin': {'l': 0, 'r': 0, 'b': 0, 't': 20},
                    'legend': {'x': 0, 'y': 0}}
            },
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
              'padding': '2rem 4rem'}),

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
    [
        # dash.dependencies.Output('det_list', 'children'),
        dash.dependencies.Output('det_grid', 'figure'),
        dash.dependencies.Output('look_typy_picker', 'options'),
        dash.dependencies.Output('look_typy_picker', 'value')
    ],
    [
        dash.dependencies.Input('data_file_picker', 'value')
    ],
    [dash.dependencies.State('det_grid', 'figure')])
def update_data(data_file_name, det_plot):
    global det_list
    global det_frames
    look_options = []
    look_selection = []
    if data_file_name is not None:
        det_list = pd.read_pickle('./data/'+data_file_name)
        det_frames = []
        frame_list = det_list['Frame'].unique()
        for frame_idx in frame_list:
            filtered_list = det_list[det_list['Frame'] == frame_idx]
            filtered_list = filtered_list.reset_index()
            det_frames.append(filtered_list)
        look_types = det_list['LookName'].unique()
        for look_name in look_types:
            look_options.append({'label': look_name, 'value': look_name})
            look_selection.append(look_name)
        print(det_list[0:10])
    else:
        det_list = pd.DataFrame()
        det_frames = []
    return update_det_graph(det_plot, det_frames[0]),\
        look_options,\
        look_selection


def update_det_graph(det_plot, det_list):
    # global det_list
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
        height=700,
        scene=dict(xaxis=dict(range=[min_x, max_x], title='Lateral (m)', autorange=False),
                   yaxis=dict(range=[min_y, max_y],
                              title='Longitudinal (m)', autorange=False),
                   zaxis=dict(range=[-20, 20],
                              title='Height (m)', autorange=False),
                   #    camera=camera,
                   aspectmode='manual',
                   aspectratio=dict(x=(max_x-min_x)/40,
                                    y=(max_y-min_y)/40, z=1),
                   ),
        margin=dict(l=0, r=0, b=0, t=20),
        legend=dict(x=0, y=0),
        # uirevision=det_list,
    )
    det_plot['data'] = [det_map, vel_map]
    # return go.Figure(data=[det_map, vel_map], layout=plot_layout)
    return det_plot


if __name__ == '__main__':
    app.run_server(debug=True)
