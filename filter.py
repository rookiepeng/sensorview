"""

    Copyright (C) 2019 - 2020  Zhengyu Peng
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

import pandas as pd


def filter_range(data_frame, name, value):
    temp_frame = data_frame[data_frame[name] >= value[0]]
    return temp_frame[
        temp_frame[name] <= value[1]
    ]


def filter_picker(data_frame, name, value):
    return data_frame[pd.DataFrame(
        data_frame[name].tolist()
    ).isin(value).any(1)]


def filter_all(
        data_frame,
        numerical_key_list,
        numerical_key_values,
        categorical_key_list,
        categorical_key_values
):
    # filtered_table = data_frame
    # for filter_idx, filter_name in enumerate(numerical_key_list):
    #     filtered_table = filter_range(
    #         filtered_table,
    #         filter_name,
    #         numerical_key_values[filter_idx])

    for filter_idx, filter_name in enumerate(numerical_key_list):
        if filter_idx == 0:
            condition = data_frame[filter_name] >= numerical_key_values[filter_idx][
                0] & data_frame[filter_name] <= numerical_key_values[filter_idx][1]
        else:
            condition = condition & data_frame[filter_name] >= numerical_key_values[
                filter_idx][0] & data_frame[filter_name] <= numerical_key_values[filter_idx][1]

    # for filter_idx, filter_name in enumerate(categorical_key_list):
    #     filtered_table = filter_picker(
    #         filtered_table,
    #         filter_name,
    #         categorical_key_values[filter_idx])

    # return filtered_table
    return data_frame.loc[condition]
