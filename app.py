"""SensorView Dash Application

Assembles the app: the layout, the clientside callbacks that run in the browser,
and the registration of every server-side callback module. Importing this module
gives you a fully wired ``app`` ready to serve -- it does not serve it. Running
the app is :mod:`main`, and hosting it in a native window is :mod:`desktop`.

The pieces it wires together:

- ``settings``           the Dash instance, caches and shared constants
- ``layouts.*``          the component tree
- ``routes``             plain HTTP endpoints, outside the callback protocol
- ``view_callbacks.*``   one module per panel, each registering its own callbacks

Usage:
    from app import app        # a wired Dash app, for a WSGI server to host

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import dash
from dash.dependencies import Input, Output, State

from settings import app
from settings import APP_TITLE

from routes import register_api_routes

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
from layouts.analysis_dock_layout import DOCK_VIEWS, EMPTY_SLOT

app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = APP_TITLE
app.layout = get_app_layout


# Initialize worker
app.clientside_callback(
    dash.ClientsideFunction(
        namespace="clientside_callback", function_name="initWorker"
    ),
    Output("worker-status", "data"),
    Input("refresh-button-modal", "n_clicks"),
)

# Store data in IndexedDB via worker
app.clientside_callback(
    dash.ClientsideFunction(
        namespace="clientside_callback", function_name="storeBuffer"
    ),
    [
        Output("buffer-local", "value"),
        Output("worker-status", "data", allow_duplicate=True),
        Output("local-buffer-index", "data", allow_duplicate=True),
    ],
    Input("interval-buffer", "n_intervals"),
    State("local-buffer-index", "data"),
    State("session-id", "data"),
    State("slider-frame", "max"),
    prevent_initial_call=True,
)

# Retrieve data from IndexedDB
app.clientside_callback(
    dash.ClientsideFunction(
        namespace="clientside_callback", function_name="retrieveBuffer"
    ),
    [
        Output("scatter3d", "figure", allow_duplicate=True),
        Output("trigger-remote-figure", "data"),
    ],
    Input("slider-frame", "value"),
    Input("play-stop-button", "n_clicks"),
    Input("decay-slider", "value"),
    State("size-vary-switch", "value"),
    State("session-id", "data"),
    State("interval-component", "disabled"),
    State("colormap-3d", "value"),
    State("c-picker-3d", "value"),
    State("darkmode-switch", "value"),
    State("key-dict", "data"),
    State("dark-template", "data"),
    State("light-template", "data"),
    State("local-buffer-index", "data"),
    State("trigger-remote-figure", "data"),
    # Identifies the log the backdrop belongs to, so switching logs inside one
    # session does not keep serving the previous log's cloud out of the cache.
    State("local-file-selection", "data"),
    prevent_initial_call=True,
)


# This clientside callback function disables the interval component based on
# the number of clicks on the play button and stop button. If the play button
# is clicked and the number of play clicks is greater than 0, the interval
# component is disabled. If the stop button is clicked and the number of stop
# clicks is greater than 0, the interval component is enabled. If neither button
# is clicked, the interval component remains unchanged.
app.clientside_callback(
    """
    function(n_clicks, ispaused) {
        const triggered = dash_clientside.callback_context.triggered.map(
            t => t.prop_id
            );
        if (triggered.length > 0 && triggered[0].includes('play-stop-button')) {
            if (n_clicks > 0) {
                return ispaused ? false : true;
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("interval-component", "disabled"),
    Input("play-stop-button", "n_clicks"),
    State("interval-component", "disabled"),
)

# The loading overlay is raised and lowered by the `running` state of the load
# callback itself (view_callbacks/test_case_view.py). Raising it from here too
# meant two owners for one prop, and the one that could only ever raise it won
# whenever the load bailed out before reaching its own hide.

# The picker panel is the only place the combined logs are named, and it closes
# on demand, so the button that opens it carries the fact that some are in play.
app.clientside_callback(
    """
    function(add_file) {
        var combining = Array.isArray(add_file) && add_file.length > 0;
        return "sv-icon-btn" + (combining ? " active" : "");
    }
    """,
    Output("button-add", "className"),
    Input("file-add", "value"),
)

# Slot assignment is the enable switch for a view, and the slot layout.
#
# These six figures are expensive, so only the two on screen are live: a view
# placed in a slot gets its switch turned on and a class that orders it left or
# right, everything else goes off and stays hidden, and a collapsed dock turns
# all of them off. Re-firing on `file-loaded-trigger` means a newly loaded log
# refreshes the visible charts rather than blanking them.
app.clientside_callback(
    f"""
    function(slot_a, slot_b, dock_state, unused_file_loaded) {{
        const keys = {[key for key, _, _ in DOCK_VIEWS]};
        const live = (dock_state || {{}}).open === true;
        const a = live ? slot_a : null;
        const b = live ? slot_b : null;
        // The divider between the slots only exists when both are filled.
        const paired = keys.indexOf(a) >= 0 && keys.indexOf(b) >= 0;
        const classes = keys.map(function (key) {{
            if (key === a) return "sv-dock-pane sv-slot-a";
            if (key === b) {{
                return "sv-dock-pane sv-slot-b" + (paired ? " sv-slot-paired" : "");
            }}
            return "sv-dock-pane";
        }});
        const switches = keys.map(function (key) {{
            return key === a || key === b ? [true] : [];
        }});
        return classes.concat(switches);
    }}
    """,
    [Output(f"dock-pane-{key}", "className") for key, _, _ in DOCK_VIEWS]
    + [Output(switch_id, "value") for _, switch_id, _ in DOCK_VIEWS],
    Input("dock-slot-a", "value"),
    Input("dock-slot-b", "value"),
    Input("dock-state", "data"),
    Input("file-loaded-trigger", "data"),
)

# A view can only be in one slot -- its component ids exist once. Picking a view
# the other slot already holds therefore swaps the two rather than failing: the
# store remembers the last accepted pair, which is how this knows which of the
# two selects the user just changed.
app.clientside_callback(
    f"""
    function(slot_a, slot_b, previous) {{
        const empty = "{EMPTY_SLOT}";
        const prev = previous || {{}};
        if (slot_a && slot_a === slot_b && slot_a !== empty) {{
            if (slot_a !== prev.a) {{
                slot_b = prev.a || empty;
            }} else {{
                slot_a = prev.b || empty;
            }}
        }}
        return [slot_a, slot_b, {{a: slot_a, b: slot_b}}];
    }}
    """,
    Output("dock-slot-a", "value"),
    Output("dock-slot-b", "value"),
    Output("dock-slots", "data"),
    Input("dock-slot-a", "value"),
    Input("dock-slot-b", "value"),
    State("dock-slots", "data"),
)

app.clientside_callback(
    """
    function(n_clicks, slot_a, slot_b) {
        if (!n_clicks) {
            return [window.dash_clientside.no_update,
                    window.dash_clientside.no_update];
        }
        return [slot_b, slot_a];
    }
    """,
    Output("dock-slot-a", "value", allow_duplicate=True),
    Output("dock-slot-b", "value", allow_duplicate=True),
    Input("dock-swap", "n_clicks"),
    State("dock-slot-a", "value"),
    State("dock-slot-b", "value"),
    prevent_initial_call=True,
)

# The dock's open state has to reach the server-side gate above, and the collapse
# itself is clientside, so the toggle button updates a store that both read.
app.clientside_callback(
    """
    function(n_clicks, state) {
        if (!n_clicks) {
            return window.dash_clientside.no_update;
        }
        return {open: !((state || {}).open === true)};
    }
    """,
    Output("dock-state", "data"),
    Input("dock-toggle", "n_clicks"),
    State("dock-state", "data"),
)

# Mirror the hidden path/case/file fields into the top bar breadcrumb.
app.clientside_callback(
    """
    function(case_name, log_file) {
        const empty = "sv-crumb sv-crumb-file sv-crumb-empty";
        const named = "sv-crumb sv-crumb-file";
        return [
            case_name || "No test case",
            log_file || "select a log …",
            log_file ? named : empty,
        ];
    }
    """,
    Output("crumb-case", "children"),
    Output("crumb-file", "children"),
    Output("crumb-file", "className"),
    Input("test-case", "value"),
    Input("log-file", "value"),
)

# Frame counter beside the transport slider.
app.clientside_callback(
    """
    function(value, max_value) {
        return [String(value || 0), " / " + String(max_value || 0)];
    }
    """,
    Output("frame-current", "children"),
    Output("frame-total", "children"),
    Input("slider-frame", "value"),
    Input("slider-frame", "max"),
)

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
