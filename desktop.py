"""SensorView Desktop Shell

Runs the Dash server inside a native window rather than a browser tab: waitress
serves the app on the loopback interface, and pywebview wraps it in an OS
webview -- WebView2 on Windows, WKWebView on macOS, WebKitGTK on Linux.

The window owns the process. Closing it returns from ``run()``, which is what
ends the app; there is no heartbeat between page and server deciding whether
the user is still there.

Neither pywebview nor waitress is imported at module scope. A server
deployment imports this module only for :func:`is_available` and
:func:`pick_folder` -- both of which answer without a window -- and should not
have to install a GUI toolkit to do it.

Usage:
    from desktop import run, is_available, pick_folder

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Optional

import os
import socket
import sys
import threading
import time
import traceback

# The live native window, or None when the app is being served to a browser
# instead. Everything else in this module keys off it.
_window: Any = None


def is_available() -> bool:
    """
    Report whether a native window is hosting this session.

    Layouts call this to decide whether the desktop-only affordances -- the
    folder picker being the one that exists today -- can do anything.

    Returns:
        bool: True when running inside the desktop shell.
    """
    return _window is not None


def pick_folder(initial_path: Optional[str] = None) -> Optional[str]:
    """
    Open the OS folder chooser.

    Safe to call from a Dash callback: every pywebview backend marshals the
    dialog onto its GUI thread and blocks the caller until it closes, so this
    occupies one waitress worker for as long as the dialog is up.

    Args:
        initial_path: Directory to open the dialog at. Ignored if it does not
            exist, which is the normal case while the path field is half typed.

    Returns:
        Optional[str]: The chosen directory, or None if the user cancelled or
        no native window is hosting the session.
    """
    if _window is None:
        return None

    import webview

    start_at = ""
    if initial_path and os.path.isdir(initial_path):
        start_at = os.path.abspath(initial_path)

    # pywebview 6 moved the dialog constants into an enum and deprecated the
    # module-level names it had before.
    dialogs = getattr(webview, "FileDialog", None)
    folder = dialogs.FOLDER if dialogs is not None else webview.FOLDER_DIALOG

    result = _window.create_file_dialog(folder, directory=start_at)
    if not result:
        return None

    return os.path.normpath(result[0])


def _asset(name: str) -> str:
    """
    Resolve a file in ``assets`` for both a source run and a frozen build.

    PyInstaller collects ``assets`` next to the bundled modules, so the
    unpack directory is where a built app finds it and this file's own
    directory is where a source checkout does.

    Args:
        name: File name inside ``assets``.

    Returns:
        str: Absolute path, which may not exist.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", name)


def _window_icon() -> Optional[str]:
    """
    Pick the icon file the platform's window manager can actually load.

    WinForms wants a real multi-resolution ``.ico``; GTK and Cocoa go through
    loaders where PNG is the format guaranteed to be present.

    Returns:
        Optional[str]: Path to the icon, or None if it is missing -- in which
        case the window falls back to the executable's own icon.
    """
    name = "favicon.ico" if sys.platform == "win32" else "favicon.png"
    path = _asset(name)

    return path if os.path.isfile(path) else None


def _claim_taskbar_identity(app_id: str = "SensorView.SensorView") -> None:
    """
    Tell Windows this process is SensorView rather than whatever launched it.

    The window icon alone does not settle the taskbar: without an explicit
    AppUserModelID a source run groups and pins itself under the Python
    interpreter that hosts it, icon and all.
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        # Cosmetic only -- never worth failing a launch over.
        pass


def _app_data_dir() -> str:
    """
    Locate the per-user directory the app keeps its own state in.

    Returns:
        str: Data directory, created if missing.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    path = os.path.join(base, "SensorView")
    os.makedirs(path, exist_ok=True)
    return path


def _storage_path() -> str:
    """
    Locate the per-user directory the webview keeps its profile in.

    IndexedDB is not a cache here -- the frame buffer the worker fills lives in
    it -- so the window runs with persistent storage rather than pywebview's
    default private mode, and needs somewhere of its own to keep it.

    Returns:
        str: Profile directory, created if missing.
    """
    path = os.path.join(_app_data_dir(), "webview")
    os.makedirs(path, exist_ok=True)
    return path


