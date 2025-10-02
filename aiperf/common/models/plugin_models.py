# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aiperf.common.enums.plugin_enums import AIPerfPluginType


class AIPerfPluginMetadata(BaseModel):
    """Metadata for a plugin.

    This is used to identify the plugin in the plugin factory.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(..., description="The name of the plugin.", min_length=1)
    version: str = Field(..., description="The version of the plugin.", min_length=1)
    description: str | None = Field(
        default=None, description="The description of the plugin.", min_length=1
    )
    author: str | None = Field(
        default=None, description="The author of the plugin.", min_length=1
    )
    author_email: str | None = Field(
        default=None, description="The email of the author of the plugin.", min_length=1
    )
    url: str | None = Field(
        default=None, description="The URL of the plugin.", min_length=1
    )


class AIPerfPluginMapping(BaseModel):
    """Mapping information for a plugin.

    Used to store the plugin type, name, class type, entry point, and metadata for the PluginManager.
    """

    plugin_type: AIPerfPluginType = Field(
        ...,
        description="The type of the plugin. This is the plugin type as defined in the pyproject.toml file.",
    )
    name: str = Field(
        ...,
        description="The name of the plugin. This is the name of the plugin as defined in the pyproject.toml file.",
        min_length=1,
    )
    package_name: str = Field(
        ...,
        description="The name of the package that provides the plugin. This is the name of the package as defined in the pyproject.toml file.",
        min_length=1,
    )
    built_in: bool = Field(
        default=False,
        description="Whether the plugin is a built-in plugin. This is used to indicate that the plugin is a built-in plugin that is included in the AIPerf package.",
    )
    class_type: type[Any] | None = Field(
        default=None,
        description="The class type of the plugin. This is lazy loaded when needed.",
    )
    entry_point: Any = Field(
        ...,
        description="The entry point of the plugin. This is the importlib.metadata.EntryPoint object.",
    )
    metadata: AIPerfPluginMetadata = Field(
        ...,
        description="The metadata of the plugin. This is the metadata of the plugin as defined in the pyproject.toml file.",
    )
