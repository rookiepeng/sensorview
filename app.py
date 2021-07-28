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


import datetime

import json
import os

import dash
from dash.dependencies import Input, Output, State, MATCH, ALL
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_bootstrap_components as dbc

import base64

import numpy as np
import pandas as pd
import os
import plotly.graph_objs as go
import plotly.express as px

from layout import get_app_layout

from viz.viz import get_scatter3d
from viz.viz import get_scatter2d, get_heatmap
from viz.viz import get_animation_data

from tasks import filter_all
from tasks import celery_filtering_data

from utils import load_config, redis_set, redis_get, REDIS_KEYS


""" Initialize Dash App """
app = dash.Dash(__name__,
                meta_tags=[{
                    'name': 'viewport',
                    'content': 'width=device-width,initial-scale=1'
                }]
                )
server = app.server
app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = 'SensorView'
app.layout = get_app_layout(app)

""" Global Variables """
REDIS_HASH_NAME = os.environ.get('DASH_APP_NAME', app.title)
SPECIAL_FOLDERS = ['imgs', 'images']
KEY_TYPES = {'CAT': 'categorical',
             'NUM': 'numerical'}

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

""" Callbacks """


@ app.callback(
    [
        Output('case-picker', 'options'),
        Output('case-picker', 'value'),
    ],
    Input('refresh-button', 'n_clicks')
)
def refresh_button_clicked(_):
    """
    Callback when the refresh button is clicked

    :param _:
        Number of clicks

    :return: [
        Test case options,
        Test case default value
    ]
    :rtype: list
    """

    options = []
    obj = os.scandir('./data')
    for entry in obj:
        if entry.is_dir():
            options.append({'label': entry.name,
                            'value': entry.name})

    return [options, options[0]['value']]


@ app.callback([
    Output('file-picker', 'value'),
    Output('file-picker', 'options')] +
    DROPDOWN_OPTIONS_ALL +
    DROPDOWN_VALUES_ALL +
    DROPDOWN_OPTIONS_CAT_COLOR +
    DROPDOWN_VALUES_CAT_COLOR +
    DROPDOWN_OPTIONS_CAT +
    DROPDOWN_VALUES_CAT,
    Input('case-picker', 'value'),
    State('session-id', 'data'))
def case_selected(case, session_id):
    """
    Callback when a test case is selected

    :param str case:
        Selected test case
    :param str session_id:
        Session id

    :return: [
        Test file default value,
        Test file option lists,
        Options for dropdown components with all the keys,
        Values for dropdown components with all the keys,
        Options for dropdown components with categorical keys and `None`,
        Values for dropdown components with categorical keys and `None`,
        Options for dropdown components with categorical keys,
        Values for dropdown components with categorical keys
    ]
    :rtype: list
    """

    if case is None:
        raise PreventUpdate

    data_files = []
    case_dir = './data/'+case

    for dirpath, dirnames, files in os.walk(case_dir):
        dirnames[:] = [d for d in dirnames if d not in SPECIAL_FOLDERS]
        for name in files:
            if name.lower().endswith('.csv'):
                data_files.append({
                    'label': os.path.join(dirpath[len(case_dir):], name),
                    'value': json.dumps({
                        'path': dirpath[len(case_dir):],
                        'name': name,
                        'feather_name': name.replace('.csv', '.feather')})})
            elif name.lower().endswith('.pkl'):
                data_files.append({
                    'label': os.path.join(dirpath[len(case_dir):], name),
                    'value': json.dumps({
                        'path': dirpath[len(case_dir):],
                        'name': name,
                        'feather_name': name.replace('.pkl', '.feather')})})

    if os.path.exists('./data/' +
                      case +
                      '/config.json'):
        config = load_config('./data/' +
                             case +
                             '/config.json')
        redis_set(config, session_id, REDIS_KEYS['config'])
    else:
        raise PreventUpdate

    # extract keys and save to Redis
    num_keys = []
    cat_keys = []
    for _, item in enumerate(config['keys']):
        if config['keys'][item].get(
                'type', KEY_TYPES['NUM']) == KEY_TYPES['NUM']:
            num_keys.append(item)
        else:
            cat_keys.append(item)
    filter_kwargs = {'num_keys': num_keys,
                     'cat_keys': cat_keys}
    redis_set(filter_kwargs, session_id, REDIS_KEYS['filter_kwargs'])

    # options for `DROPDOWN_OPTIONS_ALL`
    options_all = [[{
        'label': config['keys'][item].get('description', item),
        'value': item}
        for _, item in enumerate(config['keys'])
    ]]*len(DROPDOWN_OPTIONS_ALL)

    # values for `DROPDOWN_VALUES_ALL`
    all_keys = num_keys+cat_keys
    if len(all_keys) == 0:
        values_all = [None]*len(DROPDOWN_VALUES_ALL)
    else:
        values_all = [all_keys[x % len(all_keys)]
                      for x in range(0, len(DROPDOWN_VALUES_ALL))]

    # options for `DROPDOWN_OPTIONS_CAT_COLOR`
    options_cat_color = [[{
        'label': 'None',
        'value': 'None'}]+[{
            'label': config['keys'][item].get('description', item),
            'value': item}
            for _, item in enumerate(cat_keys)
    ]]*len(DROPDOWN_OPTIONS_CAT_COLOR)

    # values for `DROPDOWN_VALUES_CAT_COLOR`
    values_cat_color = ['None']*len(DROPDOWN_VALUES_CAT_COLOR)

    # options for `DROPDOWN_OPTIONS_CAT`
    options_cat = [[{
        'label': config['keys'][item].get('description', item),
        'value': item}
        for _, item in enumerate(cat_keys)
    ]]*len(DROPDOWN_OPTIONS_CAT)

    # values for `DROPDOWN_VALUES_CAT`
    if len(cat_keys) == 0:
        values_cat = [None]*len(DROPDOWN_VALUES_CAT)
    else:
        values_cat = [cat_keys[0]]*len(DROPDOWN_VALUES_CAT)

    return [data_files[0]['value'], data_files] +\
        options_all +\
        values_all +\
        options_cat_color +\
        values_cat_color +\
        options_cat +\
        values_cat


