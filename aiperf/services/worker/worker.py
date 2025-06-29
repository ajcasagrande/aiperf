# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import sys
from typing import cast

from aiperf.common.comms.base import BaseCommunication
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType
from aiperf.common.factories import (
    CommunicationFactory,
    ServiceFactory,
)
from aiperf.common.hooks import (
    aiperf_task,
    on_cleanup,
    on_configure,
    on_init,
    on_stop,
)
from aiperf.common.models.messages import (
    CommandMessage,
)
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.services.worker.universal import UniversalWorker


@ServiceFactory.register(ServiceType.WORKER)
class Worker(BaseComponentService, UniversalWorker):
    """Worker is primarily responsible for converting the data into the appropriate
    format for the interface being used by the server. Also responsible for managing
    the conversation between turns.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str,
    ) -> None:
        super().__init__(
            service_config=service_config,
            service_id=service_id,
        )
        UniversalWorker.__init__(
            self,
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )
        self._zmq_comms: BaseCommunication | None = None

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

    @on_init
    async def _initialize(self) -> None:
        """Initialize worker-specific components."""
        self._zmq_comms = CommunicationFactory.create_instance(
            self.service_config.comm_backend,
            config=self.service_config.comm_config,
        )
        await self._zmq_comms.initialize()
        await UniversalWorker.do_initialize(self, zmq_comms=self._zmq_comms)

    @aiperf_task
    async def _health_check_task(self) -> None:
        """Health check task."""
        while not self.stop_event.is_set():
            try:
                health_message = self._health_check()
                await self.pub_client.publish(health_message)
            except Exception as e:
                self.logger.error("Error reporting health: %s", e)
            await asyncio.sleep(self.health_check_interval)


@ServiceFactory.register(ServiceType.MULTI_WORKER_PROCESS)
class MultiWorkerProcess(BaseComponentService):
    """MultiWorkerProcess is a process that runs multiple workers as concurrent tasks on the event loop."""

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ):
        super().__init__(service_config=service_config, service_id=service_id)

        self.logger.debug("Initializing worker process")
        self.workers: list[Worker] = []
        self.tasks: list[asyncio.Task] = []
        self.worker_count = int(os.getenv("AIPERF_TASKS_PER_WORKER", 1))
        self.user_config: UserConfig | None = None
        self.next_worker_id = 0
        self.worker: UniversalWorker

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.MULTI_WORKER_PROCESS

    @on_configure
    async def _configure(self, message: CommandMessage) -> None:
        self.logger.debug("Configuring multi-worker process %s", self.service_id)
        self.worker = UniversalWorker(
            service_config=self.service_config,
            user_config=cast(UserConfig, message.data),
            service_id=f"{self.service_id}",
        )
        await self.worker.do_initialize(zmq_comms=self.comms)

    @on_stop
    async def _stop(self) -> None:
        self.logger.debug("Stopping multi-worker process %s", self.service_id)
        await self.worker.do_shutdown()

    @on_cleanup
    async def _cleanup(self) -> None:
        self.logger.debug("Cleaning up multi-worker process %s", self.service_id)
        await asyncio.gather(*self.tasks)


def main() -> None:
    """Main entry point for the worker process."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(MultiWorkerProcess)


if __name__ == "__main__":
    sys.exit(main())
