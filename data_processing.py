
import numpy as np
from threading import Thread
from queue import Queue

import pandas as pd

from viz.viz import get_figure_data, get_figure_layout, get_host_data
from viz.viz import get_2d_scatter


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

        self.categorical_key_list = []
        self.categorical_key_values = []

        self.numerical_key_list = []
        self.numerical_key_values = []

        self.frame_idx = []

        self.task_queue = task_queue
        # self.fig_queue = fig_queue

        self.filtering_ready = False
        self.frame_list_ready = False

        self.frame_ready_index = 0

        self.filtered_table = pd.DataFrame()
        self.det_table = pd.DataFrame()
        self.fig_list = []

        self.is_locked = True

        self.left_figure = {
            'data': [{'mode': 'markers', 'type': 'scatter',
                      'x': [], 'y': []}
                     ],
            'layout': {
                'uirevision': 'no_change'
            }}
        self.right_figure = {
            'data': [{'mode': 'markers', 'type': 'scatter',
                      'x': [], 'y': []}
                     ],
            'layout': {
                'uirevision': 'no_change'
            }}
        self.left_figure_ready = False
        self.right_figure_ready = False

        self.skip_filter = False

        self.work = {
            'trigger': 'none'
        }

    def load_data(self, data):
        self.is_locked = True
        self.data = data
        self.frame_idx = self.data[
            self.config['numerical']
            [self.config['slider']]['key']].unique()

        self.categorical_key_list = []
        self.categorical_key_values = []

        self.numerical_key_list = []
        self.numerical_key_values = []

        for idx, d_item in enumerate(self.config['categorical']):
            self.categorical_key_list.append(
                self.config['categorical'][d_item]['key'])

            var_list = self.data[self.config['categorical']
                                 [d_item]['key']].unique()
            self.categorical_key_values.append(var_list)

        for idx, s_item in enumerate(self.config['numerical']):
            self.numerical_key_list.append(
                self.config['numerical'][s_item]['key'])
            var_min = round(
                np.min(self.data[self.config['numerical'][s_item]['key']]), 1)
            var_max = round(
                np.max(self.data[self.config['numerical'][s_item]['key']]), 1)

            self.numerical_key_values.append([var_min, var_max])

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
        while True:

            if not self.skip_filter:
                self.work = self.task_queue.get()  # 3s timeout

            if self.work['trigger'] == 'filter':
                new_data = self.work.get('data', None)
                if new_data is not None:
                    self.load_data(new_data)

                self.categorical_key_values = self.work.get(
                    'cat_values', self.categorical_key_values)
                self.numerical_key_values = self.work.get(
                    'num_values', self.numerical_key_values)

                self.skip_filter = False

                self.filtering_ready = False
                self.frame_list_ready = False
                self.frame_ready_index = 0

                layout_params = self.work['layout']

                self.filtered_table = self.data
                for filter_idx, filter_name in enumerate(self.numerical_key_list):
                    self.filtered_table = filter_range(
                        self.filtered_table,
                        filter_name,
                        self.numerical_key_values[filter_idx])

                    if not self.task_queue.empty():
                        self.work = self.task_queue.get_nowait()
                        if self.work['trigger'] == 'filter':
                            self.skip_filter = True
                            self.task_queue.task_done()
                            break

                for filter_idx, filter_name in enumerate(self.categorical_key_list):
                    self.filtered_table = filter_picker(
                        self.filtered_table,
                        filter_name,
                        self.categorical_key_values[filter_idx])

                    if not self.task_queue.empty():
                        self.work = self.task_queue.get_nowait()
                        if self.work['trigger'] == 'filter':
                            self.skip_filter = True
                            self.task_queue.task_done()
                            break

                if not self.skip_filter:
                    self.filtering_ready = True

                    # self.fig_queue.put_nowait(
                    #     {
                    #         'trigger': 'filter_done',
                    #         'data': self.filtered_table
                    #     }
                    # )

                    self.fig_list = []
                    frame_idx = self.data['Frame'].unique()
                    for idx, frame_idx in enumerate(frame_idx):
                        filtered_list = self.filtered_table[
                            self.filtered_table['Frame'] == frame_idx
                        ]
                        filtered_list = filtered_list.reset_index()

                        self.fig_list.append(
                            dict(
                                data=[
                                    get_figure_data(
                                        det_list=filtered_list,
                                        x_key=self.config['numerical'][
                                            self.config['graph_3d_detections']['default_x']
                                        ]['key'],
                                        y_key=self.config['numerical'][
                                            self.config['graph_3d_detections']['default_y']
                                        ]['key'],
                                        z_key=self.config['numerical'][
                                            self.config['graph_3d_detections']['default_z']
                                        ]['key'],
                                        color_key=layout_params['color_key'],
                                        color_label=layout_params['color_label'],
                                        name='Index: ' +
                                        str(idx) + ' (' +
                                        self.config['numerical'][self.config['slider']
                                                                 ]['description']+')',
                                        hover_dict={
                                            **self.config['numerical'],
                                            **self.config['categorical']
                                        },
                                        c_range=layout_params['c_range'],
                                        db=layout_params['db']
                                    ),
                                    get_host_data(
                                        det_list=filtered_list,
                                        x_key=self.config['host'][
                                            self.config['graph_3d_host']['default_x']
                                        ]['key'],
                                        y_key=self.config['host'][
                                            self.config['graph_3d_host']['default_y']
                                        ]['key']
                                    )
                                ],
                                layout=get_figure_layout(
                                    x_range=layout_params['x_range'],
                                    y_range=layout_params['y_range'],
                                    z_range=layout_params['z_range'])
                            )
                        )

                        self.frame_ready_index = idx

                        if not self.task_queue.empty():
                            self.work = self.task_queue.get_nowait()
                            if self.work['trigger'] == 'filter':
                                self.skip_filter = True
                                self.frame_ready_index = 0
                                self.task_queue.task_done()
                                break

                    if not self.skip_filter:
                        self.frame_list_ready = True
                        self.task_queue.task_done()


