
import numpy as np
from threading import Thread, Event
from queue import Queue

import pandas as pd

from viz import get_2d_scatter, get_figure_data, get_figure_layout, get_host_data


class DataProcessing(Thread):
    def __init__(self, config, task_queue, fig_queue):
        Thread.__init__(self)

        self.config = config

        self.categorical_key_list = []
        self.categorical_key_values = []

        self.numerical_key_list = []
        self.numerical_key_values = []

        self.data = pd.DataFrame()
        self.frame_list = []
        self.task_queue = task_queue
        self.fig_queue = fig_queue

        self.filtering_ready = False
        self.frame_list_ready = False

        self.frame_ready_index = 0

        self.filtered_table = pd.DataFrame()
        self.det_table = pd.DataFrame()
        self.fig_list = []

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
        self.data = data
        self.frame_list = self.data[
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

    def update_numerical_key_values(self, num_values):
        self.numerical_key_values = num_values

    def update_categorical_key_values(self, cat_values):
        self.categorical_key_values = cat_values

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

    def filter_range(self, data_frame, name, value):
        temp_frame = data_frame[data_frame[name] >= value[0]]
        return temp_frame[
            temp_frame[name] <= value[1]
        ].reset_index(drop=True)

    def filter_picker(self, data_frame, name, value):
        return data_frame[pd.DataFrame(
            data_frame[name].tolist()
        ).isin(value).any(1)].reset_index(drop=True)

    def run(self):
        while True:

            if not self.skip_filter:
                self.work = self.task_queue.get()  # 3s timeout

            if self.work['trigger'] == 'filter':
                if self.work['new_data']:
                    self.load_data(self.work['data'])
                else:
                    self.categorical_key_values = self.work['cat_values']
                    self.numerical_key_values = self.work['num_values']

                self.skip_filter = False

                self.filtering_ready = False
                self.frame_list_ready = False
                self.frame_ready_index = 0

                layout_params = self.work['layout']
                # ui_config = self.work['config']

                # full_table = self.work['data']
                self.filtered_table = self.data
                for filter_idx, filter_name in enumerate(self.numerical_key_list):
                    self.filtered_table = self.filter_range(
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
                    self.filtered_table = self.filter_picker(
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

                    self.fig_queue.put_nowait(
                        {
                            'trigger': 'filter_done',
                            'data': self.filtered_table
                        }
                    )

                    self.fig_list = []
                    frame_list = self.data['Frame'].unique()
                    for idx, frame_idx in enumerate(frame_list):
                        filtered_list = self.filtered_table[
                            self.filtered_table['Frame'] == frame_idx
                        ]
                        filtered_list = filtered_list.reset_index()

                        self.fig_list.append(
                            dict(
                                data=[
                                    get_figure_data(
                                        det_list=filtered_list,
                                        x_key='Latitude',
                                        y_key='Longitude',
                                        z_key='Height',
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
                                        x_key='HostLatitude',
                                        y_key='HostLongitude',
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

                    # if filter_trigger:
                    #     skip_filter = True
                    #     break


class FigureProcessing(Thread):
    def __init__(self, task_queue):
        Thread.__init__(self)

        self.task_queue = task_queue

        self.left_figure = {
            'data': [{'mode': 'markers', 'type': 'scatter',
                      'x': [], 'y': []}
                     ],
            'layout': {
                'uirevision': 'no_change'
            }}
        self.left_figure_keys = []
        self.right_figure = {
            'data': [{'mode': 'markers', 'type': 'scatter',
                      'x': [], 'y': []}
                     ],
            'layout': {
                'uirevision': 'no_change'
            }}
        self.right_figure_keys = []
        self.left_figure_ready = False
        self.right_figure_ready = False

        # self.left_outdated = True
        # self.right_outdated = True

        self.work = {
            'trigger': 'none'
        }

    def set_left_figure_keys(self, keys):
        self.left_figure_keys = keys

    def set_right_figure_keys(self, keys):
        self.right_figure_keys = keys

    def set_left_outdated(self):
        self.left_figure_ready = False

    def set_right_outdated(self):
        self.right_figure_ready = False

    def is_left_figure_ready(self):
        return self.left_figure_ready

    def get_left_figure(self):
        return self.left_figure

    def is_right_figure_ready(self):
        return self.right_figure_ready

    def get_right_figure(self):
        return self.right_figure

    def run(self):
        while True:
            self.work = self.task_queue.get()

            if self.work['trigger'] == 'left_figure':
                self.left_figure_ready = False

                self.left_figure = get_2d_scatter(
                    self.work['data'],
                    self.left_figure_keys[0],
                    self.left_figure_keys[1],
                    self.left_figure_keys[2],
                    self.left_figure_keys[3],
                    self.left_figure_keys[4],
                    self.left_figure_keys[5]
                )
                self.left_figure_ready = True
                # self.left_outdated = False
                # self.right_outdated = False
                self.task_queue.task_done()

            elif self.work['trigger'] == 'right_figure':
                self.right_figure_ready = False

                self.right_figure = get_2d_scatter(
                    self.work['data'],
                    self.right_figure_keys[0],
                    self.right_figure_keys[1],
                    self.right_figure_keys[2],
                    self.right_figure_keys[3],
                    self.right_figure_keys[4],
                    self.right_figure_keys[5]
                )
                self.right_figure_ready = True
                # self.left_outdated = False
                # self.right_outdated = False
                self.task_queue.task_done()
            elif self.work['trigger'] == 'filter_done':
                self.right_figure_ready = False
                self.left_figure_ready = False

                self.left_figure = get_2d_scatter(
                    self.work['data'],
                    self.left_figure_keys[0],
                    self.left_figure_keys[1],
                    self.left_figure_keys[2],
                    self.left_figure_keys[3],
                    self.left_figure_keys[4],
                    self.left_figure_keys[5]
                )
                self.left_figure_ready = True

                self.right_figure = get_2d_scatter(
                    self.work['data'],
                    self.right_figure_keys[0],
                    self.right_figure_keys[1],
                    self.right_figure_keys[2],
                    self.right_figure_keys[3],
                    self.right_figure_keys[4],
                    self.right_figure_keys[5]
                )
                self.right_figure_ready = True

                # self.left_outdated = False
                # self.right_outdated = False
                self.task_queue.task_done()
