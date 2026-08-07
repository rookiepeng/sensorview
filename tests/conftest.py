"""Shared fixtures for the manifest tests.

A manifest is only meaningful next to the files it describes -- sidecars are
discovered on disk, not declared -- so most of these tests need a real directory
with real (empty) files in it rather than a dict.

Author: Zhengyu Peng
License: GPL-3.0
"""

import json

import pytest


@pytest.fixture
def make_case(tmp_path):
    """
    Build a case directory on disk.

    Returns a factory taking the manifest dict to write as ``info.json`` (None
    writes no manifest at all) and the sidecar filenames to create empty. Each
    call gets its own directory, so one test can compare two cases.
    """
    counter = {"n": 0}

    def _make(manifest=None, files=(), name=None):
        counter["n"] += 1
        case = tmp_path / (name or f"case_{counter['n']}")
        case.mkdir(parents=True, exist_ok=True)
        if manifest is not None:
            (case / "info.json").write_text(
                json.dumps(manifest), encoding="utf-8", newline="\n"
            )
        for file_name in files:
            (case / file_name).touch()
        return str(case)

    return _make


@pytest.fixture
def v2_manifest():
    """A minimal v2 manifest declaring every optional block."""
    return {
        "manifest_version": 2,
        "name": "Example",
        "table": {"slider": "Frame", "keys": {"speed": {"description": "Speed"}}},
        "cloud": {"suffix": ".cloud.h5"},
        "curve": {"suffix": ".curve.h5"},
        "image": {"suffix": [".mp4", ".avi"]},
    }


@pytest.fixture
def v1_manifest():
    """A v1 manifest: flat, no manifest_version."""
    return {
        "name": "Legacy",
        "slider": "Frame",
        "x_3d": "x",
        "y_3d": "y",
        "z_3d": "z",
        "keys": {"speed": {"description": "Speed"}},
    }
