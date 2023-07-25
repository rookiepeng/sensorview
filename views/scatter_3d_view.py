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

import base64

import numpy as np

import dash
from maindash import app
from dash.dependencies import Input, Output, State,  ALL
from dash.exceptions import PreventUpdate

from tasks import filter_all
from tasks import celery_filtering_data, celery_export_video

from utils import cache_set, cache_get, CACHE_KEYS, KEY_TYPES
from utils import load_data

from viz.viz import get_scatter3d
from viz.graph_data import get_scatter3d_data, get_ref_scatter3d_data
from viz.graph_layout import get_scatter3d_layout


def prepare_figure_kwargs(
    config,
    frame_list,
    colormap,
    outline_enable,
    darkmode,
    slider_arg,
    c_key,
    num_keys,
    num_values,
):
    keys_dict = config['keys']
    # prepare figure key word arguments
    fig_kwargs = dict()
    fig_kwargs['hover'] = keys_dict
    fig_kwargs['image'] = None

    # set outline width
    if outline_enable:
        fig_kwargs['linewidth'] = 1
    else:
        fig_kwargs['linewidth'] = 0

    if darkmode:
        fig_kwargs['template'] = 'plotly_dark'
    else:
        fig_kwargs['template'] = 'plotly'

    fig_kwargs['x_key'] = config.get('x_3d', num_keys[0])
    fig_kwargs['x_label'] = keys_dict[fig_kwargs['x_key']].get(
        'description', fig_kwargs['x_key'])
    fig_kwargs['y_key'] = config.get('y_3d', num_keys[1])
    fig_kwargs['y_label'] = keys_dict[fig_kwargs['y_key']].get(
        'description', fig_kwargs['y_key'])
    fig_kwargs['z_key'] = config.get('z_3d', num_keys[2])
    fig_kwargs['z_label'] = keys_dict[fig_kwargs['z_key']].get(
        'description', fig_kwargs['z_key'])
    fig_kwargs['c_key'] = c_key
    fig_kwargs['c_label'] = keys_dict[fig_kwargs['c_key']].get(
        'description', fig_kwargs['c_key'])
    fig_kwargs['x_ref'] = config.get('x_ref', None)
    fig_kwargs['y_ref'] = config.get('y_ref', None)

    # set graph's range the same for all the frames
    if (fig_kwargs['x_ref'] is not None) and (fig_kwargs['y_ref'] is not None):
        fig_kwargs['x_range'] = [
            min([num_values[num_keys.index(fig_kwargs['x_key'])][0],
                 num_values[num_keys.index(fig_kwargs['x_ref'])][0]]),
            max([num_values[num_keys.index(fig_kwargs['x_key'])][1],
                 num_values[num_keys.index(fig_kwargs['x_ref'])][1]])
        ]
        fig_kwargs['y_range'] = [
            min([num_values[num_keys.index(fig_kwargs['y_key'])][0],
                 num_values[num_keys.index(fig_kwargs['y_ref'])][0]]),
            max([num_values[num_keys.index(fig_kwargs['y_key'])][1],
                 num_values[num_keys.index(fig_kwargs['y_ref'])][1]])
        ]
    else:
        fig_kwargs['x_range'] = [
            num_values[num_keys.index(fig_kwargs['x_key'])][0],
            num_values[num_keys.index(fig_kwargs['x_key'])][1]
        ]
        fig_kwargs['y_range'] = [
            num_values[num_keys.index(fig_kwargs['y_key'])][0],
            num_values[num_keys.index(fig_kwargs['y_key'])][1]
        ]
    fig_kwargs['z_range'] = [
        num_values[num_keys.index(fig_kwargs['z_key'])][0],
        num_values[num_keys.index(fig_kwargs['z_key'])][1]
    ]

    if keys_dict[c_key].get('type', KEY_TYPES['NUM']) == KEY_TYPES['NUM']:
        fig_kwargs['c_range'] = [
            num_values[num_keys.index(c_key)][0],
            num_values[num_keys.index(c_key)][1]
        ]
    else:
        fig_kwargs['c_range'] = [0, 0]

    slider_label = keys_dict[config['slider']]['description']
    fig_kwargs['name'] = 'Index: ' +\
        str(slider_arg) +\
        ' (' +\
        slider_label +\
        ': ' +\
        str(frame_list[slider_arg]) +\
        ')'
    fig_kwargs['colormap'] = colormap
    fig_kwargs['c_type'] = keys_dict[c_key].get('type', KEY_TYPES['NUM'])
    fig_kwargs['ref_name'] = 'Host Vehicle'

    return fig_kwargs


