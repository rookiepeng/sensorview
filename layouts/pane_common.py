"""Analysis Pane Building Blocks

Shared structure for the six charts in the bottom dock. They differ only in
which selectors sit in the control strip, so the strip, the plot area, and the
loading behaviour are defined once here.

Every pane is a fixed-height control strip over a plot that takes all remaining
height. Because the dock is user-resizable, panes never carry a hard-coded plot
height -- they inherit whatever the dock currently is.

Usage:
    from layouts.pane_common import labelled_select, pane

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import List, Optional

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc


def labelled_select(component_id: str, label: str, tooltip: str, **kwargs) -> html.Div:
    """
    Build a compact labelled select with its tooltip.

    Args:
        component_id: Component id, also the tooltip target.
        label: Prefix shown in the input group.
        tooltip: Explanatory text.
        **kwargs: Extra props forwarded to ``dbc.Select``.

    Returns:
        html.Div: The input group and its tooltip.
    """
    return html.Div(
        [
            dbc.InputGroup(
                [dbc.InputGroupText(label), dbc.Select(id=component_id, **kwargs)],
                size="sm",
            ),
            dbc.Tooltip(tooltip, target=component_id, placement="top"),
        ],
        className="sv-grow",
    )


def number_input(component_id: str, label: str) -> dbc.InputGroup:
    """
    Build an axis-limit entry box that falls back to autoscaling when empty.

    Args:
        component_id: Component id.
        label: Prefix shown in the input group.

    Returns:
        dbc.InputGroup: The bounded number input.
    """
    return dbc.InputGroup(
        [
            dbc.InputGroupText(label),
            dbc.Input(
                id=component_id, type="number", placeholder="auto", debounce=True
            ),
        ],
        size="sm",
    )


def icon_button(
    component_id: str,
    icon: str,
    tooltip: str,
    color: str = "secondary",
    class_name: str = "",
) -> html.Div:
    """
    Build a pane action button.

    Args:
        component_id: Component id, also the tooltip target.
        icon: Bootstrap icon class suffix.
        tooltip: Explanatory text.
        color: dbc button color.
        class_name: Extra classes on the wrapper, e.g. ``ms-auto`` to start the
            right-aligned action group.

    Returns:
        html.Div: The button and its tooltip.
    """
    return html.Div(
        [
            dbc.Button(
                html.I(className=f"bi {icon}"),
                id=component_id,
                color=color,
                size="sm",
                n_clicks=0,
            ),
            dbc.Tooltip(tooltip, target=component_id, placement="top"),
        ],
        className=class_name,
    )


def pane(
    controls: List,
    graph: dcc.Graph,
    collapse_id: str,
    loading_id: str,
    extra_rows: Optional[List] = None,
) -> html.Div:
    """
    Assemble one dock pane.

    The collapse is what gates rendering: a view whose switch is off produces no
    figure at all, which is the whole point of the switches -- these charts are
    expensive and there is no reason to compute one nobody is looking at.

    The spinner wraps the control strip as well as the plot. Every one of those
    selectors is an input to the background callback the spinner belongs to, so
    a pane that leaves them live while it recomputes is inviting a second job to
    be queued on top of the one already running. ``overlay_style`` dims them and
    takes their pointer events rather than hiding them, so the strip keeps its
    height -- the plot below would otherwise jump every time a figure is
    regenerated -- and the settings the pending figure is being built from stay
    readable while it is built.

    Args:
        controls: Components for the control strip.
        graph: The pane's figure.
        collapse_id: Id of the render gate, driven by the view's enable switch.
        loading_id: Id of the spinner wrapper.
        extra_rows: Optional extra rows placed under the control strip.

    Returns:
        html.Div: The pane.
    """
    return html.Div(
        dcc.Loading(
            id=loading_id,
            type="default",
            # `className` styles the spinner; `parent_className` is the box the
            # spinner is centred in, which is now the whole pane body.
            parent_className="sv-pane-body",
            overlay_style={
                "visibility": "visible",
                "opacity": 0.4,
                "pointerEvents": "none",
            },
            # One wrapper of our own, so the flex column can be handed down
            # through the unclassed div dcc.Loading renders around its children.
            children=html.Div(
                [
                    html.Div(controls, className="sv-pane-controls"),
                    *(extra_rows or []),
                    html.Div(
                        dbc.Collapse(graph, id=collapse_id, is_open=False),
                        className="sv-pane-plot",
                    ),
                ],
                className="sv-pane-stack",
            ),
        ),
        className="sv-pane",
    )
