# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
from typing import cast

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    on_cleanup,
    on_configure,
    on_stop,
)
from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.messages import CommandMessage
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.types import ModelEndpointInfo
from aiperf.services.worker.inference_worker import InferenceWorkerMixin


@ServiceFactory.register(ServiceType.WORKER)
class Worker(BaseComponentService):
    """Worker is primarily responsible for converting the data into the appropriate
    format for the interface being used by the server. Also responsible for managing
    the conversation between turns.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ):
        super().__init__(service_config=service_config, service_id=service_id)

        self.logger.debug("Initializing worker process")
        self.user_config: UserConfig | None = None
        self.inference_worker: InferenceWorkerMixin | None = None
        self.inference_client: InferenceClientProtocol | None = None
        self.model_endpoint: ModelEndpointInfo | None = None

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

    @on_configure
    async def _configure(self, message: CommandMessage) -> None:
        self.logger.debug("Configuring worker process %s", self.service_id)
        self.user_config = cast(UserConfig, message.data)
        self.inference_client = self.create_inference_client(
            self.user_config.inference_client_config,
        )
        self.model_endpoint = self.user_config.model_endpoint_info

        self.inference_worker = InferenceWorkerMixin(
            worker_comms=self,
            inference_client=self.inference_client,
            model_endpoint=self.model_endpoint,
        )

    @on_stop
    async def _stop(self) -> None:
        self.logger.debug("Stopping worker process %s", self.service_id)

    @on_cleanup
    async def _cleanup(self) -> None:
        self.logger.debug("Cleaning up worker process %s", self.service_id)


def main() -> None:
    """Main entry point for the worker process."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(Worker)


if __name__ == "__main__":
    sys.exit(main())
