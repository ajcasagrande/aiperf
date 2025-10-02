# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class AIPerfPluginType(CaseInsensitiveStrEnum):
    """The type of a plugin. This is equivalent to the entry-point type in the pyproject.toml file.

    This is used to identify the plugin type when registering with the PluginFactory.
    """

    SERVICE = "aiperf.service"
    UI = "aiperf.ui"