def process_single_frame(
        slider_arg,
        config,
        cat_values,
        num_values,
        colormap,
        visible_list,
        c_key,
        overlay_enable,
        outline_enable,
        decay,
        darkmode,
        session_id,
        case,
        file,
        file_list):

    keys_dict = config['keys']

    opacity = np.linspace(1, 0.2, decay+1)

    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    filter_kwargs['num_values'] = num_values
    filter_kwargs['cat_values'] = cat_values
    cache_set(filter_kwargs, session_id, CACHE_KEYS['filter_kwargs'])

    # get visibility table from Redis
    visible_table = cache_get(session_id, CACHE_KEYS['visible_table'])

    # get frame list from Redis
    frame_list = cache_get(session_id, CACHE_KEYS['frame_list'])

    # prepare figure key word arguments
    fig_kwargs = prepare_figure_kwargs(
        config,
        frame_list,
        colormap,
        outline_enable,
        darkmode,
        slider_arg,
        c_key,
        num_keys,
        num_values,
    )

    if overlay_enable:
        # overlay all the frames
        # get data from .feather file on the disk
        data = load_data(file, file_list, case)
        filterd_frame = filter_all(data,
                                   num_keys,
                                   num_values,
                                   cat_keys,
                                   cat_values,
                                   visible_table,
                                   visible_list)
        fig_kwargs['image'] = None

        # generate the graph
        fig = get_scatter3d(
            filterd_frame,
            **fig_kwargs
        )
    else:
        file = json.loads(file)
        img_path = './data/' +\
            case +\
            file['path'] +\
            '/'+file['name'][0:-4]+'/' + \
            str(slider_arg) +\
            '.jpg'

        # encode image frame
        try:
            encoding = base64.b64encode(open(img_path, 'rb').read())
            fig_kwargs['image'] = 'data:image/jpeg;base64,{}'.format(
                encoding.decode())
        except FileNotFoundError:
            fig_kwargs['image'] = None
        except NotADirectoryError:
            fig_kwargs['image'] = None

        # get a single frame data from Redis
        data = cache_get(session_id,
                         CACHE_KEYS['frame_data'],
                         str(frame_list[slider_arg]))

        filterd_frame = filter_all(data,
                                   num_keys,
                                   num_values,
                                   cat_keys,
                                   cat_values,
                                   visible_table,
                                   visible_list)
        fig = get_scatter3d_data(
            filterd_frame,
            **fig_kwargs
        )

        if decay > 0:
            for val in range(1, decay+1):
                if (slider_arg-val) >= 0:
                    # filter the data
                    frame_temp = filter_all(
                        cache_get(session_id,
                                  CACHE_KEYS['frame_data'],
                                  str(frame_list[slider_arg-val])),
                        num_keys,
                        num_values,
                        cat_keys,
                        cat_values,
                        visible_table,
                        visible_list
                    )
                    fig_kwargs['opacity'] = opacity[val]
                    fig_kwargs['name'] = 'Index: ' +\
                        str(slider_arg-val) +\
                        ' (' +\
                        keys_dict[config['slider']]['description'] +\
                        ': ' +\
                        str(frame_list[slider_arg-val]) +\
                        ')'
                    fig = fig+get_scatter3d_data(
                        frame_temp,
                        **fig_kwargs
                    )

                else:
                    break

        if fig_kwargs['x_ref'] is not None and fig_kwargs['y_ref'] is not None:
            fig_ref = [
                get_ref_scatter3d_data(
                    data_frame=filterd_frame,
                    x_key=fig_kwargs['x_ref'],
                    y_key=fig_kwargs['y_ref'],
                    z_key=None,
                    name=fig_kwargs.get('ref_name', None))
            ]
        else:
            fig_ref = []

        layout = get_scatter3d_layout(**fig_kwargs)

        fig = dict(
            data=fig_ref+fig,
            layout=layout
        )

    return fig


