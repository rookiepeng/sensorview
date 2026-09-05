"""Session Cache Helpers

The disk cache every session's derived data passes through: loaded frames, the
figure buffer the API serves, the manifest, the filter arguments. Keys are
composed rather than declared -- a major key from :data:`settings.CACHE_KEYS`,
the session id, and an optional minor key such as a frame id -- which is what
keeps one session's entries from being read by another.

Entries expire on their own after :data:`settings.EXPIRATION`; the cache is
never cleared wholesale, since a background-callback worker may be mid-write.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Optional, Any

from settings import EXPIRATION
from settings import frame_cache


def cache_set(
    data: Any, id_str: str, key_major: str, key_minor: Optional[str] = None
) -> None:
    """
    Store data in the cache with expiration time.

    Args:
        data: Data to be cached (any type).
        id_str: Unique identifier string for the cache entry.
        key_major: Primary key component for cache entry.
        key_minor: Optional secondary key component for cache entry. Defaults to None.
    """
    if key_minor is None:
        key_str = key_major + id_str
    else:
        key_str = key_major + id_str + key_minor

    frame_cache.set(key_str, data, expire=EXPIRATION)


def cache_expire() -> None:
    """
    Expire all items in the cache immediately.
    """
    frame_cache.expire()


def cache_get(
    id_str: str, key_major: str, key_minor: Optional[str] = None
) -> Optional[Any]:
    """
    Retrieve data from the cache.

    Args:
        id_str: Unique identifier string for the cache entry.
        key_major: Primary key component for cache entry.
        key_minor: Optional secondary key component for cache entry. Defaults to None.

    Returns:
        Cached data if found, None otherwise.
    """
    if key_minor is None:
        key_str = key_major + id_str
    else:
        key_str = key_major + id_str + key_minor

    val = frame_cache.get(key_str, default=None, retry=True)
    return val