# class FigureProcessing(Thread):
#     def __init__(self, task_queue):
#         Thread.__init__(self)

#         self.task_queue = task_queue

#         self.left_figure = {
#             'data': [{'mode': 'markers', 'type': 'scattergl',
#                       'x': [], 'y': []}
#                      ],
#             'layout': {
#                 'uirevision': 'no_change'
#             }}
#         self.left_figure_keys = []
#         self.right_figure = {
#             'data': [{'mode': 'markers', 'type': 'scattergl',
#                       'x': [], 'y': []}
#                      ],
#             'layout': {
#                 'uirevision': 'no_change'
#             }}
#         self.right_figure_keys = []
#         self.left_figure_ready = False
#         self.right_figure_ready = False

#         self.new_left_figure = False
#         self.new_right_figure = False

#         self.work = {
#             'trigger': 'none'
#         }

#     def set_left_figure_keys(self, keys):
#         self.left_figure_keys = keys

#     def set_right_figure_keys(self, keys):
#         self.right_figure_keys = keys

#     def set_left_outdated(self):
#         self.left_figure_ready = False

#     def set_right_outdated(self):
#         self.right_figure_ready = False

#     def is_left_figure_ready(self):
#         return self.left_figure_ready

#     def is_new_left_figure(self):
#         return self.new_left_figure

#     def is_new_right_figure(self):
#         return self.new_right_figure

#     def get_left_figure(self):
#         self.new_left_figure = False
#         return self.left_figure

#     def is_right_figure_ready(self):
#         return self.right_figure_ready

#     def get_right_figure(self):
#         self.new_right_figure = False
#         return self.right_figure

#     def run(self):
#         while True:
#             self.work = self.task_queue.get()

#             if self.work['trigger'] == 'left_figure':
#                 self.left_figure_ready = False

#                 self.left_figure = get_2d_scatter(
#                     self.work['data'],
#                     self.left_figure_keys[0],
#                     self.left_figure_keys[1],
#                     self.left_figure_keys[2],
#                     self.left_figure_keys[3],
#                     self.left_figure_keys[4],
#                     self.left_figure_keys[5]
#                 )
#                 self.left_figure_ready = True
#                 self.new_left_figure = True

#                 self.task_queue.task_done()

#             elif self.work['trigger'] == 'right_figure':
#                 self.right_figure_ready = False

#                 self.right_figure = get_2d_scatter(
#                     self.work['data'],
#                     self.right_figure_keys[0],
#                     self.right_figure_keys[1],
#                     self.right_figure_keys[2],
#                     self.right_figure_keys[3],
#                     self.right_figure_keys[4],
#                     self.right_figure_keys[5]
#                 )
#                 self.right_figure_ready = True
#                 self.new_right_figure = True

#                 self.task_queue.task_done()
#             elif self.work['trigger'] == 'filter_done':
#                 print('filter done trigger')
#                 self.right_figure_ready = False
#                 self.left_figure_ready = False

#                 self.left_figure = get_2d_scatter(
#                     self.work['data'],
#                     self.left_figure_keys[0],
#                     self.left_figure_keys[1],
#                     self.left_figure_keys[2],
#                     self.left_figure_keys[3],
#                     self.left_figure_keys[4],
#                     self.left_figure_keys[5]
#                 )
#                 self.left_figure_ready = True
#                 self.new_left_figure = True

#                 self.right_figure = get_2d_scatter(
#                     self.work['data'],
#                     self.right_figure_keys[0],
#                     self.right_figure_keys[1],
#                     self.right_figure_keys[2],
#                     self.right_figure_keys[3],
#                     self.right_figure_keys[4],
#                     self.right_figure_keys[5]
#                 )
#                 self.right_figure_ready = True
#                 self.new_right_figure = True

#                 self.task_queue.task_done()
