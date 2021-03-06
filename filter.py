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

import pandas as pd


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
