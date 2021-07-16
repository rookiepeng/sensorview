from celery import Celery
from celery.utils.log import get_task_logger
import redis
import os
import base64

from filter import filter_all
from viz.viz import get_scatter3d

import pickle

redis_instance = redis.StrictRedis.from_url(
    os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379'))

logger = get_task_logger(__name__)

celery_app = Celery("Celery_App", broker=os.environ.get(
    'REDIS_URL', 'redis://127.0.0.1:6379'))

accept_content = ['json']


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

    logger.info('ID:'+str(self.request.id))

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
    # return