@ app.callback(
    [
        Output('slider-frame', 'value'),
        Output('slider-frame', 'min'),
        Output('slider-frame', 'max'),
        Output('dropdown-container', 'children'),
        Output('slider-container', 'children'),
        Output('interval-component', 'disabled'),
        Output('dim-picker-parallel', 'options'),
        Output('dim-picker-parallel', 'value'),
    ],
    [
        Input('file-picker', 'value'),
        Input('previous-button', 'n_clicks'),
        Input('next-button', 'n_clicks'),
        Input('interval-component', 'n_intervals'),
        Input('play-button', 'n_clicks'),
        Input('stop-button', 'n_clicks'),
    ],
    [
        State('case-picker', 'value'),
        State('session-id', 'data'),
        State('slider-frame', 'max'),
        State('slider-frame', 'value'),
        State('visible-picker', 'value'),
        State('c-picker-3d', 'value'),
        State('outline-switch', 'value'),
        State('colormap-3d', 'value'),
    ])
def file_selected(
        file,
        left_btn,
        right_btn,
        interval,
        play_clicks,
        stop_clicks,
        case,
        session_id,
        slider_max,
        slider_var,
        visible_list,
        c_key,
        outline_enable,
        colormap
):
    """
    Callback when a data file is selected

    :param json file
        json string of the selected file
        `path`, `name`, `feather_name`
    :param int left_btn
        number of clicks from next button
    :param int right_btn
        number of clicks from previous button
    :param int interval
        number of intervals
    :param int play_clicks
        number of clicks from play button
    :param int stop_clicks
        number of clicks from stop button
    :param str case
        case name
    :param str session_id
        session id
    :param int slider_max
        maximum number of slider
    :param int slider_var
        current slider position
    :param list visible_list
        list of visibility [`visible', 'hidden']
    :param str c_key
        key for the colormap
    :param boolean outline_enable
        flag to enable outline for the scatters
    :param str colormap
        colormap name

    :return: [
        Set default slider value to 0,
        Minimal slider range,
        Maximal slider range,
        Dropdown layouts,
        Slider layouts,
        Enable/disable interval component,
        Dimensions picker options for parallel categories plot,
        Dimensions picker default value
    ]
    :rtype: list
    """
    if file is None:
        raise PreventUpdate

    if case is None:
        raise PreventUpdate

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # get keys from Redis
    config = redis_get(session_id, REDIS_KEYS['config'])
    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    keys_dict = config['keys']

    if trigger_id == 'file-picker':
        # load data from selected file (supoprt .csv or .pickle)
        #   - check if there is a .feather file with the same name
        #   - if the .feather file exits, load through the .feather file
        #   - otherwise, load the file and save the DataFrame into a
        #     .feather file
        file = json.loads(file)
        if os.path.exists('./data/' +
                          case +
                          file['path'] +
                          '/' +
                          file['feather_name']):
            new_data = pd.read_feather('./data/' +
                                       case +
                                       file['path'] +
                                       '/' +
                                       file['feather_name'])
        else:
            if '.pkl' in file['name']:
                new_data = pd.read_pickle('./data/' +
                                          case +
                                          file['path'] +
                                          '/' +
                                          file['name'])
                new_data = new_data.reset_index(drop=True)

            elif '.csv' in file['name']:
                new_data = pd.read_csv('./data/' +
                                       case +
                                       file['path'] +
                                       '/' +
                                       file['name'])

            new_data.to_feather('./data/' +
                                case +
                                file['path'] +
                                '/' +
                                file['feather_name'])

        # get the list of frames and save to Redis
        frame_list = np.sort(new_data[config['slider']].unique())
        redis_set(frame_list, session_id, REDIS_KEYS['frame_list'])

        # create the visibility table and save to Redis
        #   the visibility table is used to indicate if the data point is
        #   `visible` or `hidden`
        visible_table = pd.DataFrame()
        visible_table['_IDS_'] = new_data.index
        visible_table['_VIS_'] = 'visible'
        redis_set(visible_table, session_id, REDIS_KEYS['visible_table'])

        # group the DataFrame by frame and save the grouped data one by one
        # into Redis
        frame_group = new_data.groupby(config['slider'])
        for frame_idx, frame_data in frame_group:
            redis_set(frame_data, session_id,
                      REDIS_KEYS['frame_data'],
                      str(frame_idx))

        # create dropdown layouts
        # obtain categorical values
        cat_values = []
        new_dropdown = []
        for idx, d_item in enumerate(cat_keys):
            var_list = new_data[d_item].unique().tolist()
            value_list = var_list

            new_dropdown.append(
                dbc.Label(
                    keys_dict[d_item]['description']
                )
            )
            new_dropdown.append(
                dcc.Dropdown(
                    id={'type': 'filter-dropdown',
                        'index': idx},
                    options=[{'label': i,
                              'value': i}
                             for i in var_list],
                    value=value_list,
                    multi=True
                ))

            cat_values.append(value_list)

        # create slider layouts
        # obtain numerical values
        num_values = []
        new_slider = []
        for idx, item in enumerate(num_keys):
            var_min = np.floor(np.min(new_data[item]))
            var_max = np.ceil(np.max(new_data[item]))

            new_slider.append(
                dbc.Label(
                    keys_dict[item]['description']
                )
            )
            new_slider.append(dcc.RangeSlider(
                id={'type': 'filter-slider',
                    'index': idx},
                min=var_min,
                max=var_max,
                step=round((var_max-var_min)/100, 3),
                value=[var_min, var_max],
                tooltip={'always_visible': False}
            ))

            num_values.append([var_min, var_max])

        # save categorical values and numerical values to Redis
        filter_kwargs['num_values'] = num_values
        filter_kwargs['cat_values'] = cat_values
        redis_set(filter_kwargs, session_id, REDIS_KEYS['filter_kwargs'])

        # outline width
        if outline_enable:
            linewidth = 1
        else:
            linewidth = 0

        # invoke celery task
        redis_set(0, session_id, REDIS_KEYS['task_id'])
        redis_set(-1, session_id, REDIS_KEYS['figure_idx'])
        celery_filtering_data.apply_async(
            args=[session_id,
                  case,
                  file,
                  visible_list,
                  c_key,
                  linewidth,
                  keys_dict[c_key]['description'],
                  keys_dict[config['slider']
                            ]['description'],
                  colormap], serializer='json')

        # dimensions picker default value
        if len(cat_keys) == 0:
            values_cat = None
        else:
            values_cat = cat_keys[0]

        return [0,
                0,
                len(frame_list)-1,
                new_dropdown,
                new_slider,
                dash.no_update,
                [{'label': ck, 'value': ck} for ck in cat_keys],
                [values_cat]]

    elif trigger_id == 'previous-button':
        if left_btn == 0:
            raise PreventUpdate

        # previous button is clicked
        return [(slider_var-1) % (slider_max+1),
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update]

    elif trigger_id == 'next-button':
        if right_btn == 0:
            raise PreventUpdate

        # next button is clicked
        return [(slider_var+1) % (slider_max+1),
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update]

    elif trigger_id == 'interval-component':
        if interval == 0:
            raise PreventUpdate

        # triggerred from interval
        if slider_var == slider_max:
            return [dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    True,
                    dash.no_update,
                    dash.no_update]

        else:
            return [(slider_var+1) % (slider_max+1),
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update]

    elif trigger_id == 'play-button':
        if play_clicks == 0:
            raise PreventUpdate

        # play button is clicked
        return [dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                False,
                dash.no_update,
                dash.no_update]

    elif trigger_id == 'stop-button':
        if stop_clicks == 0:
            raise PreventUpdate

        # stop button is clicked
        return [dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                True,
                dash.no_update,
                dash.no_update]


