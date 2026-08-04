"""Analysis Dock Layout Module

The bottom dock: two side-by-side slots, each showing any one of the six
statistical views, over a drag-resizable panel that collapses to its own header.

They used to be six stacked cards, each behind an "Enable" switch, on a page you
had to scroll past the 3D view to reach. The switches were never really a
preference -- they exist because these figures are expensive and there is no
point computing one nobody is looking at. So slot assignment *is* the switch: a
view placed in a slot is live, everything else is idle, and a collapsed dock
computes nothing at all. The switches survive as hidden state (see the
clientside gate in ``app.py``) because every view callback already reads them.

All six panes are always in the tree -- component ids have to be unique, so a
pane cannot be moved between slots. Instead the gate assigns each pane a slot
class, and the stylesheet's flex ``order`` puts the two chosen ones left and
right in the order the user picked them.

Usage:
    from layouts.analysis_dock_layout import get_analysis_dock_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from layouts.left2d_card_layout import get_left2d_pane_layout
from layouts.right2d_card_layout import get_right2d_pane_layout
from layouts.hist_card_layout import get_hist_pane_layout
from layouts.violin_card_layout import get_violin_pane_layout
from layouts.parallel_card_layout import get_parallel_pane_layout
from layouts.heatmap_card_layout import get_heatmap_pane_layout


# View key -> the enable switch it drives -> the label offered in the slot
# pickers. app.py's clientside gate reads the same list, and the keys are what
# the slot selects hold.
DOCK_VIEWS = [
    ("left", "left-switch", "2D Scatter A"),
    ("right", "right-switch", "2D Scatter B"),
    ("hist", "histogram-switch", "Histogram"),
    ("violin", "violin-switch", "Violin"),
    ("parallel", "parallel-switch", "Parallel Categories"),
    ("heat", "heat-switch", "Heatmap"),
]

# An empty slot hands its width to the other one, which is how a single view
# gets the whole dock.
EMPTY_SLOT = "none"

SLOT_OPTIONS = [{"label": "— empty —", "value": EMPTY_SLOT}] + [
    {"label": label, "value": key} for key, _, label in DOCK_VIEWS
]

DEFAULT_SLOTS = {"a": "left", "b": "hist"}


def _hidden_switches():
    """
    Build the six enable switches, which slot assignment drives.

    They stay in the tree rather than being removed because every analysis
    callback reads them; hiding them just means the dock owns the decision
    instead of the user flipping six toggles.

    Returns:
        html.Div: The switches, not rendered.
    """
    return html.Div(
        [
            dbc.Checklist(
                options=[{"label": "", "value": True}],
                value=[],
                id=switch_id,
                switch=True,
            )
            for _, switch_id, _ in DOCK_VIEWS
        ],
        style={"display": "none"},
    )


def _slot_picker(slot: str, label: str, value: str):
    """
    Build the header control for one slot.

    Each picker is half the dock's width so it sits directly over the pane it
    governs, which is what makes the header read as two slot titles rather than
    as a toolbar.

    Args:
        slot: ``"a"`` or ``"b"``.
        label: Caption shown in the input group.
        value: View key initially shown in this slot.

    Returns:
        html.Div: The picker.
    """
    picker_id = f"dock-slot-{slot}"
    return html.Div(
        [
            dbc.InputGroup(
                [
                    dbc.InputGroupText(label),
                    dbc.Select(id=picker_id, options=SLOT_OPTIONS, value=value),
                ],
                size="sm",
            ),
            dbc.Tooltip(
                "Choose the plot shown in this half of the dock. Picking a view "
                "already in the other half swaps the two.",
                target=picker_id,
                placement="top",
            ),
        ],
        className="sv-slot-picker",
    )


def get_analysis_dock_layout():
    """
    Build the bottom analysis dock.

    Returns:
        html.Div: The dock, preceded by its drag handle.
    """
    panes = {
        "left": get_left2d_pane_layout(),
        "right": get_right2d_pane_layout(),
        "hist": get_hist_pane_layout(),
        "violin": get_violin_pane_layout(),
        "parallel": get_parallel_pane_layout(),
        "heat": get_heatmap_pane_layout(),
    }

    return html.Div(
        [
            html.Div(id="dock-splitter", className="sv-splitter sv-splitter-row"),
            html.Section(
                [
                    _hidden_switches(),
                    # Open state reaches the gate through a store because the
                    # collapse itself is clientside.
                    dcc.Store(id="dock-state", data={"open": False}),
                    # Last accepted slot pair, so the swap guard knows which of
                    # the two selects the user just changed.
                    dcc.Store(id="dock-slots", data=dict(DEFAULT_SLOTS)),
                    html.Div(
                        [
                            _slot_picker("a", "Left", DEFAULT_SLOTS["a"]),
                            _slot_picker("b", "Right", DEFAULT_SLOTS["b"]),
                            html.Div(
                                [
                                    dbc.Button(
                                        html.I(className="bi bi-arrow-left-right"),
                                        id="dock-swap",
                                        color="transparent",
                                        n_clicks=0,
                                        className="sv-icon-btn",
                                    ),
                                    dbc.Tooltip(
                                        "Swap the two slots",
                                        target="dock-swap",
                                        placement="top",
                                    ),
                                    dbc.Button(
                                        html.I(className="bi bi-chevron-bar-up"),
                                        id="dock-toggle",
                                        color="transparent",
                                        n_clicks=0,
                                        className="sv-icon-btn",
                                    ),
                                    dbc.Tooltip(
                                        "Show / hide the analysis dock",
                                        target="dock-toggle",
                                        placement="top",
                                    ),
                                ],
                                className="sv-dock-actions",
                            ),
                        ],
                        className="sv-dock-head",
                    ),
                    html.Div(
                        [
                            html.Div(
                                panes[key],
                                id=f"dock-pane-{key}",
                                className="sv-dock-pane",
                            )
                            for key, _, _ in DOCK_VIEWS
                        ],
                        className="sv-dock-grid",
                    ),
                ],
                id="analysis-dock",
                className="sv-dock sv-collapsed",
            ),
        ],
        className="sv-dock-wrap",
    )
