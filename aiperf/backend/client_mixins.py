#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
################################################################################
# Backend Client Mixins
################################################################################


from typing import Generic

from aiperf.common.types import ConfigT

__all__ = [
    "BackendClientConfigMixin",
]


class BackendClientConfigMixin(Generic[ConfigT]):
    """Mixin for backend client configuration."""

    def __init__(self, client_config: ConfigT) -> None:
        """Create a new backend client based on the provided configuration."""
        self._client_config = client_config

    @property
    def client_config(self) -> ConfigT:
        """Get the client configuration."""
        return self._client_config