@ app.callback(
    [
        Output('left-switch', 'value'),
        Output('right-switch', 'value'),
        Output('histogram-switch', 'value'),
        Output('violin-switch', 'value'),
        Output('parallel-switch', 'value'),
        Output('heat-switch', 'value'),
    ],
    Input('file-picker', 'value'),
    State('case-picker', 'value'))
def reset_switch_state(file, case):
    """
    Reset all the enable switches when a new file is selected

    :param json file
        json string of the selected file
        `path`, `name`, `feather_name`
    :param str case
        case name

    :return: [
        Left figure enable switch,
        Right figure enable switch,
        Histogram figure enable switch,
        Violin figure enable switch,
        Parallel categories figure enable switch,
        Heatmap figure enable switch
    ]
    :rtype: list
    """
    if file is None:
        raise PreventUpdate

    if case is None:
        raise PreventUpdate

    return [[], [], [], [], [], []]


@ app.callback(
    [
        Output('slider-frame', 'disabled'),
        Output('previous-button', 'disabled'),
        Output('next-button', 'disabled'),
        Output('play-button', 'disabled'),
        Output('stop-button', 'disabled'),
    ],
    Input('overlay-switch', 'value'))
def overlay_switch_changed(overlay):
    """
    Callback when the overlay switch state is changed

    :param boolean overlay
        overlay switch state

    :return: [
        Frame slider enable/disable,
        Previous button enable/disable,
        Next button enable/disable,
        Play button enable/disable,
        Stop button enable/disable
    ]
    :rtype: list
    """
    if overlay:
        return [True]*5
    else:
        return [False]*5


