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

import json
import os

import pandas as pd
import numpy as np

import dash
from maindash import app
from maindash import SPECIAL_FOLDERS
from maindash import DROPDOWN_OPTIONS_ALL, DROPDOWN_VALUES_ALL
from maindash import DROPDOWN_OPTIONS_CAT, DROPDOWN_VALUES_CAT
from maindash import DROPDOWN_OPTIONS_CAT_COLOR, DROPDOWN_VALUES_CAT_COLOR
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from utils import load_config, redis_set, redis_get, REDIS_KEYS, KEY_TYPES

import dash_bootstrap_components as dbc
from dash import dcc

from tasks import celery_filtering_data


@app.callback(
    [
        Output('case-picker', 'options'),
        Output('case-picker', 'value'),
    ],
    Input('refresh-button', 'n_clicks')
)
def refresh_button_clicked(unused):
    """
    Callback when the refresh button is clicked

        Scan all the folders under './data' with 'config.json' inside

    :param unused:
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
            # only add the folder with 'config.json'
            if os.path.exists('./data/' +
                              entry.name +
                              '/config.json'):
                options.append({'label': entry.name,
                                'value': entry.name})

    return [options, options[0]['value']]


@app.callback([
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


@app.callback(
    [
        Output('slider-frame', 'value'),
        Output('slider-frame', 'min'),
        Output('slider-frame', 'max'),
        Output('dropdown-container', 'children'),
        Output('slider-container', 'children'),
        Output('dim-picker-parallel', 'options'),
        Output('dim-picker-parallel', 'value'),
    ],
    [
        Input('file-picker', 'value'),
        Input('previous-button', 'n_clicks'),
        Input('next-button', 'n_clicks'),
        Input('interval-component', 'n_intervals')
    ],
    [
        State('decay-slider', 'value'),
        State('case-picker', 'value'),
        State('session-id', 'data'),
        State('slider-frame', 'max'),
        State('slider-frame', 'value'),
        State('visible-picker', 'value'),
        State('c-picker-3d', 'value'),
        State('outline-switch', 'value'),
        State('colormap-3d', 'value'),
        State('darkmode-switch', 'value'),
    ])
def file_selected(
        file,
        left_btn,
        right_btn,
        interval,
        decay,
        case,
        session_id,
        slider_max,
        slider_var,
        visible_list,
        c_key,
        outline_enable,
        colormap,
        darkmode
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
    :param int decay
        number additional frames to display
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
            # use `.tolist()` to convert numpy type ot python type
            var_min = np.floor(np.min(new_data[item])).tolist()
            var_max = np.ceil(np.max(new_data[item])).tolist()

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

        task_kwargs = dict()
        # outline width
        if outline_enable:
            task_kwargs['linewidth'] = 1
        else:
            task_kwargs['linewidth'] = 0

        task_kwargs['c_key'] = c_key
        task_kwargs['colormap'] = colormap
        task_kwargs['decay'] = decay
        if darkmode:
            task_kwargs['template'] = 'plotly_dark'
        else:
            task_kwargs['template'] = 'plotly'

        # invoke celery task
        redis_set(0, session_id, REDIS_KEYS['task_id'])
        redis_set(-1, session_id, REDIS_KEYS['figure_idx'])
        celery_filtering_data.apply_async(
            args=[session_id,
                  case,
                  file,
                  visible_list], kwargs=task_kwargs, serializer='json')

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
                    dash.no_update,
                    dash.no_update]

        else:
            return [(slider_var+1) % (slider_max+1),
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update]


@app.callback(
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