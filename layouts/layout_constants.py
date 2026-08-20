"""Layout Constants Module

Reusable constants for layout components including color scale options for visualizations.

Usage:
    from layouts.layout_constants import colorscales

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

colorscales = [
    "Blackbody",
    "Bluered",
    "Blues",
    "Earth",
    "Electric",
    "Greens",
    "Greys",
    "Hot",
    "Jet",
    "Picnic",
    "Portland",
    "Rainbow",
    "RdBu",
    "Reds",
    "Viridis",
    "YlGnBu",
    "YlOrRd",
]

# The full-screen loading overlays' geometry lives in the stylesheet; callbacks
# only ever toggle ``display``.
HIDE_LOADING = {"display": "none"}
SHOW_LOADING = {"display": "flex"}
