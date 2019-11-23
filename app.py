import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import os

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

df = pd.read_csv(
    'https://gist.githubusercontent.com/chriddyp/cb5392c35661370d95f300086accea51/raw/8e0768211f6b747c0db42a9ce9a0937dafcbd8b2/indicators.csv')

available_indicators = df['Indicator Name'].unique()

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
            min=df['Year'].min(),
            max=df['Year'].max(),
            value=df['Year'].max(),
            marks={str(year): str(year) for year in df['Year'].unique()}
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
    return det_list.to_json(), look_options, look_selection


def update_graph(xaxis_column_name, yaxis_column_name,
                 xaxis_type, yaxis_type,
                 year_value):
    dff = df[df['Year'] == year_value]

    return {
        'data': [dict(
            x=dff[dff['Indicator Name'] == xaxis_column_name]['Value'],
            y=dff[dff['Indicator Name'] == yaxis_column_name]['Value'],
            text=dff[dff['Indicator Name'] ==
                     yaxis_column_name]['Country Name'],
            customdata=dff[dff['Indicator Name'] ==
                           yaxis_column_name]['Country Name'],
            mode='markers',
            marker={
                'size': 15,
                'opacity': 0.5,
                'line': {'width': 0.5, 'color': 'white'}
            }
        )],
        'layout': dict(
            xaxis={
                'title': xaxis_column_name,
                'type': 'linear' if xaxis_type == 'Linear' else 'log'
            },
            yaxis={
                'title': yaxis_column_name,
                'type': 'linear' if yaxis_type == 'Linear' else 'log'
            },
            margin={'l': 40, 'b': 30, 't': 10, 'r': 0},
            height=450,
            hovermode='closest'
        )
    }


def create_time_series(dff, axis_type, title):
    return {
        'data': [dict(
            x=dff['Year'],
            y=dff['Value'],
            mode='lines+markers'
        )],
        'layout': {
            'height': 225,
            'margin': {'l': 20, 'b': 30, 'r': 10, 't': 10},
            'annotations': [{
                'x': 0, 'y': 0.85, 'xanchor': 'left', 'yanchor': 'bottom',
                'xref': 'paper', 'yref': 'paper', 'showarrow': False,
                'align': 'left', 'bgcolor': 'rgba(255, 255, 255, 0.5)',
                'text': title
            }],
            'yaxis': {'type': 'linear' if axis_type == 'Linear' else 'log'},
            'xaxis': {'showgrid': False}
        }
    }


if __name__ == '__main__':
    app.run_server(debug=True)
