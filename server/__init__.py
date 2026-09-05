"""SensorView Application Shell

Everything that exists to assemble the app and put it in front of a user. The
four modules are one pipeline, read top to bottom:

- :mod:`~server.dash_app`    wires the layout, the routes and every callback
  module into the ``app`` from :mod:`settings`, and stops there -- importing it
  starts nothing
- :mod:`~server.clientside`  the callbacks that run in the browser, registered
  by the above
- :mod:`~server.routes`      the plain HTTP endpoints the browser fetches
  outside Dash's callback protocol
- :mod:`~server.desktop`     serves a wired app with waitress and shows it in a
  native window

Nothing is re-exported here on purpose. :mod:`~server.desktop` is imported by
:mod:`layouts.modal_layout`, which :mod:`~server.dash_app` pulls in while
assembling -- re-exporting ``app`` from this file would put that cycle in the
package's own import, so callers name the module they want::

    from server.dash_app import app
    from server import desktop

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""