@ app.callback(
    [
        Output('scatter3d', 'figure'),
        Output('filter-trigger', 'data'),
    ],
    [
        Input('slider-frame', 'value'),
        Input({'type': 'filter-dropdown', 'index': ALL}, 'value'),
        Input({'type': 'filter-slider', 'index': ALL}, 'value'),
        Input('colormap-3d', 'value'),
        Input('visible-picker', 'value'),
        Input('c-picker-3d', 'value'),
        Input('overlay-switch', 'value'),
        Input('outline-switch', 'value'),
        Input('scatter3d', 'clickData'),
        Input('left-hide-trigger', 'data'),
    ],
    [
        State('click-hide-switch', 'value'),
        State('filter-trigger', 'data'),
        State('session-id', 'data'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ])
def update_filter(
    slider_arg,
    cat_values,
    num_values,
    colormap,
    visible_list,
    c_key,
    overlay_enable,
    outline_enable,
    click_data,
    _,
    click_hide,
    trigger_idx,
    session_id,
    case,
    file,
):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    config = redis_get(session_id, REDIS_KEYS['config'])
    keys_dict = config['keys']

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    filter_kwargs['num_values'] = num_values
    filter_kwargs['cat_values'] = cat_values
    redis_set(filter_kwargs, session_id, REDIS_KEYS['filter_kwargs'])

    if trigger_id == 'scatter3d' and \
            ((not click_hide) or
                (click_data['points'][0]['curveNumber'] != 0)):
        raise PreventUpdate

    if (trigger_id == 'slider-frame'):
        fig_idx = redis_get(session_id, REDIS_KEYS['figure_idx'])
        if fig_idx is not None:
            if slider_arg <= fig_idx:
                return [redis_get(session_id,
                                  REDIS_KEYS['figure'],
                                  str(slider_arg)),
                        dash.no_update]

    c_label = keys_dict[c_key]['description']

    slider_label = keys_dict[config['slider']
                             ]['description']

    x_det = config.get('x_3d', num_keys[0])
    y_det = config.get('y_3d', num_keys[1])
    z_det = config.get('z_3d', num_keys[2])
    x_host = config.get('x_ref', None)
    y_host = config.get('y_ref', None)

    visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])
    frame_list = redis_get(session_id, REDIS_KEYS['frame_list'])

    if trigger_id == 'scatter3d' and click_hide and \
            click_data['points'][0]['curveNumber'] == 0:
        if visible_table['_VIS_'][
            click_data['points'][0]['id']
        ] == 'visible':
            visible_table.at[click_data['points']
                             [0]['id'], '_VIS_'] = 'hidden'
        else:
            visible_table.at[click_data['points']
                             [0]['id'], '_VIS_'] = 'visible'

        redis_set(visible_table, session_id, REDIS_KEYS['visible_table'])

    if overlay_enable:
        file = json.loads(file)
        data = pd.read_feather('./data/' +
                               case +
                               file['path'] +
                               '/' +
                               file['feather_name'])
        source_encoded = None
    else:
        file = json.loads(file)
        data = redis_get(session_id, REDIS_KEYS['frame_data'], str(
            frame_list[slider_arg]))

        img = './data/' +\
            case +\
            file['path'] +\
            '/imgs/' + \
            file['name'][0:-4] + \
            '_' +\
            str(slider_arg) +\
            '.jpg'

        try:
            encoded_image = base64.b64encode(open(img, 'rb').read())
            source_encoded = 'data:image/jpeg;base64,{}'.format(
                encoded_image.decode())
        except FileNotFoundError:
            source_encoded = None

    if outline_enable:
        linewidth = 1
    else:
        linewidth = 0

    x_range = [
        float(
            np.min([num_values[num_keys.index(x_det)][0],
                    num_values[num_keys.index(x_host)][0]])),
        float(
            np.max([num_values[num_keys.index(x_det)][1],
                    num_values[num_keys.index(x_host)][1]]))]
    y_range = [
        float(
            np.min([num_values[num_keys.index(y_det)][0],
                    num_values[num_keys.index(y_host)][0]])),
        float(
            np.max([num_values[num_keys.index(y_det)][1],
                    num_values[num_keys.index(y_host)][1]]))]
    z_range = [
        float(num_values[num_keys.index(z_det)][0]),
        float(num_values[num_keys.index(z_det)][1])]

    if keys_dict[c_key].get('type', KEY_TYPES['NUM']) == KEY_TYPES['NUM']:
        c_range = [
            num_values[num_keys.index(c_key)][0],
            num_values[num_keys.index(c_key)][1]
        ]
    else:
        c_range = [0, 0]

    if trigger_id != 'slider-frame':
        celery_filtering_data.apply_async(
            args=[session_id,
                  case,
                  file,
                  visible_list,
                  c_key,
                  linewidth,
                  c_label,
                  slider_label,
                  colormap], serializer='json')

    filterd_frame = filter_all(
        data,
        num_keys,
        num_values,
        cat_keys,
        cat_values,
        visible_table,
        visible_list
    )

    fig = get_scatter3d(
        filterd_frame,
        x_det,
        y_det,
        z_det,
        c_key,
        x_ref=x_host,
        y_ref=y_host,
        hover=keys_dict,
        name='Index: ' + str(slider_arg) + ' (' +
        slider_label+': '+str(frame_list[slider_arg])+')',
        c_label=c_label,
        linewidth=linewidth,
        colormap=colormap,
        c_type=keys_dict[c_key].get('type', KEY_TYPES['NUM']),
        image=source_encoded,
        x_range=x_range,
        y_range=y_range,
        z_range=z_range,
        c_range=c_range,
        ref_name='Host Vehicle'
    )

    if (trigger_id == 'slider-frame') or \
        (trigger_id == 'left-hide-trigger') or \
            (trigger_id == 'colormap-3d') or \
            (trigger_id == 'outline-switch'):
        filter_trig = dash.no_update
    elif trigger_id == 'scatter3d':
        if click_hide and \
                click_data['points'][0]['curveNumber'] == 0:
            filter_trig = trigger_idx+1
        else:
            filter_trig = dash.no_update
    else:
        filter_trig = trigger_idx+1

    return [fig, filter_trig]


