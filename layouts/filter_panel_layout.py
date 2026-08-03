"""Filter Rail Layout Module

The left rail: display options and the dynamic per-column filters. Previously
this lived inside the 3D card and took a quarter of the plot's width; as a rail
it can be collapsed to a 44px strip, handing that space straight to the canvas.

The rail collapses clientside (``assets/workbench.js``) -- it changes nothing
the server knows about, so a callback round trip would only add latency.

Usage:
    from layouts.filter_panel_layout import get_filter_rail_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from app_config import THEME


def _switch(component_id, label, tooltip):
    """
    Build one display toggle with its tooltip.

    Args:
        component_id (str): Component id, also the tooltip target.
        label (str): Visible label.
        tooltip (str): Explanatory text.

    Returns:
        list: The switch and its tooltip.
    """
    return [
        dbc.Checklist(
            options=[{"label": label, "value": True}],
            value=[],
            id=component_id,
            switch=True,
            className="mb-2",
        ),
        dbc.Tooltip(tooltip, target=component_id, placement="right"),
    ]


def _display_section():
    """
    Build the display options block.

    Returns:
        html.Div: Overlay, click-to-hide, size-vary switches and the decay slider.
    """
    return html.Div(
        [
            html.Span("Display", className="sv-section-label"),
            *_switch(
                "overlay-switch",
                "Overlay all frames",
                "Draw every frame at once instead of just the current one",
            ),
            *_switch(
                "click-hide-switch",
                "Click to toggle visibility",
                "When enabled, clicking a point on the plot flips its "
                "hidden/visible state",
            ),
            *_switch(
                "size-vary-switch",
                "Size varies with category",
                "Scale marker size by the selected categorical column",
            ),
            html.Div(
                [
                    html.Span("Decay", className="sv-section-label"),
                    dcc.Slider(
                        id="decay-slider",
                        min=0,
                        max=10,
                        step=1,
                        value=0,
                        marks=None,
                        tooltip={"always_visible": False, "placement": "top"},
                        className="px-0 py-0",
                    ),
                ],
                className="mt-3",
            ),
            dbc.Tooltip(
                "Fade in this many previous frames behind the current one",
                target="decay-slider",
                placement="right",
            ),
        ]
    )


def _filter_section():
    """
    Build the data filter block.

    The dropdown and slider containers are populated per column when a log
    loads, so their contents depend entirely on the dataset.

    Returns:
        html.Div: Visibility picker plus the dynamic filter containers.
    """
    return html.Div(
        [
            html.Span("Data filters", className="sv-section-label"),
            html.Div(
                [
                    html.Span("Visibility", className="sv-section-label"),
                    html.Div(
                        dcc.Dropdown(
                            id="visible-picker",
                            options=["visible", "hidden"],
                            value=["visible"],
                            multi=True,
                        ),
                        className=THEME,
                    ),
                ],
                className="sv-field",
                id="visible-picker-container",
            ),
            dbc.Tooltip(
                "All data starts out labelled 'visible'. Use click-to-toggle or "
                "the 2D selection tools to relabel points as 'hidden', then "
                "filter on that label here.",
                target="visible-picker-container",
                placement="right",
            ),
            html.Div(id="dropdown-container", children=[]),
            html.Div(id="slider-container", children=[]),
        ]
    )


def get_filter_rail_layout():
    """
    Build the collapsible left filter rail.

    Returns:
        html.Aside: The rail.
    """
    return html.Aside(
        [
            html.Div(
                [
                    html.Span(
                        [html.I(className="bi bi-funnel"), "Filters"],
                        className="sv-panel-title",
                    ),
                    dbc.Button(
                        html.I(className="bi bi-layout-sidebar-inset"),
                        id="toggle-sidebar-button",
                        color="transparent",
                        n_clicks=0,
                        className="sv-icon-btn",
                    ),
                ],
                className="sv-panel-head",
            ),
            dbc.Tooltip(
                "Collapse / expand the filter rail",
                target="toggle-sidebar-button",
                placement="right",
            ),
            html.Div(
                [
                    _display_section(),
                    html.Div(className="sv-divider"),
                    _filter_section(),
                ],
                className="sv-rail-body",
            ),
        ],
        id="filter-sidebar-col",
        className="sv-rail",
    )
