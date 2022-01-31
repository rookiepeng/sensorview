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

import os

import dash
from dash.dependencies import Output


# options for dropdown components with all the keys
DROPDOWN_OPTIONS_ALL = [
    Output('c-picker-3d', 'options'),
    Output('x-picker-2d-left', 'options'),
    Output('y-picker-2d-left', 'options'),
    Output('c-picker-2d-left', 'options'),
    Output('x-picker-2d-right', 'options'),
    Output('y-picker-2d-right', 'options'),
    Output('c-picker-2d-right', 'options'),
    Output('x-picker-histogram', 'options'),
    Output('x-picker-heatmap', 'options'),
    Output('y-picker-heatmap', 'options'),
    Output('y-picker-violin', 'options'),
]

# values for dropdown components with all the keys
DROPDOWN_VALUES_ALL = [
    Output('c-picker-3d', 'value'),
    Output('x-picker-2d-left', 'value'),
    Output('y-picker-2d-left', 'value'),
    Output('c-picker-2d-left', 'value'),
    Output('x-picker-2d-right', 'value'),
    Output('y-picker-2d-right', 'value'),
    Output('c-picker-2d-right', 'value'),
    Output('x-picker-histogram', 'value'),
    Output('x-picker-heatmap', 'value'),
    Output('y-picker-heatmap', 'value'),
    Output('y-picker-violin', 'value'),
]

# options for dropdown components with categorical keys
DROPDOWN_OPTIONS_CAT = [
    Output('x-picker-violin', 'options'),
]

# values for dropdown components with categorical keys
DROPDOWN_VALUES_CAT = [
    Output('x-picker-violin', 'value'),
]

# options for dropdown components with categorical keys and `None`
# for color dropdown components
DROPDOWN_OPTIONS_CAT_COLOR = [
    Output('c-picker-histogram', 'options'),
    Output('c-picker-violin', 'options'),
    Output('c-picker-parallel', 'options'),
]

# values for dropdown components with categorical keys and `None`
# for color dropdown components
DROPDOWN_VALUES_CAT_COLOR = [
    Output('c-picker-histogram', 'value'),
    Output('c-picker-violin', 'value'),
    Output('c-picker-parallel', 'value'),
]

app = dash.Dash(__name__,
                meta_tags=[{
                    'name': 'viewport',
                    'content': 'width=device-width,initial-scale=1'
                }]
                )


""" Global Variables """
REDIS_HASH_NAME = os.environ.get('DASH_APP_NAME', app.title)
SPECIAL_FOLDERS = ['imgs', 'images']
