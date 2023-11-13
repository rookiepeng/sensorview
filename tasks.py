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
import json

from celery import Celery
from celery.utils.log import get_task_logger

from viz.graph_data import get_scatter3d_data, get_ref_scatter3d_data
from viz.graph_data import get_hover_strings
from viz.graph_layout import get_scatter3d_layout
from utils import cache_set, cache_get, CACHE_KEYS
from utils import load_data_list
from utils import load_image
from utils import prepare_figure_kwargs

logger = get_task_logger(__name__)

redis_ip = os.environ.get("REDIS_SERVER_SERVICE_HOST", "127.0.0.1")
redis_url = "redis://" + redis_ip + ":6379"
celery_app = Celery("Celery_App", broker=redis_url, backend=redis_url)

celery_app.conf.broker_connection_retry_on_startup = False


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
        if f_name not in data.columns:
            continue

        if f_idx == 0:
            condition = (data[f_name] >= num_values[f_idx][0]) & (
                data[f_name] <= num_values[f_idx][1]
            )
        else:
            condition = (
                condition
                & (data[f_name] >= num_values[f_idx][0])
                & (data[f_name] <= num_values[f_idx][1])
            )

    for f_idx, f_name in enumerate(cat_list):
        if f_name not in data.columns:
            continue

        if not cat_values[f_idx]:
            condition = condition & False
            break
        else:
            for val_idx, val in enumerate(cat_values[f_idx]):
                if val_idx == 0:
                    val_condition = data[f_name] == val
                else:
                    val_condition = val_condition | (data[f_name] == val)

            condition = condition & val_condition

    if len(visible_list) == 1:
        condition = condition & (visible_table["_VIS_"] == visible_list[0])
    elif not visible_list:
        condition = condition & False

    return data.loc[condition]


@celery_app.task(bind=True)
def celery_filtering_data(self, session_id, case, file_list, visible_picker, **kwargs):
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
        'c_key' color key
        'colormap' colormap name
    """
    # file_list=[]

    # set figure index to -1 (no buffer is ready)
    cache_set(-1, session_id, CACHE_KEYS["figure_idx"])

    # set new task_id in Redis, this will terminate the previously running task
    task_id = self.request.id
    cache_set(task_id, session_id, CACHE_KEYS["task_id"])

    config = cache_get(session_id, CACHE_KEYS["config"])
    keys_dict = config["keys"]

    slider_label = keys_dict[config["slider"]]["description"]

    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs["cat_keys"]
    num_keys = filter_kwargs["num_keys"]
    num_values = filter_kwargs["num_values"]
    cat_values = filter_kwargs["cat_values"]

    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
    frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

    dataset = load_data_list(file_list, case)
    frame_group = dataset.groupby(config["slider"])

    if cache_get(session_id, CACHE_KEYS["task_id"]) != task_id:
        logger.info("Task " + str(task_id) + " terminated by a new task")
        return

    # prepare figure key word arguments
    fig_kwargs = prepare_figure_kwargs(
        config,
        frame_list,
        kwargs["c_key"],
        num_keys,
        num_values,
    )

    for slider_arg, frame_idx in enumerate(frame_list):
        file = json.loads(file_list[0])
        img_path = (
            "./data/"
            + case
            + file["path"]
            + "/"
            + file["name"][0:-4]
            + "/"
            + str(slider_arg)
            + ".jpg"
        )

        # encode image frame
        fig_kwargs["image"] = load_image(img_path)

        fig_kwargs["name"] = (
            "Index: "
            + str(slider_arg)
            + " ("
            + slider_label
            + ": "
            + str(frame_idx)
            + ")"
        )

        data = frame_group.get_group(frame_idx)
        filterd_frame = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_picker,
        )

        fig = get_scatter3d_data(filterd_frame, **fig_kwargs)

        hover_strings = get_hover_strings(
            filterd_frame, fig_kwargs["c_key"], fig_kwargs["c_type"], keys_dict
        )
        if fig_kwargs["x_ref"] is not None and fig_kwargs["y_ref"] is not None:
            ref_fig = [
                get_ref_scatter3d_data(
                    data_frame=filterd_frame,
                    x_key=fig_kwargs["x_ref"],
                    y_key=fig_kwargs["y_ref"],
                    z_key=None,
                    name=fig_kwargs.get("ref_name", None),
                )
            ]
        else:
            ref_fig = []

        fig_layout = get_scatter3d_layout(**fig_kwargs)

        if cache_get(session_id, CACHE_KEYS["task_id"]) == task_id:
            cache_set(fig, session_id, CACHE_KEYS["figure"], str(slider_arg))
            cache_set(hover_strings, session_id, CACHE_KEYS["hover"], str(slider_arg))
            cache_set(ref_fig, session_id, CACHE_KEYS["figure_ref"], str(slider_arg))
            cache_set(
                fig_layout, session_id, CACHE_KEYS["figure_layout"], str(slider_arg)
            )
            cache_set(slider_arg, session_id, CACHE_KEYS["figure_idx"])
        else:
            logger.info("Task " + str(task_id) + " terminated by a new task")
            return
