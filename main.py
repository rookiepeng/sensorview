"""SensorView Entry Point

Start the app here::

    python main.py

Everything else is a piece of it: :mod:`app` wires the Dash application,
:mod:`settings` holds the shared configuration, and :mod:`desktop` hosts a
running server in a native window. None of them start anything on import.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from multiprocessing import freeze_support

import desktop

from app import app
from settings import APP_TITLE

# The Dash dev server instead of the desktop window: hot reload and in-browser
# tracebacks, served on every interface.
DEBUG = False

# Loopback port the desktop shell serves on. Only the webview connects to it.
PORT = 8521


def main() -> None:
    """
    Serve the app.

    Returns:
        None
    """
    if DEBUG:
        app.run(debug=True, threaded=True, processes=1, host="0.0.0.0")
        return

    # Spawned background-callback workers re-import this module, so the
    # freeze support has to be in place before anything else starts.
    freeze_support()

    # Serves on loopback with waitress and shows it in an OS webview. For a
    # deployment, drop the window and serve on a public interface instead:
    #     from waitress import serve
    #     serve(app.server, listen="*:8000")
    desktop.run(app.server, title=APP_TITLE, port=PORT)


if __name__ == "__main__":
    main()
