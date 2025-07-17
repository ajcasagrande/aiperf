#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
# SPDX-License-Identifier: Apache-2.0

import asyncio
from typing import Protocol, runtime_checkable

from aiperf.common.comms.base import PubClientProtocol
from aiperf.common.enums import CreditPhase
from aiperf.common.hooks import aiperf_task
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.mixins import (
    AIPerfLoggerMixinProtocol,
    ProcessHealthMixin,
    ProcessHealthMixinProtocol,
)
from aiperf.common.models import WorkerPhaseTaskStats


@runtime_checkable
class WorkerHealthMixinRequirements(
    AIPerfLoggerMixinProtocol, ProcessHealthMixinProtocol, Protocol
):
    """WorkerHealthMixinRequirements is a protocol that provides the requirements needed for the WorkerHealthMixin."""

    health_check_interval: int
    service_id: str
    pub_client: PubClientProtocol
    task_stats: dict[CreditPhase, WorkerPhaseTaskStats]


class WorkerHealthMixin(ProcessHealthMixin, WorkerHealthMixinRequirements):
    def __init__(self, **kwargs):
        if not isinstance(self, WorkerHealthMixinRequirements):
            raise ValueError(
                "WorkerHealthMixin must be used in a class that conforms to WorkerHealthMixinRequirements"
            )

    @aiperf_task
    async def _health_check_task(self) -> None:
        """Task to report the health of the worker to the worker manager."""
        while True:
            try:
                health_message = self.create_health_message()
                await self.pub_client.publish(health_message)
            except Exception as e:
                self.exception(f"Error reporting health: {e}")
            except asyncio.CancelledError:
                self.debug("Health check task cancelled")
                break

            await asyncio.sleep(self.health_check_interval)

    def create_health_message(self) -> WorkerHealthMessage:
        return WorkerHealthMessage(
            service_id=self.service_id,
            process=self.get_process_health(),
            task_stats=self.task_stats,
        )
