"""SensorView Modal Layout Module

Defines the data selection modal dialog layout for the SensorView application,
using Dash and Bootstrap components.

Core Components:
---------------
- Data path input group
- Test case picker
- Log file picker
- Tooltips for guidance
- Modal dialog structure

Dependencies:
------------
- dash & dash-bootstrap-components

Usage:
------
Import the modal layout:
    from layouts.modal_layout import modal

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import List
from dash import html
import dash_bootstrap_components as dbc


def get_path_input_group() -> dbc.InputGroup:
    """
    Create the input group for specifying the data path.

    Returns:
        dbc.InputGroup: Input group component for the data path.
    """
    return dbc.InputGroup(
        [
            dbc.InputGroupText("Data Path"),
            dbc.Input(
                id="data-path-modal",
                placeholder="Add path to the data files ...",
                type="text",
            ),
            dbc.Button(
                html.I(className="bi bi-arrow-clockwise"),
                id="refresh-button-modal",
                n_clicks=0,
            ),
        ]
    )


def get_tooltips() -> List[dbc.Tooltip]:
    """
    Create tooltip components for modal input elements.

    Returns:
        List[dbc.Tooltip]: List of tooltip components for guidance.
    """
    return [
        dbc.Tooltip(
            "Directory of the data files",
            target="data-path-modal",
            placement="top",
        ),
        dbc.Tooltip(
            "Refresh test cases",
            target="refresh-button-modal",
            placement="top",
        ),
        dbc.Tooltip(
            "Select a test case",
            target="case-picker-modal",
            placement="top",
        ),
        dbc.Tooltip(
            "Select a log file",
            target="file-picker-modal",
            placement="top",
        ),
    ]


def get_case_picker() -> dbc.InputGroup:
    """
    Create the input group for selecting a test case.

    Returns:
        dbc.InputGroup: Input group component for test case selection.
    """
    return dbc.InputGroup(
        [
            dbc.InputGroupText("Test Case"),
            dbc.Select(id="case-picker-modal"),
        ]
    )


def get_file_picker() -> dbc.InputGroup:
    """
    Create the input group for selecting a log file.

    Returns:
        dbc.InputGroup: Input group component for log file selection.
    """
    return dbc.InputGroup(
        [
            dbc.InputGroupText("Log File"),
            dbc.Select(id="file-picker-modal"),
        ]
    )


def get_modal_body() -> dbc.Row:
    """
    Assemble the modal body with all input groups and tooltips.

    Returns:
        dbc.Row: Modal body layout containing all input elements.
    """
    return dbc.Row(
        [
            dbc.Col(get_path_input_group(), width=12),
            *get_tooltips(),
            dbc.Col(
                get_case_picker(),
                width=12,
                className="mt-3",
            ),
            dbc.Col(
                get_file_picker(),
                width=12,
                className="mt-3",
            ),
        ]
    )


modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("Select Data File"), close_button=False),
        dbc.ModalBody(get_modal_body()),
        dbc.ModalFooter(
            dbc.Button(
                "OK",
                id="ok-modal",
                className="ms-auto",
                n_clicks=0,
            )
        ),
    ],
    id="modal-centered",
    size="lg",
    keyboard=False,
    centered=True,
    is_open=True,
    backdrop="static",
)