@ app.callback(
    [
        Output('scatter2d-left', 'figure'),
        Output('x-picker-2d-left', 'disabled'),
        Output('y-picker-2d-left', 'disabled'),
        Output('c-picker-2d-left', 'disabled'),
        Output('colormap-scatter2d-left', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('left-switch', 'value'),
        Input('x-picker-2d-left', 'value'),
        Input('y-picker-2d-left', 'value'),
        Input('c-picker-2d-left', 'value'),
        Input('colormap-scatter2d-left', 'value'),
        Input('outline-switch', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_left_graph(
    unused1,
    unused2,
    left_sw,
    x_left,
    y_left,
    color_left,
    colormap,
    outline_enable,
    session_id,
    visible_list,
    case,
    file
):
    config = redis_get(session_id, REDIS_KEYS['config'])

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    x_key = x_left
    y_key = y_left
    c_key = color_left
    x_label = config['keys'][x_left]['description']
    y_label = config['keys'][y_left]['description']
    c_label = config['keys'][color_left]['description']

    if outline_enable:
        linewidth = 1
    else:
        linewidth = 0

    if left_sw:
        file = json.loads(file)
        data = pd.read_feather('./data/' +
                               case +
                               file['path'] +
                               '/' +
                               file['feather_name'])
        visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])

        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list
        )

        left_fig = get_scatter2d(
            filtered_table,
            x_key,
            y_key,
            c_key,
            x_label,
            y_label,
            c_label,
            colormap=colormap,
            linewidth=linewidth,
            c_type=config['keys'][c_key].get('type', KEY_TYPES['NUM'])
        )
        left_x_disabled = False
        left_y_disabled = False
        left_color_disabled = False
        colormap_disable = False

    else:
        left_fig = {
            'data': [{'mode': 'markers',
                      'type': 'scattergl',
                      'x': [],
                      'y': []}
                     ],
            'layout': {
            }}
        left_x_disabled = True
        left_y_disabled = True
        left_color_disabled = True
        colormap_disable = True

    return [
        left_fig,
        left_x_disabled,
        left_y_disabled,
        left_color_disabled,
        colormap_disable
    ]


@ app.callback(
    [
        Output('scatter2d-right', 'figure'),
        Output('x-picker-2d-right', 'disabled'),
        Output('y-picker-2d-right', 'disabled'),
        Output('c-picker-2d-right', 'disabled'),
        Output('colormap-scatter2d-right', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('right-switch', 'value'),
        Input('x-picker-2d-right', 'value'),
        Input('y-picker-2d-right', 'value'),
        Input('c-picker-2d-right', 'value'),
        Input('colormap-scatter2d-right', 'value'),
        Input('outline-switch', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_right_graph(
    unused1,
    unused2,
    right_sw,
    x_right,
    y_right,
    color_right,
    colormap,
    outline_enable,
    session_id,
    visible_list,
    case,
    file
):
    config = redis_get(session_id, REDIS_KEYS['config'])
    keys_dict = config['keys']

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    x_key = x_right
    y_key = y_right
    c_key = color_right
    x_label = keys_dict[x_right]['description']
    y_label = keys_dict[y_right]['description']
    c_label = keys_dict[color_right]['description']

    if outline_enable:
        linewidth = 1
    else:
        linewidth = 0

    if right_sw:
        file = json.loads(file)
        data = pd.read_feather('./data/' +
                               case +
                               file['path'] +
                               '/' +
                               file['feather_name'])
        visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])
        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list
        )

        right_fig = get_scatter2d(
            filtered_table,
            x_key,
            y_key,
            c_key,
            x_label,
            y_label,
            c_label,
            colormap=colormap,
            linewidth=linewidth,
            c_type=keys_dict[c_key].get('type', KEY_TYPES['NUM'])
        )
        right_x_disabled = False
        right_y_disabled = False
        right_color_disabled = False
        colormap_disable = False

    else:
        right_fig = {
            'data': [{'mode': 'markers',
                      'type': 'scattergl',
                      'x': [],
                      'y': []}
                     ],
            'layout': {
            }}

        right_x_disabled = True
        right_y_disabled = True
        right_color_disabled = True
        colormap_disable = True

    return [
        right_fig,
        right_x_disabled,
        right_y_disabled,
        right_color_disabled,
        colormap_disable,
    ]


@ app.callback(
    [
        Output('histogram', 'figure'),
        Output('x-picker-histogram', 'disabled'),
        Output('y-histogram', 'disabled'),
        Output('c-picker-histogram', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('histogram-switch', 'value'),
        Input('x-picker-histogram', 'value'),
        Input('y-histogram', 'value'),
        Input('c-picker-histogram', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_histogram(
    unused1,
    unused2,
    histogram_sw,
    x_histogram,
    y_histogram,
    c_histogram,
    session_id,
    visible_list,
    case,
    file
):
    config = redis_get(session_id, REDIS_KEYS['config'])

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    x_key = x_histogram
    x_label = config['keys'][x_histogram]['description']
    y_key = y_histogram

    if histogram_sw:
        file = json.loads(file)
        data = pd.read_feather('./data/' +
                               case +
                               file['path'] +
                               '/' +
                               file['feather_name'])
        visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])
        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list
        )

        if y_key == 'probability':
            y_label = 'Probability'
        elif y_key == 'density':
            y_label = 'Density'
        if c_histogram == 'None':
            histogram_fig = px.histogram(filtered_table,
                                         x=x_key,
                                         histnorm=y_key,
                                         opacity=1,
                                         barmode='stack',
                                         labels={x_key: x_label,
                                                 y_key: y_label})
        else:
            histogram_fig = px.histogram(filtered_table,
                                         x=x_key,
                                         color=c_histogram,
                                         histnorm=y_key,
                                         opacity=1,
                                         barmode='stack',
                                         labels={x_key: x_label,
                                                 y_key: y_label})
        histogram_x_disabled = False
        histogram_y_disabled = False
        histogram_c_disabled = False
    else:
        histogram_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
            }}
        histogram_x_disabled = True
        histogram_y_disabled = True
        histogram_c_disabled = True

    return [
        histogram_fig,
        histogram_x_disabled,
        histogram_y_disabled,
        histogram_c_disabled
    ]


@ app.callback(
    [
        Output('violin', 'figure'),
        Output('x-picker-violin', 'disabled'),
        Output('y-picker-violin', 'disabled'),
        Output('c-picker-violin', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('violin-switch', 'value'),
        Input('x-picker-violin', 'value'),
        Input('y-picker-violin', 'value'),
        Input('c-picker-violin', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_violin(
    unused1,
    unused2,
    violin_sw,
    x_violin,
    y_violin,
    c_violin,
    session_id,
    visible_list,
    case,
    file
):
    config = redis_get(session_id, REDIS_KEYS['config'])

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    x_key = x_violin
    if x_violin is None:
        raise PreventUpdate

    x_label = config['keys'][x_violin].get('description', x_key)
    y_key = y_violin
    y_label = config['keys'][y_violin].get('description', y_key)

    if violin_sw:
        file = json.loads(file)
        data = pd.read_feather('./data/' +
                               case +
                               file['path'] +
                               '/' +
                               file['feather_name'])
        visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])
        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list
        )

        if c_violin == 'None':
            violin_fig = px.violin(filtered_table,
                                   x=x_key,
                                   y=y_key,
                                   box=True,
                                   violinmode='group',
                                   labels={x_key: x_label,
                                           y_key: y_label})
        else:
            violin_fig = px.violin(filtered_table,
                                   x=x_key,
                                   y=y_key,
                                   color=c_violin,
                                   box=True,
                                   violinmode='group',
                                   labels={x_key: x_label,
                                           y_key: y_label})
        violin_x_disabled = False
        violin_y_disabled = False
        violin_c_disabled = False
    else:
        violin_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
            }}
        violin_x_disabled = True
        violin_y_disabled = True
        violin_c_disabled = True

    return [
        violin_fig,
        violin_x_disabled,
        violin_y_disabled,
        violin_c_disabled
    ]


