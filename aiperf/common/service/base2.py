# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import uuid
from typing import ClassVar

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import MessageType, ServiceType
from aiperf.common.hooks import (
    on_cleanup,
    on_init,
)
from aiperf.common.mixins import (
    AIPerfLifecycleMixin,
    AIPerfProfileMixin,
    EventBusClientMixin,
)


class AIPerfServiceMixin(AIPerfLifecycleMixin, EventBusClientMixin):
    service_type: ClassVar[ServiceType]

    def __init__(self, service_config: ServiceConfig, service_id: str | None = None):
        super().__init__(service_config)
        self.service_config = service_config
        self.service_id = service_id or f"{self.service_type}_{uuid.uuid4().hex[:8]}"
        self.logger = logging.getLogger(self.service_id)
        self.logger.debug(
            f"Initializing {self.service_type} service (id: {self.service_id})"
        )

    @on_init
    async def initialize(self):
        """Initialize the service."""
        await super().initialize()

    @on_cleanup
    async def cleanup(self):
        """Cleanup the service."""
        await super().cleanup()


class AIPerfComponentServiceMixin(AIPerfProfileMixin, AIPerfServiceMixin):
    """Mixin to add component service support to a class. It abstracts away the details of the
    :class:`AIPerfComponentService` and provides a simple interface for registering and running components."""

    def __init__(self, service_config: ServiceConfig, service_id: str | None = None):
        super().__init__(service_config, service_id)

    @on_init
    async def initialize(self):
        """Initialize the service."""
        await super().initialize()
        await self.sub_client.subscribe(
            message_type=MessageType.COMMAND,
            callback=self._on_command,
        )

    @on_cleanup
    async def cleanup(self):
        """Cleanup the service."""
        await super().cleanup()
