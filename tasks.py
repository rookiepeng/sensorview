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

from celery import Celery
from celery.utils.log import get_task_logger
import os
import base64
import pandas as pd
import numpy as np

from viz.viz import get_scatter3d
from utils import redis_set, redis_get, REDIS_KEYS


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
def celery_filtering_data(self,
                          session_id,
                          case,
                          file,
                          visible_picker,
                          c_key,
                          linewidth,
                          c_label,
                          slider_label,
                          colormap):

    redis_set(-1, session_id, REDIS_KEYS['figure_idx'])

    task_id = self.request.id

    redis_set(task_id, session_id, REDIS_KEYS['task_id'])

    config = redis_get(session_id, REDIS_KEYS['config'])
    keys_dict = config['keys']

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

    x_det = config.get('x_3d', num_keys[0])
    y_det = config.get('y_3d', num_keys[1])
    z_det = config.get('z_3d', num_keys[2])
    x_host = config.get('x_ref', None)
    y_host = config.get('y_ref', None)

    x_range = [
        float(np.min([num_values[num_keys.index(x_det)][0],
                      num_values[num_keys.index(x_host)][0]])),
        float(np.max([num_values[num_keys.index(x_det)][1],
                      num_values[num_keys.index(x_host)][1]]))]
    y_range = [
        float(np.min([num_values[num_keys.index(y_det)][0],
                      num_values[num_keys.index(y_host)][0]])),
        float(np.max([num_values[num_keys.index(y_det)][1],
                      num_values[num_keys.index(y_host)][1]]))]
    z_range = [float(num_values[num_keys.index(z_det)][0]), float(
        num_values[num_keys.index(z_det)][1])]

    if keys_dict[c_key].get('type', 'numerical') == 'numerical':
        c_range = [
            num_values[num_keys.index(c_key)][0],
            num_values[num_keys.index(c_key)][1]
        ]
    else:
        c_range = [0, 0]

    for slider_arg in range(0, len(frame_list)):

        img = './data/'+case+file['path']+'/imgs/' + \
            file['name'][0:-4] + '_'+str(slider_arg)+'.jpg'

        try:
            encoded_image = base64.b64encode(open(img, 'rb').read())
            source_encoded = 'data:image/jpeg;base64,{}'.format(
                encoded_image.decode())
        except FileNotFoundError:
            source_encoded = None

        data = frame_group.get_group(frame_list[slider_arg])

        x_det = config.get('x_3d', num_keys[0])
        y_det = config.get('y_3d', num_keys[1])
        z_det = config.get('z_3d', num_keys[2])
        x_host = config.get('x_ref', None)
        y_host = config.get('y_ref', None)

        filterd_frame = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_picker
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
            c_type=keys_dict[c_key].get('type', 'numerical'),
            linewidth=linewidth,
            colormap=colormap,
            image=source_encoded,
            x_range=x_range,
            y_range=y_range,
            z_range=z_range,
            c_range=c_range,
            ref_name='Host Vehicle'
        )

        if redis_get(session_id, REDIS_KEYS['task_id']) == task_id:
            redis_set(fig, session_id, REDIS_KEYS['figure'], str(slider_arg))
            redis_set(slider_arg, session_id, REDIS_KEYS['figure_idx'])
        else:
            logger.info('Task '+str(task_id)+' terminated by a new task')
            return
