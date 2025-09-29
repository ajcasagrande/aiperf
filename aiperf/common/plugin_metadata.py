# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel


class AIPerfPluginMetadata(BaseModel):
    """Metadata for a plugin.
    This is used to identify the plugin in the plugin factory.
    """

    name: str
    version: str
    description: str | None = None
    author: str | None = None
    author_email: str | None = None
    url: str | None = None
