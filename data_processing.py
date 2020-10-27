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

import numpy as np
from threading import Thread
from queue import Queue

import pandas as pd

from viz.viz import get_figure_data, get_figure_layout, get_host_data


def filter_range(data_frame, name, value):
    temp_frame = data_frame[data_frame[name] >= value[0]]
    return temp_frame[
        temp_frame[name] <= value[1]
    ].reset_index(drop=True)


def filter_picker(data_frame, name, value):
    return data_frame[pd.DataFrame(
        data_frame[name].tolist()
    ).isin(value).any(1)].reset_index(drop=True)


def filter_all(
        data_frame,
        numerical_key_list,
        numerical_key_values,
        categorical_key_list,
        categorical_key_values
):
    filtered_table = data_frame
    for filter_idx, filter_name in enumerate(numerical_key_list):
        filtered_table = filter_range(
            filtered_table,
            filter_name,
            numerical_key_values[filter_idx])

    for filter_idx, filter_name in enumerate(categorical_key_list):
        filtered_table = filter_picker(
            filtered_table,
            filter_name,
            categorical_key_values[filter_idx])

    return filtered_table


class DataProcessing(Thread):
    def __init__(self, config, task_queue):
        Thread.__init__(self)

        self.config = config

        self.data = pd.DataFrame()

        self.frame_idx = []

        self.task_queue = task_queue

        self.filtering_ready = False
        self.frame_list_ready = False

        self.frame_ready_index = 0

        self.filtered_table = pd.DataFrame()

        self.fig_list = []

        self.is_locked = True

    def load_data(self, data):
        self.is_locked = True
        self.data = data
        self.frame_idx = self.data[
            self.config['numerical']
            [self.config['slider']]['key']].unique()

        self.is_locked = False

    def is_filtering_ready(self):
        return self.filtering_ready

    def is_frame_list_ready(self):
        return self.frame_list_ready

    def get_frame_ready_index(self):
        return self.frame_ready_index

    def get_frame(self, idx):
        return self.fig_list[idx]

    def get_filtered_data(self):
        return self.filtered_table

    def run(self):
        skip_filter = False
        while True:
            work = self.task_queue.get()

            if work['trigger'] == 'filter':
                new_data = work.get('data', None)
                if new_data is not None:
                    self.load_data(new_data)

                cat_values = work['cat_values']
                num_values = work['num_values']
                cat_keys = work['cat_keys']
                num_keys = work['num_keys']

                skip_filter = False

                self.filtering_ready = False
                self.frame_list_ready = False
                self.frame_ready_index = 0

                graph_params = work['graph_params']

                self.filtered_table = self.data
                for filter_idx, filter_name in enumerate(num_keys):
                    self.filtered_table = filter_range(
                        self.filtered_table,
                        filter_name,
                        num_values[filter_idx])

                    if not self.task_queue.empty():
                        skip_filter = True
                        break

                for filter_idx, filter_name in enumerate(cat_keys):
                    self.filtered_table = filter_picker(
                        self.filtered_table,
                        filter_name,
                        cat_values[filter_idx])

                    if not self.task_queue.empty():
                        skip_filter = True
                        break

                if not skip_filter:
                    self.filtering_ready = True

                    self.fig_list = []
                    for idx, frame in enumerate(self.frame_idx):
                        filtered_list = self.filtered_table[
                            self.filtered_table['Frame'] == frame
                        ]
                        filtered_list = filtered_list.reset_index()

                        self.fig_list.append(dict(
                            data=[
                                get_figure_data(
                                    det_list=filtered_list,
                                    x_key=graph_params['x_det_key'],
                                    y_key=graph_params['y_det_key'],
                                    z_key=graph_params['z_det_key'],
                                    color_key=graph_params['color_key'],
                                    color_label=graph_params['color_label'],
                                    name='Index: ' +
                                    str(idx) + ' (' +
                                    self.config['numerical'][
                                        self.config['slider']
                                    ]['description']+')',
                                    hover_dict={
                                        **self.config['numerical'],
                                        **self.config['categorical']
                                    },
                                    c_range=graph_params['c_range'],
                                    db=graph_params['db']
                                ),
                                get_host_data(
                                    det_list=filtered_list,
                                    x_key=graph_params['x_host_key'],
                                    y_key=graph_params['y_host_key'],
                                )
                            ],
                            layout=get_figure_layout(
                                x_range=graph_params['x_range'],
                                y_range=graph_params['y_range'],
                                z_range=graph_params['z_range'])
                        )
                        )

                        self.frame_ready_index = idx

                        if not self.task_queue.empty():

                            skip_filter = True
                            self.frame_ready_index = 0
                            break

                    if not skip_filter:
                        self.frame_list_ready = True

                    self.task_queue.task_done()