@app.callback(
    output=dict(
        scatter3d=Output('scatter3d', 'figure', allow_duplicate=True),
    ),
    inputs=dict(
        slider_arg=Input('slider-frame', 'value'),
        overlay_enable=Input('overlay-switch', 'value'),
        decay=Input('decay-slider', 'value'),
    ),
    state=dict(
        cat_values=State({'type': 'filter-dropdown', 'index': ALL}, 'value'),
        num_values=State({'type': 'filter-slider', 'index': ALL}, 'value'),
        colormap=State('colormap-3d', 'value'),
        visible_list=State('visible-picker', 'value'),
        c_key=State('c-picker-3d', 'value'),
        outline_enable=State('outline-switch', 'value'),
        click_data=State('scatter3d', 'clickData'),
        left_hide_trigger=State('left-hide-trigger', 'data'),
        darkmode=State('darkmode-switch', 'value'),
        click_hide=State('click-hide-switch', 'value'),
        trigger_idx=State('filter-trigger', 'data'),
        session_id=State('session-id', 'data'),
        case=State('case-picker', 'value'),
        file=State('file-picker', 'value'),
        file_list=State('file-add', 'value')
    ),
    prevent_initial_call=True,
)
def slider_change_callback(
        slider_arg,
        cat_values,
        num_values,
        colormap,
        visible_list,
        c_key,
        overlay_enable,
        outline_enable,
        click_data,
        left_hide_trigger,
        decay,
        darkmode,
        click_hide,
        trigger_idx,
        session_id,
        case,
        file,
        file_list):

    fig_idx = cache_get(session_id, CACHE_KEYS['figure_idx'])

    opacity = np.linspace(1, 0.2, decay+1)

    # if slider value changed
    #   - if Redis `figure` buffer ready, return figure from Redis
    if fig_idx is not None:
        if slider_arg <= fig_idx:
            fig = cache_get(session_id,
                            CACHE_KEYS['figure'],
                            str(slider_arg))
            if decay > 0:
                for val in range(1, decay+1):
                    if (slider_arg-val) >= 0:
                        new_fig = cache_get(session_id,
                                            CACHE_KEYS['figure'],
                                            str(slider_arg-val))
                        new_fig[0]['marker']['opacity'] = opacity[val]
                        fig = fig+new_fig

            fig_ref = cache_get(session_id,
                                CACHE_KEYS['figure_ref'],
                                str(slider_arg))
            layout = cache_get(session_id,
                               CACHE_KEYS['figure_layout'],
                               str(slider_arg))
            return dict(
                scatter3d=dict(data=fig_ref+fig,
                               layout=layout)
            )

    config = cache_get(session_id, CACHE_KEYS['config'])
    fig = process_single_frame(
        slider_arg,
        config,
        cat_values,
        num_values,
        colormap,
        visible_list,
        c_key,
        overlay_enable,
        outline_enable,
        decay,
        darkmode,
        session_id,
        case,
        file,
        file_list)

    return dict(
        scatter3d=fig
    )


