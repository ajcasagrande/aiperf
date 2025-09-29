# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, ConfigDict, Field


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
