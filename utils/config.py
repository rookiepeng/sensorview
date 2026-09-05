"""Configuration File Persistence

Reads and writes the JSON a dataset is configured by: the per-case ``info.json``
the file picker loads, and the ``config.json`` the app remembers the last opened
path in. Both are plain documents -- nothing here knows what the keys mean.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Dict, Any

import json


def load_config(json_file: str) -> Dict[str, Any]:
    """
    Load a configuration file from JSON format.

    Args:
        json_file: Path to the JSON configuration file.

    Returns:
        Dictionary containing the configuration data.
    """
    with open(json_file, "r", encoding="utf-8") as read_file:
        return json.load(read_file)


def save_config(json_dict: Dict[str, Any], json_file: str) -> None:
    """
    Save configuration data to a JSON file.

    Args:
        json_dict: Dictionary containing configuration data to save.
        json_file: Path where the JSON file will be saved.
    """
    with open(json_file, "w+", encoding="utf-8") as write_file:
        json.dump(json_dict, write_file, indent=4)
