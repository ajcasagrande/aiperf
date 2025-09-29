# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pluggy

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.protocols import AIPerfUIProtocol

hookspec = pluggy.HookspecMarker("aiperf")


class AIPerfHookSpecs:
    @hookspec
    def create_ui(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs,
    ) -> type[AIPerfUIProtocol]:
        """Return a UI class type implementing AIPerfUIProtocol."""
        ...
