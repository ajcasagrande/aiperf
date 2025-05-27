#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
################################################################################
# Backend Client Mixins
################################################################################


from typing import Generic

from aiperf.common.models import BackendClientConfig
from aiperf.common.types import ConfigT

__all__ = [
    "BackendClientConfigMixin",
]


class BackendClientConfigMixin(Generic[ConfigT]):
    """Mixin for backend client configuration."""

    def __init__(self, cfg: BackendClientConfig[ConfigT]) -> None:
        """Create a new backend client based on the provided configuration."""
        self._client_config = cfg.client_config

    @property
    def client_config(self) -> ConfigT:
        """Get the client configuration."""
        return self._client_config
