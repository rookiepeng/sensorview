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

import redis
import os
import json
import pickle

EXPIRATION = 172800  # 2 days in seconds
REDIS_KEYS = {"dataset": "DATASET",
              "frame_list": "FRAME_LIST",
              "frame_data": "FRAME_DATA",
              "vis_table": "VIS_TABLE",
              "config": "CONFIG",
              "figure_idx": "FIGURE_IDX",
              "figure": "FIGURE",
              "task_id": "TASK_ID"}

redis_instance = redis.StrictRedis.from_url(
    os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379'))


def load_config(json_file):
    with open(json_file, 'r') as read_file:
        return json.load(read_file)


def redis_set(data, id, key_major, key_minor=None):
    if key_minor is None:
        key_str = key_major+id
    else:
        key_str = key_major+id+key_minor
    redis_instance.set(
        key_str,
        pickle.dumps(data),
        ex=EXPIRATION
    )


def redis_get(id, key_major, key_minor=None):
    if key_minor is None:
        key_str = key_major+id
    else:
        key_str = key_major+id+key_minor

    val = redis_instance.get(key_str)
    if val is not None:
        return pickle.loads(val)
    else:
        return None