@ app.callback(
    [
        Output('parallel', 'figure'),
        Output('dim-picker-parallel', 'disabled'),
        Output('c-picker-parallel', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('parallel-switch', 'value'),
        Input('dim-picker-parallel', 'value'),
        Input('c-picker-parallel', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_parallel(
    unused1,
    unused2,
    parallel_sw,
    dim_parallel,
    c_key,
    session_id,
    visible_list,
    case,
    file
):
    config = redis_get(session_id, REDIS_KEYS['config'])

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    if parallel_sw and len(dim_parallel) > 0:
        file = json.loads(file)
        data = pd.read_feather('./data/' +
                               case +
                               file['path'] +
                               '/' +
                               file['feather_name'])
        visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])
        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list
        )

        dims = []
        for _, dim_key in enumerate(dim_parallel):
            dims.append(go.parcats.Dimension(
                values=filtered_table[dim_key], label=dim_key))

        if c_key != 'None':
            colorscale = []
            unique_list = np.sort(filtered_table[c_key].unique())

            if np.issubdtype(unique_list.dtype, np.integer) or \
                    np.issubdtype(unique_list.dtype, np.floating):
                parallel_fig = go.Figure(
                    data=[go.Parcats(dimensions=dims,
                                     line={'color': filtered_table[c_key],
                                           'colorbar':dict(
                                         title=c_key)},
                                     hoveron='color',
                                     hoverinfo='count+probability',
                                     arrangement='freeform')])
            else:
                filtered_table['_C_'] = np.zeros_like(filtered_table[c_key])
                for idx, var in enumerate(unique_list):
                    filtered_table.loc[filtered_table[c_key]
                                       == var, '_C_'] = idx

                parallel_fig = go.Figure(
                    data=[go.Parcats(dimensions=dims,
                                     line={'color': filtered_table['_C_']},
                                     hoverinfo='count+probability',
                                     arrangement='freeform')])
        else:
            parallel_fig = go.Figure(data=[go.Parcats(dimensions=dims,
                                                      arrangement='freeform')])

        parallel_dim_disabled = False
        parallel_c_disabled = False
    else:
        parallel_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
            }}
        parallel_dim_disabled = True
        parallel_c_disabled = True

    return [
        parallel_fig,
        parallel_dim_disabled,
        parallel_c_disabled
    ]