@app.callback(
    output=dict(
        scatter3d=Output('scatter3d', 'figure'),
    ),
    inputs=dict(
        cat_values=Input({'type': 'filter-dropdown', 'index': ALL}, 'value'),
        num_values=Input({'type': 'filter-slider', 'index': ALL}, 'value'),
        colormap=Input('colormap-3d', 'value'),
        visible_list=Input('visible-picker', 'value'),
        c_key=Input('c-picker-3d', 'value'),
        outline_enable=Input('outline-switch', 'value'),
        click_data=Input('scatter3d', 'clickData'),
        left_hide_trigger=Input('left-hide-trigger', 'data'),
        darkmode=Input('darkmode-switch', 'value')
    ),
    state=dict(
        slider_arg=State('slider-frame', 'value'),
        overlay_enable=State('overlay-switch', 'value'),
        decay=State('decay-slider', 'value'),
        click_hide=State('click-hide-switch', 'value'),
        session_id=State('session-id', 'data'),
        case=State('case-picker', 'value'),
        file=State('file-picker', 'value'),
        file_list=State('file-add', 'value')
    )
)
def filter_changed(
    slider_arg,
    cat_values,
    num_values,
    colormap,
    visible_list,
    c_key,
    overlay_enable,
    outline_enable,
    click_data,
    left_hide_trigger,
    decay,
    darkmode,
    click_hide,
    session_id,
    case,
    file,
    file_list
):
    """
    Callback when filter changed

    :param int slider_arg
        slider position
    :param list cat_values
        selected categorical keys
    :param list num_values
        sliders range
    :param str colormap
        colormap name
    :param list visible_list
        visibility list
    :param str c_key
        key for color
    :param boolean overlay_enable
        flag to overlay all frames
    :param boolean outline_enable
        flag to enable outline for the scatters
    :param json click_data
        properties of the clicked data point
    _
    :param int decay
        number of decay frames
    :param boolean click_hide
        flag to hide the data when clicked
    :param int trigger_idx
        current trigger value
    :param str session_id
        session id
    :param str case
        case name
    :param json file
        selected file

    :return: [
        Scatter 3D graph,
        Filter trigger value (to trigger other graphs)
    ]
    :rtype: list
    """

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    # file = json.loads(file)

    # no update if:
    #   - triggered from 3D scatter, and
    #   - click_hide switch is disabled or the reference point is clicked
    if trigger_id == 'scatter3d' and \
            ((not click_hide) or
                (click_data['points'][0]['curveNumber'] == 0)):
        raise PreventUpdate
    opacity = np.linspace(1, 0.2, decay+1)

    # get config from Redis
    config = cache_get(session_id, CACHE_KEYS['config'])
    keys_dict = config['keys']

    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    filter_kwargs['num_values'] = num_values
    filter_kwargs['cat_values'] = cat_values
    cache_set(filter_kwargs, session_id, CACHE_KEYS['filter_kwargs'])

    # get visibility table from Redis
    visible_table = cache_get(session_id, CACHE_KEYS['visible_table'])

    # get frame list from Redis
    frame_list = cache_get(session_id, CACHE_KEYS['frame_list'])

    # update visibility table if a data point is clicked to hide
    if trigger_id == 'scatter3d' and \
        click_hide and \
            click_data['points'][0]['curveNumber'] > 0:

        if visible_table['_VIS_'][
            click_data['points'][0]['id']
        ] == 'visible':
            visible_table.at[
                click_data['points'][0]['id'], '_VIS_'] = 'hidden'
        else:
            visible_table.at[
                click_data['points'][0]['id'], '_VIS_'] = 'visible'

        cache_set(visible_table, session_id, CACHE_KEYS['visible_table'])

    # prepare figure key word arguments
    fig_kwargs = dict()
    fig_kwargs['hover'] = keys_dict
    fig_kwargs['image'] = None

    task_kwargs = dict()
    task_kwargs['c_key'] = c_key
    task_kwargs['colormap'] = colormap
    task_kwargs['decay'] = decay
    # set outline width
    if outline_enable:
        fig_kwargs['linewidth'] = 1
        task_kwargs['linewidth'] = 1
    else:
        fig_kwargs['linewidth'] = 0
        task_kwargs['linewidth'] = 0

    if darkmode:
        task_kwargs['template'] = 'plotly_dark'
        fig_kwargs['template'] = 'plotly_dark'
    else:
        task_kwargs['template'] = 'plotly'
        fig_kwargs['template'] = 'plotly'

    # invoke celery task
    if trigger_id != 'slider-frame' and \
        trigger_id != 'overlay-switch' and \
            trigger_id != 'decay-slider':
        cache_set(0, session_id, CACHE_KEYS['task_id'])
        cache_set(-1, session_id, CACHE_KEYS['figure_idx'])
        if file not in file_list:
            file_list.append(file)
        celery_filtering_data.apply_async(args=[session_id,
                                                case,
                                                file_list,
                                                visible_list],
                                          kwargs=task_kwargs,
                                          serializer='json')

    slider_label = keys_dict[config['slider']]['description']
    fig_kwargs['x_key'] = config.get('x_3d', num_keys[0])
    fig_kwargs['x_label'] = keys_dict[fig_kwargs['x_key']].get(
        'description', fig_kwargs['x_key'])
    fig_kwargs['y_key'] = config.get('y_3d', num_keys[1])
    fig_kwargs['y_label'] = keys_dict[fig_kwargs['y_key']].get(
        'description', fig_kwargs['y_key'])
    fig_kwargs['z_key'] = config.get('z_3d', num_keys[2])
    fig_kwargs['z_label'] = keys_dict[fig_kwargs['z_key']].get(
        'description', fig_kwargs['z_key'])
    fig_kwargs['c_key'] = c_key
    fig_kwargs['c_label'] = keys_dict[fig_kwargs['c_key']].get(
        'description', fig_kwargs['c_key'])
    fig_kwargs['x_ref'] = config.get('x_ref', None)
    fig_kwargs['y_ref'] = config.get('y_ref', None)

    # set graph's range the same for all the frames
    if (fig_kwargs['x_ref'] is not None) and (fig_kwargs['y_ref'] is not None):
        fig_kwargs['x_range'] = [
            min([num_values[num_keys.index(fig_kwargs['x_key'])][0],
                 num_values[num_keys.index(fig_kwargs['x_ref'])][0]]),
            max([num_values[num_keys.index(fig_kwargs['x_key'])][1],
                 num_values[num_keys.index(fig_kwargs['x_ref'])][1]])
        ]
        fig_kwargs['y_range'] = [
            min([num_values[num_keys.index(fig_kwargs['y_key'])][0],
                 num_values[num_keys.index(fig_kwargs['y_ref'])][0]]),
            max([num_values[num_keys.index(fig_kwargs['y_key'])][1],
                 num_values[num_keys.index(fig_kwargs['y_ref'])][1]])
        ]
    else:
        fig_kwargs['x_range'] = [
            num_values[num_keys.index(fig_kwargs['x_key'])][0],
            num_values[num_keys.index(fig_kwargs['x_key'])][1]
        ]
        fig_kwargs['y_range'] = [
            num_values[num_keys.index(fig_kwargs['y_key'])][0],
            num_values[num_keys.index(fig_kwargs['y_key'])][1]
        ]
    fig_kwargs['z_range'] = [
        num_values[num_keys.index(fig_kwargs['z_key'])][0],
        num_values[num_keys.index(fig_kwargs['z_key'])][1]
    ]

    if keys_dict[c_key].get('type', KEY_TYPES['NUM']) == KEY_TYPES['NUM']:
        fig_kwargs['c_range'] = [
            num_values[num_keys.index(c_key)][0],
            num_values[num_keys.index(c_key)][1]
        ]
    else:
        fig_kwargs['c_range'] = [0, 0]

    fig_kwargs['name'] = 'Index: ' +\
        str(slider_arg) +\
        ' (' +\
        slider_label +\
        ': ' +\
        str(frame_list[slider_arg]) +\
        ')'
    fig_kwargs['colormap'] = colormap
    fig_kwargs['c_type'] = keys_dict[c_key].get('type', KEY_TYPES['NUM'])
    fig_kwargs['ref_name'] = 'Host Vehicle'

    if overlay_enable:
        # overlay all the frames
        # get data from .feather file on the disk
        data = load_data(file, file_list, case)
        filterd_frame = filter_all(data,
                                   num_keys,
                                   num_values,
                                   cat_keys,
                                   cat_values,
                                   visible_table,
                                   visible_list)
        fig_kwargs['image'] = None

        # generate the graph
        fig = get_scatter3d(
            filterd_frame,
            **fig_kwargs
        )
    else:
        file = json.loads(file)
        img_path = './data/' +\
            case +\
            file['path'] +\
            '/'+file['name'][0:-4]+'/' + \
            str(slider_arg) +\
            '.jpg'

        # encode image frame
        try:
            encoding = base64.b64encode(open(img_path, 'rb').read())
            fig_kwargs['image'] = 'data:image/jpeg;base64,{}'.format(
                encoding.decode())
        except FileNotFoundError:
            fig_kwargs['image'] = None
        except NotADirectoryError:
            fig_kwargs['image'] = None

        # get a single frame data from Redis
        data = cache_get(session_id,
                         CACHE_KEYS['frame_data'],
                         str(frame_list[slider_arg]))

        filterd_frame = filter_all(data,
                                   num_keys,
                                   num_values,
                                   cat_keys,
                                   cat_values,
                                   visible_table,
                                   visible_list)
        fig = get_scatter3d_data(
            filterd_frame,
            **fig_kwargs
        )

        if decay > 0:
            for val in range(1, decay+1):
                if (slider_arg-val) >= 0:
                    # filter the data
                    frame_temp = filter_all(
                        cache_get(session_id,
                                  CACHE_KEYS['frame_data'],
                                  str(frame_list[slider_arg-val])),
                        num_keys,
                        num_values,
                        cat_keys,
                        cat_values,
                        visible_table,
                        visible_list
                    )
                    fig_kwargs['opacity'] = opacity[val]
                    fig_kwargs['name'] = 'Index: ' +\
                        str(slider_arg-val) +\
                        ' (' +\
                        slider_label +\
                        ': ' +\
                        str(frame_list[slider_arg-val]) +\
                        ')'
                    fig = fig+get_scatter3d_data(
                        frame_temp,
                        **fig_kwargs
                    )

                else:
                    break

        if fig_kwargs['x_ref'] is not None and fig_kwargs['y_ref'] is not None:
            fig_ref = [
                get_ref_scatter3d_data(
                    data_frame=filterd_frame,
                    x_key=fig_kwargs['x_ref'],
                    y_key=fig_kwargs['y_ref'],
                    z_key=None,
                    name=fig_kwargs.get('ref_name', None))
            ]
        else:
            fig_ref = []

        layout = get_scatter3d_layout(**fig_kwargs)

        fig = dict(
            data=fig_ref+fig,
            layout=layout
        )

    # if (trigger_id == 'left-hide-trigger') or \
    #     (trigger_id == 'colormap-3d') or \
    #     (trigger_id == 'outline-switch') or \
    #         (trigger_id == 'decay-slider'):
    #     filter_trig = dash.no_update
    # elif trigger_id == 'scatter3d':
    #     if click_hide and \
    #             click_data['points'][0]['curveNumber'] > 0:
    #         filter_trig = trigger_idx+1
    #     else:
    #         filter_trig = dash.no_update
    # else:
    #     filter_trig = trigger_idx+1

    return dict(
        scatter3d=fig,
    )


