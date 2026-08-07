"""Pytest root marker.

Its presence at the repository root is what puts the root on ``sys.path`` under
pytest's default import mode, so tests can ``import utils`` and
``from dataio.frames import ...`` the same way the application does. Without it
only ``tests/`` would be importable and every test module would need its own
path shim.
"""
