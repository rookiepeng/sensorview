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
from diskcache import Cache
from dash import DiskcacheManager

EXPIRATION = 172800  # 2 days in seconds
CACHE_KEYS = {'dataset': 'DATASET',
              'frame_list': 'FRAME_LIST',
              'frame_data': 'FRAME_DATA',
              'visible_table': 'VIS_TABLE',
              'config': 'CONFIG',
              'figure_idx': 'FIGURE_IDX',
              'figure': 'FIGURE',
              'figure_ref': 'FIGURE_REF',
              'figure_layout': 'FIGURE_LAYOUT',
              'task_id': 'TASK_ID',
              'filter_kwargs': 'FILTGER_KWARGS',
              'selected_data': 'SELECTED_DATA'}
KEY_TYPES = {'CAT': 'categorical',
             'NUM': 'numerical'}

redis_ip = os.environ.get('REDIS_SERVER_SERVICE_HOST', '127.0.0.1')
redis_url = 'redis://'+redis_ip+':6379'
redis_instance = redis.StrictRedis.from_url(redis_url)

cache = Cache('./cache', eviction_policy='none')
# background_callback_manager_disk = DiskcacheManager(cache)

cache_figure = Cache('./cache/figure', eviction_policy='none')
background_callback_manager_figure = DiskcacheManager(cache_figure)


def load_config(json_file):
    """
    Load config json file

    :param str json_file
        json file path

    :return: configuration struct
    :rtype: dict
    """
    with open(json_file, 'r') as read_file:
        return json.load(read_file)


def cache_set(data, id, key_major, key_minor=None):
    """
    Set data to Redis

    :param dict/str/pandas.Dataframe data
        data to be stored in Redis
    :param str id
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name
    """
    if key_minor is None:
        key_str = key_major+id
    else:
        key_str = key_major+id+key_minor

    cache.set(key_str, data, expire=EXPIRATION)


def redis_set(data, id, key_major, key_minor=None):
    """
    Set data to Redis

    :param dict/str/pandas.Dataframe data
        data to be stored in Redis
    :param str id
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name
    """
    if key_minor is None:
        key_str = key_major+id
    else:
        key_str = key_major+id+key_minor

    redis_instance.set(
        key_str,
        pickle.dumps(data),
        ex=EXPIRATION
    )


def cache_get(id, key_major, key_minor=None):
    """
    Get data from Redis

    :param str id
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name

    :return: data in Redis
    :rtype: dict/str/pandas.Dataframe
    """
    if key_minor is None:
        key_str = key_major+id
    else:
        key_str = key_major+id+key_minor

    val = cache.get(key_str, default=None, retry=True)
    return val


def redis_get(id, key_major, key_minor=None):
    """
    Get data from Redis

    :param str id
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name

    :return: data in Redis
    :rtype: dict/str/pandas.Dataframe
    """
    if key_minor is None:
        key_str = key_major+id
    else:
        key_str = key_major+id+key_minor

    val = redis_instance.get(key_str)

    if val is not None:
        return pickle.loads(val)
    else:
        return None
