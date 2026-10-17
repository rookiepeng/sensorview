"""Native-shell capabilities, as seen from the Dash app.

This used to be the desktop shell: waitress on loopback, a pywebview window
around it, and the platform matrix that came with it -- WebView2 on Windows,
WKWebView on macOS, WebKitGTK or QtWebEngine on Linux, each with its own
installation story and its own bugs. Electron replaces all of it. The window,
the menus and the native dialogs are in ``src/main``.

What is left is the two questions the Dash layouts ask. Both now answer "no
native shell here", which is the path those call sites already had for being
served to a browser: the Browse button renders disabled and the user types a
path instead. That is the correct answer while the Dash views are hosted
inside Electron, because the folder chooser they would reach for is the
Electron one, wired to ``case:open`` and owned by the renderer.

This module goes away with the last Dash view.

Usage:
    from server.desktop import is_available, pick_folder

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Optional


def is_available() -> bool:
    """
    Report whether a native window is hosting this session.

    Always False now. The layouts use it to decide whether the desktop-only
    affordances can do anything, and under Electron they cannot -- the native
    dialog belongs to the main process, not to a Dash callback.

    Returns:
        bool: False.
    """
    return False


def pick_folder(initial_path: Optional[str] = None) -> Optional[str]:
    """
    Open the OS folder chooser.

    Always None now; see :func:`is_available`. Callers already treat None as
    "cancelled or unavailable" and leave a typed path alone, so nothing above
    this needs to know the shell went away.

    Args:
        initial_path: Ignored.

    Returns:
        None.
    """
    return None
