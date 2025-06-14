from dash import html

import dash_bootstrap_components as dbc


modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("Select Data File"), close_button=False),
        dbc.ModalBody(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.InputGroup(
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
                        ),
                        width=12,
                    ),
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
                    dbc.Col(
                        dbc.InputGroup(
                            [
                                dbc.InputGroupText("Test Case"),
                                dbc.Select(id="case-picker-modal"),
                            ]
                        ),
                        width=12,
                        className="mt-3",
                    ),
                    dbc.Tooltip(
                        "Select a test case",
                        target="case-picker-modal",
                        placement="top",
                    ),
                    dbc.Col(
                        dbc.InputGroup(
                            [
                                dbc.InputGroupText("Log File"),
                                dbc.Select(id="file-picker-modal"),
                            ]
                        ),
                        width=12,
                        className="mt-3",
                    ),
                    dbc.Tooltip(
                        "Select a log file",
                        target="file-picker-modal",
                        placement="top",
                    ),
                ]
            )
        ),
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
