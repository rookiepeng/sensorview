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
