"""SensorView Dash Application

Assembles the app: the layout, the browser-side callbacks, and the registration
of every server-side callback module. Importing this module gives you a fully
wired ``app`` ready to serve -- it does not serve it. Running the app is
:mod:`main`, and hosting it in a native window is :mod:`server.desktop`.

Assembly is all this module does; every piece it names is defined elsewhere:

- ``settings``            the Dash instance, caches and shared constants
- ``layouts.*``           the component tree
- ``server.clientside``   the callbacks that run in the browser
- ``server.routes``       plain HTTP endpoints, outside the callback protocol
- ``view_callbacks.*``    one module per panel, each registering its own callbacks

Usage:
    from server.dash_app import app  # a wired Dash app, for a WSGI server to host

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from settings import app
from settings import APP_TITLE

from server.clientside import get_clientside_callbacks
from server.routes import register_api_routes

from view_callbacks.file_modal_view import get_file_modal_view_callbacks
from view_callbacks.test_case_view import get_test_case_view_callbacks
from view_callbacks.control_view import get_control_view_callbacks
from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks
from view_callbacks.scatter_3d_view_background import (
    get_scatter_3d_view_background_callbacks,
)
from view_callbacks.scatter_2d_left_view import get_scatter_2d_left_view_callbacks
from view_callbacks.scatter_2d_right_view import get_scatter_2d_right_view_callbacks
from view_callbacks.heatmap_view import get_heatmap_view_callbacks
from view_callbacks.histogram_view import get_histogram_view_callbacks
from view_callbacks.parcats_view import get_parcats_view_callbacks
from view_callbacks.violin_view import get_violin_view_callbacks
from view_callbacks.camera_view import get_camera_view_callbacks
from view_callbacks.threshold_view import get_threshold_view_callbacks

from layouts.app_layout import get_app_layout

app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = APP_TITLE
app.layout = get_app_layout

get_clientside_callbacks(app)

register_api_routes(app)

get_file_modal_view_callbacks(app)
get_test_case_view_callbacks(app)
get_control_view_callbacks(app)
get_scatter_3d_view_callbacks(app)
get_scatter_3d_view_background_callbacks(app)
get_scatter_2d_left_view_callbacks(app)
get_scatter_2d_right_view_callbacks(app)
get_heatmap_view_callbacks(app)
get_histogram_view_callbacks(app)
get_parcats_view_callbacks(app)
get_violin_view_callbacks(app)
get_camera_view_callbacks(app)
get_threshold_view_callbacks(app)
