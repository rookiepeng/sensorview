"""SensorView Entry Point

Start the app here::

    python main.py

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import os
import sys

from multiprocessing import freeze_support

from server import desktop

from server.dash_app import app
from settings import APP_TITLE

# The Dash dev server instead of the desktop window: hot reload and in-browser
# tracebacks, served on every interface. Asked for rather than edited in place,
# so a dev run never has to be committed and reverted:
#     python main.py --debug
#     SENSORVIEW_DEBUG=1 python main.py
# The flag is what a launch configuration can pass; the variable is what a
# shell or a container can set.
DEBUG = os.environ.get("SENSORVIEW_DEBUG") == "1" or "--debug" in sys.argv[1:]

# Port the dev server listens on. The desktop shell uses PORT below instead.
DEBUG_PORT = int(os.environ.get("SENSORVIEW_DEBUG_PORT", "8050"))

# Loopback port the desktop shell serves on. Only the webview connects to it.
PORT = 8521


def main() -> None:
    """
    Serve the app.

    Returns:
        None
    """
    if DEBUG:
        app.run(debug=True, threaded=True, processes=1, host="0.0.0.0", port=DEBUG_PORT)
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
