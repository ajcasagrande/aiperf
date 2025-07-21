# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing
from typing import Any

from pydantic import ConfigDict, Field

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import MessageType, ServiceType
from aiperf.common.hooks import (
    on_init,
    on_message,
    on_stop,
)
from aiperf.common.messages import (
    SpawnWorkersMessage,
    StopWorkersMessage,
    WorkerHealthMessage,
)
from aiperf.common.mixins import AIPerfMessageHandlerMixin
from aiperf.common.models import AIPerfBaseModel
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.service.base_service import ServiceFactory


class WorkerProcessInfo(AIPerfBaseModel):
    """Information about a worker process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    worker_id: str = Field(..., description="ID of the worker process")
    process: Any = Field(None, description="Process object or task")


@ServiceFactory.register(ServiceType.WORKER_MANAGER)
class WorkerManager(BaseComponentService, AIPerfMessageHandlerMixin):
    """
    The WorkerManager service is primary responsibility to manage the worker processes.
    It will spawn the workers, monitor their health, and stop them when the service is stopped.
    In the future it will also be responsible for the auto-scaling of the workers.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )
        self.trace("WorkerManager.__init__")
        self.workers: dict[str, WorkerProcessInfo] = {}
        self.worker_health: dict[str, WorkerHealthMessage] = {}

        self.cpu_count = multiprocessing.cpu_count()
        self.debug("Detected %s CPU cores/threads", self.cpu_count)

        self.max_concurrency = self.user_config.loadgen.concurrency
        self.max_workers = self.service_config.workers.max
        if self.max_workers is None:
            # Default to the number of CPU cores - 1
            self.max_workers = self.cpu_count - 1

        # Cap the worker count to the max concurrency + 1, but only if the user is in concurrency mode.
        if self.max_concurrency > 1:
            self.max_workers = min(
                self.max_concurrency + 1,
                self.max_workers,
            )

        # Ensure we have at least the min workers
        self.max_workers = max(
            self.max_workers,
            self.service_config.workers.min or 0,
        )
        self.initial_workers = self.max_workers

    @on_init
    async def _initialize(self) -> None:
        """Initialize worker manager-specific components."""
        self.debug("WorkerManager initializing")

        await self.pub_client.publish(
            SpawnWorkersMessage(
                service_id=self.service_id,
                worker_count=self.initial_workers,
            ),
        )

    @on_message(MessageType.WORKER_HEALTH)
    async def _on_worker_health(self, message: WorkerHealthMessage) -> None:
        self.debug("Received worker health message: %s", message)
        self.worker_health[message.service_id] = message

    @on_stop
    async def _stop(self) -> None:
        self.debug("WorkerManager stopping")

        await self.pub_client.publish(
            StopWorkersMessage(
                service_id=self.service_id,
                worker_count=len(self.workers),
            ),
        )


def main() -> None:
    bootstrap_and_run_service(WorkerManager)


if __name__ == "__main__":
    main()
