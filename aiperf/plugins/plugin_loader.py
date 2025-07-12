# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import importlib
from pathlib import Path

from aiperf.common.exceptions import PluginError


def load_plugins(plugin_dirs: list[Path]) -> None:
    """Load all plugins from the given directories."""
    for plugin_dir in plugin_dirs:
        if not plugin_dir.exists():
            raise PluginError(f"Plugin directory {plugin_dir} does not exist")

        for python_file in plugin_dir.glob("*.py"):
            if python_file.name != "__init__.py":
                module_name = python_file.stem  # Get filename without extension
                try:
                    importlib.import_module(f"aiperf.plugins.{module_name}")
                except ImportError as err:
                    raise PluginError(
                        f"Error importing plugin module '{module_name}'"
                    ) from err
