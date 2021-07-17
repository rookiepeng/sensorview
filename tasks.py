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
import redis
import os
import base64
import pickle
import pandas as pd

from viz.viz import get_scatter3d


EXPIRATION = 172800  # a week in seconds

redis_instance = redis.StrictRedis.from_url(
    os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379'))

logger = get_task_logger(__name__)

celery_app = Celery("Celery_App", broker=os.environ.get(
    'REDIS_URL', 'redis://127.0.0.1:6379'))


def filter_all(
        data,
        num_list,
        num_values,
        cat_list,
        cat_values,
        vis_table=None,
        vis_list=None,
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

    if len(vis_list) == 1:
        condition = condition & (vis_table['_VIS_'] == vis_list[0])
    elif not vis_list:
        condition = condition & False

    return data.loc[condition]


@celery_app.task(bind=True)
def celery_filtering_data(self,
                          session_id,
                          test_case,
                          data_name,
                          num_keys,
                          numerical_key_values,
                          cat_keys,
                          categorical_key_values,
                          vis_picker,
                          keys_dict,
                          c_key,
                          ui_config,
                          linewidth,
                          c_label,
                          slider_label,
                          colormap,
                          is_discrete_color,
                          x_range,
                          y_range,
                          z_range,
                          c_range):

    task_id = self.request.id

    redis_instance.set(
        'TASKID'+session_id,
        pickle.dumps(self.request.id),
        ex=EXPIRATION
    )

    vis_table = pickle.loads(redis_instance.get("VIS"+session_id))
    frame_idx = pickle.loads(redis_instance.get("FRAME_IDX"+session_id))

    for slider_arg in range(0, len(frame_idx)):

        img = './data/'+test_case+data_name['path']+'/imgs/' + \
            data_name['name'][0:-4] + '_'+str(slider_arg)+'.jpg'

        try:
            encoded_image = base64.b64encode(open(img, 'rb').read())
            source_encoded = 'data:image/jpeg;base64,{}'.format(
                encoded_image.decode())
        except FileNotFoundError:
            source_encoded = None

        data = pickle.loads(redis_instance.get(
            "FRAME"+session_id+str(frame_idx[slider_arg])))

        x_det = ui_config.get('x_3d', num_keys[0])
        y_det = ui_config.get('y_3d', num_keys[1])
        z_det = ui_config.get('z_3d', num_keys[2])
        x_host = ui_config.get('x_ref', None)
        y_host = ui_config.get('y_ref', None)

        filterd_frame = filter_all(
            data,
            num_keys,
            numerical_key_values,
            cat_keys,
            categorical_key_values,
            vis_table,
            vis_picker
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
            slider_label+': '+str(frame_idx[slider_arg])+')',
            c_label=c_label,
            linewidth=linewidth,
            colormap=colormap,
            is_discrete_color=is_discrete_color,
            image=source_encoded,
            x_range=x_range,
            y_range=y_range,
            z_range=z_range,
            c_range=c_range,
            ref_name='Host Vehicle'
        )

        if pickle.loads(redis_instance.get('TASKID'+session_id)) == task_id:
            redis_instance.set(
                'FIG'+session_id+str(slider_arg),
                pickle.dumps(fig),
                ex=EXPIRATION
            )
            redis_instance.set(
                'FIGIDX'+session_id,
                pickle.dumps(slider_arg),
                ex=EXPIRATION
            )
        else:
            logger.info('Task '+str(task_id)+' terminated by a new task.')
            return
