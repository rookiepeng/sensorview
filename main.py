"""SensorView Dash dev server.

Serves the Dash views for the Electron window to load while the renderer is
being ported::

    python main.py                 # http://127.0.0.1:8050
    npm run dev                    # the window, in a second terminal

Hosting those views in a native window used to be this file's job, through
:mod:`server.desktop`. It is now ``src/main/index.ts``: one Chromium instead of
four OS webviews, and native dialogs and downloads that behave the same way on
every platform.

This file goes away with the last Dash view.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import os

from server.dash_app import app

# Loopback by default -- the only thing that should reach these views is the
# Electron window on this machine. Set SENSORVIEW_HOST=0.0.0.0 to reach them
# from a browser on another device.
HOST = os.environ.get("SENSORVIEW_HOST", "127.0.0.1")
PORT = int(os.environ.get("SENSORVIEW_PORT", "8050"))


def main() -> None:
    """
    Serve the Dash views.

    Returns:
        None
    """
    app.run(debug=True, threaded=True, processes=1, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
