# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.comms.base import BaseCommunication, CommunicationFactory
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.hooks import AIPerfHook
from aiperf.common.mixins.hooks_mixin import HooksMixin, supports_hooks


@supports_hooks(AIPerfHook.ON_MESSAGE)
class CommunicationsMixin(HooksMixin):
    """Mixin that provides a communications instance."""

    def __init__(self, service_config: ServiceConfig, **kwargs) -> None:
        self.comms: BaseCommunication = CommunicationFactory.create_instance(
            service_config.comm_backend,
            config=service_config.comm_config,
        )

        super().__init__(**kwargs)
