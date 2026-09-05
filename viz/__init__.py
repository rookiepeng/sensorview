"""SensorView Visualization Package

Turns filtered data into Plotly figures. Two layers, and the distinction is
worth keeping:

- :mod:`~viz.graph_data`     traces from a DataFrame
- :mod:`~viz.graph_layout`   the scene, axes and colourbar around them
- :mod:`~viz.viz`            the high-level plots the 2D and camera views call
- :mod:`~viz.figure_kwargs`  resolves the axis, colour and reference arguments
  the three above all take

Those four are pure: hand them data and arguments and they hand back a figure.
:mod:`~viz.frame_figure` is the exception, and deliberately so -- it is the
pipeline that gathers one frame from the session cache and the sidecar stores
before calling them, so it is the only module here that knows a session exists.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""
