"""SensorView Modal Layout Module

The data selection dialog, opened by the top bar breadcrumb, plus the error
dialog shown when a log fails to load.

Usage:
    from layouts.modal_layout import get_modal_layout, get_error_modal

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import List

from dash import html

import dash_bootstrap_components as dbc

from server import desktop


def _field(label: str, control, hint: str, target: str) -> html.Div:
    """
    Build one labelled row of the dialog.

    Args:
        label: Field caption.
        control: The input group for the field.
        hint: Tooltip text.
        target: Component the tooltip attaches to.

    Returns:
        html.Div: The labelled field.
    """
    return html.Div(
        [
            html.Span(label, className="sv-section-label"),
            control,
            dbc.Tooltip(hint, target=target, placement="top"),
        ],
        className="sv-field",
    )


def get_modal_body() -> List[html.Div]:
    """
    Assemble the dialog body: where the data lives, then what to open.

    Returns:
        List[html.Div]: Path, test case, and log file fields.
    """
    # A native folder chooser needs a native window. Served to a browser the
    # button stays, disabled, rather than the field silently changing shape.
    native_dialogs = desktop.is_available()

    return [
        _field(
            "Data path",
            dbc.InputGroup(
                [
                    dbc.Input(
                        id="data-path-modal",
                        placeholder="Directory containing the test cases …",
                        type="text",
                    ),
                    dbc.Button(
                        html.I(className="bi bi-folder2-open"),
                        id="browse-button-modal",
                        n_clicks=0,
                        disabled=not native_dialogs,
                    ),
                    dbc.Tooltip(
                        (
                            "Browse for a folder"
                            if native_dialogs
                            else "Browsing is available in the desktop app"
                        ),
                        target="browse-button-modal",
                        placement="top",
                    ),
                    dbc.Button(
                        html.I(className="bi bi-arrow-clockwise"),
                        id="refresh-button-modal",
                        n_clicks=0,
                    ),
                    dbc.Tooltip(
                        "Rescan for test cases",
                        target="refresh-button-modal",
                        placement="top",
                    ),
                ]
            ),
            "Directory of the data files",
            "data-path-modal",
        ),
        _field(
            "Test case",
            dbc.Select(id="case-picker-modal"),
            "Select a test case",
            "case-picker-modal",
        ),
        _field(
            "Log file",
            dbc.Select(id="file-picker-modal"),
            "Select a log file",
            "file-picker-modal",
        ),
    ]


def get_modal_layout() -> dbc.Modal:
    """
    Build the data selection dialog.

    It opens on load and cannot be dismissed without a selection: with no log
    there is nothing for the workbench to show.

    Returns:
        dbc.Modal: The dialog.
    """
    return dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle(
                    html.Span(
                        [html.I(className="bi bi-database"), "Open dataset"],
                        className="sv-modal-title",
                    )
                ),
                close_button=False,
            ),
            dbc.ModalBody(get_modal_body()),
            dbc.ModalFooter(
                dbc.Button("Open", id="ok-modal", color="primary", n_clicks=0)
            ),
        ],
        id="modal-centered",
        size="lg",
        keyboard=False,
        centered=True,
        is_open=True,
        backdrop="static",
    )


def get_error_modal() -> dbc.Modal:
    """
    Build the load-failure dialog.

    Returns:
        dbc.Modal: The dialog.
    """
    return dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle(
                    html.Span(
                        [
                            html.I(className="bi bi-exclamation-triangle text-warning"),
                            "Could not load data",
                        ],
                        className="sv-modal-title",
                    )
                )
            ),
            dbc.ModalBody(html.P(id="error-modal-message", className="mb-0")),
            dbc.ModalFooter(
                dbc.Button(
                    "Close", id="close-error-modal", color="secondary", n_clicks=0
                )
            ),
        ],
        id="error-modal",
        centered=True,
        is_open=False,
    )