@app.callback(
    output=dict(
        filter_trigger=Output('filter-trigger', 'data')
    ),
    inputs=dict(
        cat_values=Input({'type': 'filter-dropdown', 'index': ALL}, 'value'),
        num_values=Input({'type': 'filter-slider', 'index': ALL}, 'value'),
        colormap=Input('colormap-3d', 'value'),
        visible_list=Input('visible-picker', 'value'),
        c_key=Input('c-picker-3d', 'value'),
        click_data=Input('scatter3d', 'clickData'),
        darkmode=Input('darkmode-switch', 'value')
    ),
    state=dict(
        trigger_idx=State('filter-trigger', 'data'),
        click_hide=State('click-hide-switch', 'value'),
    )
)
def invoke_filter_trigger(
    cat_values,
    num_values,
    colormap,
    visible_list,
    c_key,
    click_data,
    darkmode,
    trigger_idx,
    click_hide
):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'scatter3d':
        if click_hide and \
                click_data['points'][0]['curveNumber'] > 0:
            filter_trig = trigger_idx+1
        else:
            filter_trig = dash.no_update
    else:
        filter_trig = trigger_idx+1

    return dict(
        filter_trigger=filter_trig
    )


@app.callback(
    output=dict(
        dummy=Output('hidden-scatter3d', 'children')
    ),
    inputs=dict(
        btn=Input('export-scatter3d', 'n_clicks')
    ),
    state=dict(
        case=State('case-picker', 'value'),
        session_id=State('session-id', 'data'),
        c_key=State('c-picker-3d', 'value'),
        colormap=State('colormap-3d', 'value'),
        visible_list=State('visible-picker', 'value'),
        file=State('file-picker', 'value'),
        file_list=State('file-add', 'value'),
        decay=State('decay-slider', 'value'),
        outline_enable=State('outline-switch', 'value'),
        darkmode=State('darkmode-switch', 'value')
    )
)
def export_3d_scatter_animation(
    btn,
    case,
    session_id,
    c_key,
    colormap,
    visible_list,
    file,
    file_list,
    decay,
    outline_enable,
    darkmode
):
    """
    Export 3D scatter into an interactive animation file

    :param int btn
        number of clicks
    :param str case
        case name
    :param str session_id
        session id
    :param str c_key
        color key
    :param str colormap
        colormap name
    :param list visible_list
        visibility list
    :param json file
        selected file

    :return: dummy
    :rtype: int
    """
    if btn == 0:
        raise PreventUpdate

    if not os.path.exists('data/' + case + '/images'):
        os.makedirs('data/' + case + '/images')

    task_kwargs = dict()
    task_kwargs['c_key'] = c_key
    task_kwargs['colormap'] = colormap
    task_kwargs['decay'] = decay

    if darkmode:
        task_kwargs['template'] = 'plotly_dark'
    else:
        task_kwargs['template'] = 'plotly'

    if outline_enable:
        task_kwargs['linewidth'] = 1
    else:
        task_kwargs['linewidth'] = 0

    if file not in file_list:
        file_list.append(file)
    celery_export_video.apply_async(
        args=[session_id,
              case,
              file_list,
              visible_list],
        kwargs=task_kwargs,
        serializer='json')

    return dict(
        dummy=0
    )


