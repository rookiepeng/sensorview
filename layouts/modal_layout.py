"""SensorView Modal Layout Module

This module defines the data selection modal dialog components used in the
SensorView application.
"""

from typing import List
from dash import html
import dash_bootstrap_components as dbc

def get_path_input_group() -> dbc.InputGroup:
    """Get the data path input group component."""
    return dbc.InputGroup([
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
    ])

def get_tooltips() -> List[dbc.Tooltip]:
    """Get the tooltip components for the modal."""
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
    """Get the test case picker component."""
    return dbc.InputGroup([
        dbc.InputGroupText("Test Case"),
        dbc.Select(id="case-picker-modal"),
    ])

def get_file_picker() -> dbc.InputGroup:
    """Get the log file picker component."""
    return dbc.InputGroup([
        dbc.InputGroupText("Log File"),
        dbc.Select(id="file-picker-modal"),
    ])

def get_modal_body() -> dbc.Row:
    """Get the modal body component with all input groups."""
    return dbc.Row([
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
    ])

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