def _record_gui_failure(error: BaseException) -> Optional[str]:
    """
    Write down why the native window could not start.

    A built app is windowed, so it has no console: ``sys.stdout`` is None there
    and the message printed beside this call goes nowhere. That leaves the
    browser fallback looking like a deliberate choice rather than a failure,
    which is exactly how a bundling problem stays invisible.

    Args:
        error: The exception the GUI backend raised.

    Returns:
        Optional[str]: Path to the log, or None if it could not be written.
    """
    path = os.path.join(_app_data_dir(), "desktop.log")
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = traceback.format_exception(type(error), error, error.__traceback__)

    try:
        with open(path, "a", encoding="utf-8") as log:
            log.write(f"\n=== {stamp} native window unavailable ===\n")
            log.writelines(lines)
    except OSError:
        return None

    return path


def _wait_for_server(host: str, port: int, timeout: float = 30.0) -> bool:
    """
    Block until the WSGI thread is accepting connections.

    Without this the webview can reach the URL before waitress has bound the
    socket and paint its own connection-error page, which does not reload
    itself once the server does come up.

    Args:
        host: Interface waitress was told to listen on.
        port: Port waitress was told to listen on.
        timeout: Seconds to wait before giving up.

    Returns:
        bool: True once the port accepts a connection.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.25)
            if probe.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.05)

    return False


def _terminate_children() -> None:
    """
    Stop the background-callback workers before the process leaves.

    A dataset load runs in a worker process that Dash's DiskcacheManager
    spawned. Closing the window mid-load would otherwise orphan it, and an
    orphan keeps writing into the disk cache the next launch reads.
    """
    try:
        import psutil

        children = psutil.Process().children(recursive=True)
    except Exception:
        return

    for child in children:
        try:
            child.terminate()
        except psutil.Error:
            pass

    _, alive = psutil.wait_procs(children, timeout=3)
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass


def _serve_forever(server: Any, host: str, port: int) -> None:
    """
    Run the WSGI server. Target of the serving thread.

    Args:
        server: The Flask application (``app.server``).
        host: Interface to listen on.
        port: Port to listen on.
    """
    from waitress import serve

    serve(server, host=host, port=port, threads=8)


def run(
    server: Any,
    title: str,
    host: str = "127.0.0.1",
    port: int = 8521,
    width: int = 1600,
    height: int = 1000,
) -> None:
    """
    Serve the app and show it in a native window until that window closes.

    Falls back to the default browser when no GUI backend can be brought up --
    a Linux box without WebKitGTK, chiefly. The app is fully usable that way;
    what is lost is the window owning the process, so the fallback has to be
    ended with Ctrl+C.

    Must be called from the main thread: every platform's event loop insists on
    it.

    Args:
        server: The Flask application (``app.server``).
        title: Window title.
        host: Interface to listen on. Loopback -- this is not a deployment.
        port: Port to listen on.
        width: Initial window width in pixels.
        height: Initial window height in pixels.
    """
    global _window

    _claim_taskbar_identity()

    threading.Thread(
        target=_serve_forever,
        args=(server, host, port),
        name="sensorview-wsgi",
        daemon=True,
    ).start()

    url = f"http://{host}:{port}"
    if not _wait_for_server(host, port):
        raise RuntimeError(f"SensorView server did not come up on {url}")

    try:
        import webview

        # Every export in the app -- figures, Parquet, the animation -- is
        # delivered through dcc.Download, which lands as a browser download.
        # pywebview cancels those outright unless asked not to, so leaving this
        # at its default makes every export button do nothing at all.
        webview.settings["ALLOW_DOWNLOADS"] = True

        _window = webview.create_window(
            title,
            url,
            width=width,
            height=height,
            min_size=(1024, 700),
            # Off by default in a webview, and hover readouts and column names
            # are things worth copying out of.
            text_select=True,
        )
        # Every backend honours this, whatever pywebview's own docstring says.
        # Without it the window borrows the icon of the executable hosting it,
        # which for a source run is the Python interpreter's.
        webview.start(
            private_mode=False,
            storage_path=_storage_path(),
            icon=_window_icon(),
        )
    except Exception as gui_error:  # no GUI backend, or it failed to start
        _window = None
        import webbrowser

        log_path = _record_gui_failure(gui_error)
        detail = f"; details in {log_path}" if log_path else ""
        print(
            f"Native window unavailable ({gui_error}){detail}; opening {url}",
            flush=True,
        )
        webbrowser.open(url)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
    finally:
        _window = None
        _terminate_children()
