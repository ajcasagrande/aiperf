# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base_enums import (
    BasePydanticBackedStrEnum,
    BasePydanticEnumInfo,
    CaseInsensitiveStrEnum,
)


class AIPerfPluginType(CaseInsensitiveStrEnum):
    """The type of a plugin. This is equivalent to the entry-point type in the pyproject.toml file.

    This is used to identify the plugin type when registering with the PluginFactory.
    """

    SERVICE = "aiperf.service"
    UI = "aiperf.ui"


def get_available_plugins(plugin_type: AIPerfPluginType) -> list[str]:
    """Get list of available plugins for a given plugin type."""
    from aiperf.common.plugin_manager import AIPerfPluginManager

    pm = AIPerfPluginManager()
    return pm.list_plugins(plugin_type)


def create_plugin_enum(
    plugin_type: AIPerfPluginType, enum_name: str
) -> type[BasePydanticBackedStrEnum]:
    """Create a dynamic BasePydanticBackedStrEnum of available plugins for a given plugin type."""
    plugins = get_available_plugins(plugin_type)
    return BasePydanticBackedStrEnum(
        enum_name,
        {name.replace("-", "_"): BasePydanticEnumInfo(tag=name) for name in plugins},
    )  # type: ignore


# Create the UI enum immediately so it's available for UserConfig
AIPerfUIType = create_plugin_enum(AIPerfPluginType.UI, "AIPerfUIType")
