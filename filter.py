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

    for filter_idx, filter_name in enumerate(numerical_key_list):
        if filter_idx == 0:
            condition = (data_frame[filter_name] >= numerical_key_values[filter_idx][
                0]) & (data_frame[filter_name] <= numerical_key_values[filter_idx][1])
        else:
            condition = condition & (data_frame[filter_name] >= numerical_key_values[
                filter_idx][0]) & (data_frame[filter_name] <= numerical_key_values[filter_idx][1])

    for filter_idx, filter_name in enumerate(categorical_key_list):
        if categorical_key_values[filter_idx] is not None:
            for val_idx, val in enumerate(categorical_key_values[filter_idx]):
                if val_idx == 0:
                    val_condition = data_frame[filter_name] == val
                else:
                    val_condition = val_condition | (
                        data_frame[filter_name] == val)

            condition = condition & val_condition
        else:
            condition = condition & False
            break

    return data_frame.loc[condition]
