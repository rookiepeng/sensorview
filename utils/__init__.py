"""Shared Helpers

The handful of things that are needed everywhere and belong to no one view. Not
a grab bag by accident -- each submodule is one concern, and nothing here knows
about the others:

- :mod:`~utils.cache`    the session disk cache, keyed by session id
- :mod:`~utils.config`   JSON persistence for ``info.json`` and ``config.json``
- :mod:`~utils.data`     loading the radar table through :mod:`dataio`
- :mod:`~utils.filters`  reducing a frame to the rows the filter panel allows

Figure construction used to live here too; it is :mod:`viz.figure_kwargs` now,
beside the renderers that consume it.

The names below are re-exported so callers import from the package rather than
reaching into a submodule.

Usage:
    from utils import cache_get, cache_set
    from utils import filter_all, load_data

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from utils.cache import (
    cache_set,
    cache_get,
    cache_expire,
)
from utils.config import (
    load_config,
    save_config,
)
from utils.data import load_data
from utils.filters import (
    clamp_frame_index,
    filter_all,
)

__all__ = [
    "cache_set",
    "cache_get",
    "cache_expire",
    "load_config",
    "save_config",
    "load_data",
    "clamp_frame_index",
    "filter_all",
]
