# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import uuid
from abc import ABC

from aiperf.common.comms.base_comms import BaseCommunication
from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import CommAddress
from aiperf.common.exceptions import (
    ServiceError,
)
from aiperf.common.factories import CommunicationFactory
from aiperf.common.hooks import on_init
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.service.base_service_interface import BaseServiceInterface


class BaseService(AIPerfLifecycleMixin, BaseServiceInterface, ABC):
    """Base class for all AIPerf services, providing common functionality for
    communication, state management, and lifecycle operations.

    This class provides the foundation for implementing the various services of the
    AIPerf system. Some of the abstract methods are implemented here, while others
    are still required to be implemented by derived classes.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        self.service_id: str = (
            service_id or f"{self.service_type}_{uuid.uuid4().hex[:8]}"
        )
        self.service_config = service_config
        self.user_config = user_config

        super().__init__(id=self.service_id, **kwargs)

        self.debug(
            lambda: f"__init__ {self.service_type} service (id: {self.service_id})"
        )

        self.comms: BaseCommunication = CommunicationFactory.create_instance(
            self.service_config.comm_backend,
            config=self.service_config.comm_config,
        )
        self.sub_client = self.comms.create_sub_client(
            CommAddress.EVENT_BUS_PROXY_BACKEND
        )
        self.pub_client = self.comms.create_pub_client(
            CommAddress.EVENT_BUS_PROXY_FRONTEND
        )

        try:
            import setproctitle

            setproctitle.setproctitle(f"aiperf {self.service_id}")
        except Exception:
            # setproctitle is not available on all platforms, so we ignore the error
            self.debug("Failed to set process title, ignoring")

        self.debug("BaseService._init__ finished for %s", self.__class__.__name__)

    @on_init
    async def _init_comms(self) -> None:
        await self.comms.initialize()

    def _service_error(self, message: str) -> ServiceError:
        return ServiceError(
            message=message,
            service_type=self.service_type,
            service_id=self.service_id,
        )
