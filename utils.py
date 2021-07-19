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
import pickle

from tasks import redis_instance, EXPIRATION


def load_config(json_file):
    with open(json_file, 'r') as read_file:
        return json.load(read_file)


def redis_set(data, session_id, key_major, key_minor=None):
    if key_minor is None:
        key_str = key_major+session_id
    else:
        key_str = key_major+session_id+key_minor
    redis_instance.set(
        key_str,
        pickle.dumps(data),
        ex=EXPIRATION
    )


def redis_get(session_id, key_major, key_minor=None):
    if key_minor is None:
        key_str = key_major+session_id
    else:
        key_str = key_major+session_id+key_minor
    return pickle.loads(redis_instance.get(key_str))
