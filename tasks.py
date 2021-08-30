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

from celery import Celery
from celery.utils.log import get_task_logger
import os
import base64
import pandas as pd
import numpy as np

import plotly.graph_objs as go

from viz.graph_data import get_scatter3d_data, get_ref_scatter3d_data
from viz.graph_layout import get_scatter3d_layout
from viz.viz import get_animation_data
from utils import redis_set, redis_get, REDIS_KEYS, KEY_TYPES


logger = get_task_logger(__name__)

celery_app = Celery("Celery_App", broker=os.environ.get(
    'REDIS_URL', 'redis://127.0.0.1:6379'))


def filter_all(
        data,
        num_list,
        num_values,
        cat_list,
        cat_values,
        visible_table=None,
        visible_list=None,
):
    """
    Filter the DataFrame

    :param pandas.DataFrame data
        initial data table
    :param [str] num_list
        list of numerical keys
    :param [list] num_values
        numberical value ranges
    :param [str] cat_list
        list of categorical keys
    :param [list] cat_values
        categorical item lists
    :param pandas.DataFrame visible_table=None
        visibility table
    :param [str] visible_list=None
        visibility list

    :return: filtered data table
    :rtype: pandas.DataFrame
    """

    for f_idx, f_name in enumerate(num_list):
        if f_idx == 0:
            condition = (data[f_name] >= num_values[f_idx][0]) \
                & (data[f_name] <= num_values[f_idx][1])
        else:
            condition = condition \
                & (data[f_name] >= num_values[f_idx][0]) \
                & (data[f_name] <= num_values[f_idx][1])

    for f_idx, f_name in enumerate(cat_list):
        if not cat_values[f_idx]:
            condition = condition & False
            break
        else:
            for val_idx, val in enumerate(cat_values[f_idx]):
                if val_idx == 0:
                    val_condition = data[f_name] == val
                else:
                    val_condition = val_condition \
                        | (data[f_name] == val)

            condition = condition & val_condition

    if len(visible_list) == 1:
        condition = condition & (visible_table['_VIS_'] == visible_list[0])
    elif not visible_list:
        condition = condition & False

    return data.loc[condition]


@celery_app.task(bind=True)
def celery_filtering_data(
    self,
    session_id,
    case,
    file,
    visible_picker,
    **kwargs
):
    """
    Celery task for preparing the frame figures

    :param str session_id
        session id
    :param str case
        case name
    :param json file
        selected file
    :param list visible_picker
        visibility list ['visible', 'hidden']

    :param dict kwargs
        'linewidth' outline width
        'c_key' color key
        'colormap' colormap name
    """

    # set figure index to -1 (no buffer is ready)
    redis_set(-1, session_id, REDIS_KEYS['figure_idx'])

    # set new task_id in Redis, this will terminate the previously running task
    task_id = self.request.id
    redis_set(task_id, session_id, REDIS_KEYS['task_id'])

    config = redis_get(session_id, REDIS_KEYS['config'])
    keys_dict = config['keys']

    slider_label = keys_dict[config['slider']
                             ]['description']

    filter_kwargs = redis_get(session_id, REDIS_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    num_values = filter_kwargs['num_values']
    cat_values = filter_kwargs['cat_values']

    visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])
    frame_list = redis_get(session_id, REDIS_KEYS['frame_list'])

    dataset = pd.read_feather('./data/'+case +
                              file['path']+'/' +
                              file['feather_name'])
    frame_group = dataset.groupby(config['slider'])

    # prepare figure key word arguments
    fig_kwargs = kwargs
    fig_kwargs['image'] = None

    fig_kwargs['x_key'] = config.get('x_3d', num_keys[0])
    fig_kwargs['x_label'] = keys_dict[fig_kwargs['x_key']].get(
        'description', fig_kwargs['x_key'])
    fig_kwargs['y_key'] = config.get('y_3d', num_keys[1])
    fig_kwargs['y_label'] = keys_dict[fig_kwargs['y_key']].get(
        'description', fig_kwargs['y_key'])
    fig_kwargs['z_key'] = config.get('z_3d', num_keys[2])
    fig_kwargs['z_label'] = keys_dict[fig_kwargs['z_key']].get(
        'description', fig_kwargs['z_key'])
    # fig_kwargs['c_key'] = c_key
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

    if keys_dict[fig_kwargs['c_key']].\
            get('type', KEY_TYPES['NUM']) == KEY_TYPES['NUM']:
        fig_kwargs['c_range'] = [
            num_values[num_keys.index(fig_kwargs['c_key'])][0],
            num_values[num_keys.index(fig_kwargs['c_key'])][1]
        ]
    else:
        fig_kwargs['c_range'] = [0, 0]

    fig_kwargs['c_type'] = keys_dict[fig_kwargs['c_key']].get(
        'type', KEY_TYPES['NUM'])
    fig_kwargs['ref_name'] = 'Host Vehicle'
    fig_kwargs['hover'] = keys_dict

    for slider_arg in range(0, len(frame_list)):

        img_path = './data/' +\
            case +\
            file['path'] +\
            '/imgs/' + \
            file['name'][0:-4] + \
            '_' +\
            str(slider_arg) +\
            '.jpg'

        # encode image frame
        try:
            encoding = base64.b64encode(open(img_path, 'rb').read())
            fig_kwargs['image'] = 'data:image/jpeg;base64,{}'.format(
                encoding.decode())
        except FileNotFoundError:
            fig_kwargs['image'] = None

        fig_kwargs['name'] = 'Index: ' +\
            str(slider_arg) +\
            ' (' +\
            slider_label +\
            ': ' +\
            str(frame_list[slider_arg]) +\
            ')'

        data = frame_group.get_group(frame_list[slider_arg])
        filterd_frame = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_picker
        )

        fig = get_scatter3d_data(
            filterd_frame,
            **fig_kwargs
        )
        ref_fig = [get_ref_scatter3d_data(
            data_frame=filterd_frame,
            x_key=kwargs['x_ref'],
            y_key=kwargs['y_ref'],
            z_key=None,
            name=kwargs.get('ref_name', None)
        )]
        fig_layout = get_scatter3d_layout(**fig_kwargs)

        if redis_get(session_id, REDIS_KEYS['task_id']) == task_id:
            redis_set(fig,
                      session_id, REDIS_KEYS['figure'],
                      str(slider_arg))
            redis_set(ref_fig,
                      session_id,
                      REDIS_KEYS['figure_ref'],
                      str(slider_arg))
            redis_set(fig_layout,
                      session_id,
                      REDIS_KEYS['figure_layout'],
                      str(slider_arg))
            redis_set(slider_arg,
                      session_id,
                      REDIS_KEYS['figure_idx'])
        else:
            logger.info('Task '+str(task_id)+' terminated by a new task')
            return


