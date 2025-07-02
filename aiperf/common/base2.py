#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging
import uuid
from typing import ClassVar

from aiperf.common.comms.base import (
    BaseCommunication,
    PubClient,
    SubClient,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ClientAddressType, MessageType, ServiceType
from aiperf.common.factories import CommunicationFactory
from aiperf.common.hooks import (
    AIPerfLifecycleMixin,
    AIPerfProfileMixin,
    on_cleanup,
    on_init,
)


class AIPerfServiceMixin(AIPerfLifecycleMixin):
    service_type: ClassVar[ServiceType]

    def __init__(self, service_config: ServiceConfig, service_id: str | None = None):
        super().__init__()
        self.service_config = service_config
        self.service_id = service_id or f"{self.service_type}_{uuid.uuid4().hex[:8]}"
        self.logger = logging.getLogger(self.service_id)
        self.logger.debug(
            f"Initializing {self.service_type} service (id: {self.service_id})"
        )
        self.comms: BaseCommunication = CommunicationFactory.create_instance(
            self.service_config.comm_backend,
            config=self.service_config.comm_config,
        )
        self.sub_client: SubClient = self.comms.create_sub_client(
            ClientAddressType.SERVICE_PUB_SUB_BACKEND,
        )
        self.pub_client: PubClient = self.comms.create_pub_client(
            ClientAddressType.SERVICE_PUB_SUB_FRONTEND,
        )

    @on_init
    async def initialize(self):
        """Initialize the service."""
        await self.comms.initialize()

    @on_cleanup
    async def cleanup(self):
        """Cleanup the service."""
        await self.comms.shutdown()


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