@app.callback(
    output=dict(
        dummy=Output('dummy-export-data', 'data')
    ),
    inputs=dict(
        btn=Input('export-data', 'n_clicks')
    ),
    state=dict(
        session_id=State('session-id', 'data'),
        visible_list=State('visible-picker', 'value'),
        case=State('case-picker', 'value'),
        file=State('file-picker', 'value'),
        file_list=State('file-add', 'value')
    )
)
def export_data(
    btn,
    session_id,
    visible_list,
    case,
    file,
    file_list
):
    """
    Export filtered data

    :param int btn
        number of clicks
    :param str session_id
    :param list visible_list
        visibility list
    :param str case
        case name
    :param json file
        selected file

    :return: dummy
    :rtype: int
    """
    if btn == 0:
        raise PreventUpdate

    filter_kwargs = cache_get(session_id, CACHE_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    # file = json.loads(file)
    data = load_data(file, file_list, case)
    visible_table = cache_get(session_id, CACHE_KEYS['visible_table'])

    filtered_table = filter_all(
        data,
        num_keys,
        num_values,
        cat_keys,
        cat_values,
        visible_table,
        visible_list
    )
    file = json.loads(file)
    filtered_table.to_pickle('./data/' +
                             case +
                             file['path'] +
                             '/' +
                             file['name'][0:-4]+'_filtered.pkl')

    return dict(
        dummy=0
    )