@celery_app.task()
def celery_export_video(
    session_id,
    case,
    file,
    visible_picker,
    **kwargs
):
    """
    Celery task for preparing the frame figures

    :param str session_id
        session id
    :param str case
        case name
    :param json file
        selected file
    :param list visible_picker
        visibility list ['visible', 'hidden']

    :param dict kwargs
        'linewidth' outline width
        'c_key' color key
        'colormap' colormap name
    """

    config = redis_get(session_id, REDIS_KEYS['config'])
    keys_dict = config['keys']

    filter_kwargs = redis_get(session_id, REDIS_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    num_values = filter_kwargs['num_values']
    cat_values = filter_kwargs['cat_values']

    visible_table = redis_get(session_id,
                              REDIS_KEYS['visible_table'])
    frame_list = redis_get(session_id,
                           REDIS_KEYS['frame_list'])

    dataset = pd.read_feather('./data/'+case +
                              file['path']+'/' +
                              file['feather_name'])
    filtered_table = filter_all(
        dataset,
        num_keys,
        num_values,
        cat_keys,
        cat_values,
        visible_table,
        visible_picker
    )

    img_list = []

    for _, f_val in enumerate(frame_list):
        img_idx = np.where(frame_list == f_val)[0][0]
        img_list.append('./data/' +
                        case +
                        file['path'] +
                        '/imgs/' +
                        file['name'][0:-4] +
                        '_' +
                        str(img_idx) +
                        '.jpg')

    # prepare figure key word arguments
    fig_kwargs = kwargs

    fig_kwargs['hover'] = keys_dict

    fig_kwargs['x_key'] = config.get('x_3d', num_keys[0])
    fig_kwargs['x_label'] = keys_dict[fig_kwargs['x_key']].get(
        'description', fig_kwargs['x_key'])
    fig_kwargs['y_key'] = config.get('y_3d', num_keys[1])
    fig_kwargs['y_label'] = keys_dict[fig_kwargs['y_key']].get(
        'description', fig_kwargs['y_key'])
    fig_kwargs['z_key'] = config.get('z_3d', num_keys[2])
    fig_kwargs['z_label'] = keys_dict[fig_kwargs['z_key']].get(
        'description', fig_kwargs['z_key'])
    # c_key = fig_kwargs['c_key']
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

    if keys_dict[fig_kwargs['c_key']].\
            get('type', KEY_TYPES['NUM']) == KEY_TYPES['NUM']:
        fig_kwargs['c_range'] = [
            num_values[num_keys.index(fig_kwargs['c_key'])][0],
            num_values[num_keys.index(fig_kwargs['c_key'])][1]
        ]
    else:
        fig_kwargs['c_range'] = [0, 0]

    fig_kwargs['c_type'] = keys_dict[fig_kwargs['c_key']].get(
        'type', KEY_TYPES['NUM'])
    fig_kwargs['ref_name'] = 'Host Vehicle'
    fig_kwargs['hover'] = keys_dict

    fig_kwargs['title'] = file['name'][0:-4]

    fig_kwargs['height'] = 750

    fig = go.Figure(
        get_animation_data(
            filtered_table,
            img_list=img_list,
            **fig_kwargs
        )
    )

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    fig.write_html('data/' +
                   case +
                   '/images/' +
                   timestamp +
                   '_' +
                   file['name'][0:-4] +
                   '_3dview.html')
