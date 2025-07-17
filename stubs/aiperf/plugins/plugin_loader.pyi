#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from aiperf.common.exceptions import PluginError as PluginError

def load_plugins(plugin_dirs: list[Path]) -> None: ...