@ app.callback(
    [
        Output('heatmap', 'figure'),
        Output('x-picker-heatmap', 'disabled'),
        Output('y-picker-heatmap', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('heat-switch', 'value'),
        Input('x-picker-heatmap', 'value'),
        Input('y-picker-heatmap', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_heatmap(
    unused1,
    unused2,
    heat_sw,
    x_heat,
    y_heat,
    session_id,
    visible_list,
    case,
    file
):
    if heat_sw:
        config = redis_get(session_id, REDIS_KEYS['config'])

        filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
        cat_keys = filter_kwargs['cat_keys']
        num_keys = filter_kwargs['num_keys']
        cat_values = filter_kwargs['cat_values']
        num_values = filter_kwargs['num_values']

        x_key = x_heat
        x_label = config['keys'][x_heat]['description']
        y_key = y_heat
        y_label = config['keys'][y_heat]['description']

        file = json.loads(file)
        data = pd.read_feather('./data/' +
                               case +
                               file['path'] +
                               '/' +
                               file['feather_name'])
        visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])

        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list
        )

        heat_fig = get_heatmap(
            filtered_table,
            x_key,
            y_key,
            x_label,
            y_label,
        )
        heat_x_disabled = False
        heat_y_disabled = False
    else:
        heat_fig = {
            'data': [{'type': 'histogram2dcontour',
                      'x': []}
                     ],
            'layout': {
            }}
        heat_x_disabled = True
        heat_y_disabled = True

    return [
        heat_fig,
        heat_x_disabled,
        heat_y_disabled,
    ]


@ app.callback(
    Output('hidden-scatter3d', 'children'),
    Input('export-scatter3d', 'n_clicks'),
    [
        State('case-picker', 'value'),
        State('session-id', 'data'),
        State('c-picker-3d', 'value'),
        State('colormap-3d', 'value'),
        State('visible-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def export_scatter_3d(
    btn,
    case,
    session_id,
    c_key,
    colormap,
    visible_list,
    file
):
    if btn == 0:
        raise PreventUpdate

    config = redis_get(session_id, REDIS_KEYS['config'])

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    if not os.path.exists('data/' +
                          case +
                          '/images'):
        os.makedirs('data/' +
                    case +
                    '/images')

    file = json.loads(file)
    data = pd.read_feather('./data/' +
                           case +
                           file['path'] +
                           '/' +
                           file['feather_name'])
    visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])

    x_det = config.get('x_3d', num_keys[0])
    y_det = config.get('y_3d', num_keys[1])
    z_det = config.get('z_3d', num_keys[2])
    x_host = config.get('x_ref', None)
    y_host = config.get('y_ref', None)

    filtered_table = filter_all(
        data,
        num_keys,
        num_values,
        cat_keys,
        cat_values,
        visible_table,
        visible_list
    )

    frame_list = redis_get(session_id, REDIS_KEYS['frame_list'])
    frame_list = filtered_table[config['slider']].unique()
    img_list = []

    data_name = json.loads(file)
    for _, f_val in enumerate(frame_list):
        img_idx = np.where(frame_list == f_val)[0][0]
        img_list.append('./data/' +
                        case +
                        data_name['path'] +
                        '/imgs/' +
                        data_name['name'][0:-4] +
                        '_' +
                        str(img_idx) +
                        '.jpg')

    fig = go.Figure(
        get_animation_data(
            filtered_table,
            x_key=x_det,
            y_key=y_det,
            z_key=z_det,
            host_x_key=x_host,
            host_y_key=y_host,
            img_list=img_list,
            c_key=c_key,
            c_type=config['keys'][c_key].get('type', KEY_TYPES['NUM']),
            colormap=colormap,
            hover=config['keys'],
            title=data_name['name'][0:-4],
            c_label=config['keys'][c_key]['description'],
            height=750
        )
    )

    fig.write_html('data/' +
                   case +
                   '/images/' +
                   timestamp +
                   '_' +
                   data_name['name'][0:-4] +
                   '_3dview.html')
    return 0


@ app.callback(
    Output('dummy-export-scatter2d-left', 'data'),
    Input('export-scatter2d-left', 'n_clicks'),
    [
        State('scatter2d-left', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_left_scatter_2d(btn, fig, case):
    if btn == 0:
        raise PreventUpdate

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    if not os.path.exists('data/'+case+'/images'):
        os.makedirs('data/'+case+'/images')

    temp_fig = go.Figure(fig)
    temp_fig.write_image('data/'+case+'/images/' +
                         timestamp+'_fig_left.png', scale=2)
    return 0


@ app.callback(
    Output('dummy-export-scatter2d-right', 'data'),
    Input('export-scatter2d-right', 'n_clicks'),
    [
        State('scatter2d-right', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_right_scatter_2d(btn, fig, case):
    if btn == 0:
        raise PreventUpdate

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    if not os.path.exists('data/'+case+'/images'):
        os.makedirs('data/'+case+'/images')

    temp_fig = go.Figure(fig)
    temp_fig.write_image('data/'+case+'/images/' +
                         timestamp+'_fig_right.png', scale=2)
    return 0


@ app.callback(
    Output('dummy-export-histogram', 'data'),
    Input('export-histogram', 'n_clicks'),
    [
        State('histogram', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_histogram(btn, fig, case):
    if btn == 0:
        raise PreventUpdate

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    if not os.path.exists('data/'+case+'/images'):
        os.makedirs('data/'+case+'/images')

    temp_fig = go.Figure(fig)
    temp_fig.write_image('data/'+case+'/images/' +
                         timestamp+'_histogram.png', scale=2)
    return 0


@ app.callback(
    Output('dummy-export-violin', 'data'),
    Input('export-violin', 'n_clicks'),
    [
        State('violin', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_violin(btn, fig, case):
    if btn == 0:
        raise PreventUpdate

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    if not os.path.exists('data/'+case+'/images'):
        os.makedirs('data/'+case+'/images')

    temp_fig = go.Figure(fig)
    temp_fig.write_image('data/'+case+'/images/' +
                         timestamp+'_violin.png', scale=2)
    return 0


@ app.callback(
    Output('dummy-export-parallel', 'data'),
    Input('export-parallel', 'n_clicks'),
    [
        State('parallel', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_parallel(btn, fig, case):
    if btn == 0:
        raise PreventUpdate

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    if not os.path.exists('data/'+case+'/images'):
        os.makedirs('data/'+case+'/images')

    temp_fig = go.Figure(fig)
    temp_fig.write_image('data/'+case+'/images/' +
                         timestamp+'_parallel.png', scale=2)
    return 0


@ app.callback(
    Output('dummy-export-data', 'data'),
    Input('export-data', 'n_clicks'),
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def export_data(btn,
                session_id,
                visible_list,
                case,
                file):
    if btn == 0:
        raise PreventUpdate

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    config = redis_get(session_id, REDIS_KEYS['config'])

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    file = json.loads(file)
    data = pd.read_feather('./data/' +
                           case +
                           file['path'] +
                           '/' +
                           file['feather_name'])
    visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])

    filtered_table = filter_all(
        data,
        num_keys,
        num_values,
        cat_keys,
        cat_values,
        visible_table,
        visible_list
    )

    filtered_table.to_pickle('./data/' +
                             case +
                             file['path'] +
                             '/' +
                             file['name'][0:-4]+'_filtered.pkl')

    return 0


@ app.callback(
    Output('dummy-export-heatmap', 'data'),
    Input('export-heatmap', 'n_clicks'),
    [
        State('heatmap', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_heatmap(btn, fig, case):
    if btn == 0:
        raise PreventUpdate

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    if not os.path.exists('data/'+case+'/images'):
        os.makedirs('data/'+case+'/images')

    temp_fig = go.Figure(fig)
    temp_fig.write_image('data/'+case+'/images/' +
                         timestamp+'_heatmap.png', scale=2)
    return 0


@app.callback(
    Output('selected-data-left', 'data'),
    Input('scatter2d-left', 'selectedData')
)
def select_left_figure(selectedData):
    return selectedData


@app.callback(
    Output('left-hide-trigger', 'data'),
    Input('hide-left', 'n_clicks'),
    [
        State('selected-data-left', 'data'),
        State('left-hide-trigger', 'data'),
        State('session-id', 'data'),
    ]
)
def left_hide_button(
    btn,
    selectedData,
    trigger_idx,
    session_id
):
    if btn == 0:
        raise PreventUpdate

    if selectedData is None:
        raise PreventUpdate

    visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])

    s_data = pd.DataFrame(selectedData['points'])
    idx = s_data['id']
    idx.index = idx

    vis_idx = idx[visible_table['_VIS_'][idx] == 'visible']
    hid_idx = idx[visible_table['_VIS_'][idx] == 'hidden']

    visible_table.loc[vis_idx, '_VIS_'] = 'hidden'
    visible_table.loc[hid_idx, '_VIS_'] = 'visible'

    redis_set(visible_table, session_id, REDIS_KEYS['visible_table'])

    return trigger_idx+1


@app.callback(
    Output('buffer', 'value'),
    Input('buffer-interval', 'n_intervals'),
    [
        State('slider-frame', 'max'),
        State('session-id', 'data'),
    ]
)
def update_buffer_indicator(
    _,
    max_frame,
    session_id
):
    if max_frame is None:
        raise PreventUpdate

    fig_idx = redis_get(session_id, REDIS_KEYS['figure_idx'])
    if fig_idx is not None:
        return fig_idx/max_frame*100
    else:
        return 0


if __name__ == '__main__':
    app.run_server(debug=True, threaded=True, processes=1, host='0.0.0.0')
