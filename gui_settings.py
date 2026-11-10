#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persistent settings shared by the leakage-analysis Tk applications."""

import json
import os
from pathlib import Path


ENVIRONMENT_VARIABLE = "SPECTRE_LEAKAGE_SETTINGS"


def settings_path():
    """Return the user settings path, allowing tests/sites to override it."""
    override = os.environ.get(ENVIRONMENT_VARIABLE)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".spectre_leakage_analyzer.json"


def _load_all():
    path = settings_path()
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def load_settings(section):
    """Load one GUI section; malformed or absent settings use defaults."""
    value = _load_all().get(section, {})
    return value if isinstance(value, dict) else {}


def save_settings(section, values):
    """Atomically update one GUI section without discarding other sections."""
    path = settings_path()
    data = _load_all()
    data[section] = values
    parent = path.parent
    if not parent.is_dir():
        parent.mkdir(parents=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")
    try:
        os.chmod(str(temporary), 0o600)
    except OSError:
        pass
    os.replace(str(temporary), str(path))
