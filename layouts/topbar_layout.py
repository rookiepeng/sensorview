"""Top Bar Layout Module

The single horizontal strip that used to be a 150px header block: identity on
the left, what is currently loaded in the middle, global actions on the right.

The breadcrumb is the data picker. Reading which log is open and changing it
are the same control, so there is no separate "select file" affordance to hunt
for, and the three read-only path fields it replaced cost nothing on screen --
they are still in the tree (callbacks read their ``value``), just not painted.

Usage:
    from layouts.topbar_layout import get_topbar_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from app_config import app
from app_config import APP_TITLE, APP_VERSION, THEME


HIDDEN_FIELD = {"display": "none"}


def _brand():
    """
    Build the product mark.

    Returns:
        html.Div: Logo, wordmark, and version.
    """
    return html.Div(
        [
            html.Img(
                src=app.get_asset_url("sensorview_logo.svg"),
                id="sensorview-image",
                alt=APP_TITLE,
            ),
            html.Span(APP_TITLE, className="sv-brand-name"),
            html.Span(APP_VERSION, className="sv-brand-version"),
        ],
        className="sv-brand",
    )


def _breadcrumb():
    """
    Build the dataset breadcrumb, which opens the data selection modal.

    The three fields the old header displayed are kept as hidden inputs: a
    number of callbacks read ``data-path``/``test-case``/``log-file`` values as
    state, and a clientside callback mirrors them into the visible crumbs.

    Returns:
        list: The breadcrumb button followed by the hidden state fields.
    """
    return [
        html.Button(
            [
                html.I(className="bi bi-folder2-open"),
                html.Span("No test case", id="crumb-case", className="sv-crumb sv-crumb-case"),
                html.Span("/", className="sv-crumb-sep"),
                html.Span(
                    "select a log …",
                    id="crumb-file",
                    className="sv-crumb sv-crumb-file sv-crumb-empty",
                ),
                html.I(className="bi bi-chevron-expand"),
            ],
            id="select-button",
            n_clicks=0,
            className="sv-breadcrumb",
        ),
        dbc.Tooltip(
            "Change data path, test case, or log file",
            target="select-button",
            placement="bottom",
        ),
        dbc.Input(id="data-path", type="text", readonly=True, style=HIDDEN_FIELD),
        dbc.Input(id="test-case", type="text", readonly=True, style=HIDDEN_FIELD),
        dbc.Input(id="log-file", type="text", readonly=True, style=HIDDEN_FIELD),
    ]


def _combine_control():
    """
    Build the "combine other logs" button and its drop-down panel.

    Returns:
        list: Trigger button, tooltip, and the collapsible picker panel.
    """
    return [
        dbc.Button(
            html.I(className="bi bi-link-45deg"),
            id="button-add",
            n_clicks=0,
            color="transparent",
            className="sv-icon-btn",
        ),
        dbc.Tooltip("Combine other log files", target="button-add", placement="bottom"),
        dbc.Collapse(
            html.Div(
                [
                    html.Span("Combine additional logs", className="sv-section-label"),
                    html.Div(dcc.Dropdown(id="file-add", multi=True), className=THEME),
                ],
                className="sv-combine-inner",
            ),
            id="collapse-add",
            is_open=False,
            className="sv-combine-panel",
        ),
    ]


def _theme_toggle():
    """
    Build the light/dark switch.

    Returns:
        html.Div: The switch; ``workbench.js`` mirrors it onto the document so
        the app chrome and the Plotly templates change together.
    """
    return html.Div(
        [
            dbc.Checklist(
                options=[
                    {"label": html.I(className="bi bi-moon-stars-fill"), "value": True}
                ],
                value=[True],
                id="darkmode-switch",
                switch=True,
                inline=True,
                className="d-flex align-items-center",
            ),
            dbc.Tooltip(
                "Toggle light / dark theme",
                id="darkmode-switch-tooltip",
                target="darkmode-switch",
                placement="bottom",
            ),
        ],
        className="d-flex align-items-center px-2",
    )


def _export_menu():
    """
    Build the export menu.

    Returns:
        dcc.Loading: The export dropdown, wrapped so long exports show progress.
    """
    return dcc.Loading(
        children=[
            dbc.DropdownMenu(
                [
                    dbc.DropdownMenuItem("Current plot (PNG)", id="export-scatter3d-png", n_clicks=0),
                    dbc.DropdownMenuItem("Current plot (HTML)", id="export-scatter3d-html", n_clicks=0),
                    dbc.DropdownMenuItem("All frames as HTML video", id="export-scatter3d", n_clicks=0),
                    dbc.DropdownMenuItem(divider=True),
                    dbc.DropdownMenuItem("Filtered data (current frame)", id="export-data-current", n_clicks=0),
                    dbc.DropdownMenuItem("Filtered data (all frames)", id="export-data-all", n_clicks=0),
                ],
                label=html.I(className="bi bi-box-arrow-up"),
                id="export-dropdown",
                align_end=True,
                color="transparent",
                toggle_class_name="sv-icon-btn",
            )
        ],
        id="export-spinner",
        display="hide",
        delay_hide=1000,
    )


def get_topbar_layout():
    """
    Build the application top bar.

    Returns:
        html.Header: The top bar.
    """
    return html.Header(
        [
            _brand(),
            *_breadcrumb(),
            *_combine_control(),
            html.Div(className="sv-topbar-spacer"),
            html.Div(
                [
                    _theme_toggle(),
                    _export_menu(),
                    dbc.Tooltip("Export", target="export-dropdown", placement="bottom"),
                ],
                className="sv-topbar-actions",
            ),
        ],
        className="sv-topbar",
    )
