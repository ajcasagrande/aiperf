# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from collections.abc import AsyncIterator, Iterator

from aiperf.common.enums.message_enums import MessageType
from aiperf.common.hooks import on_message
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.mixins.message_bus_mixin import MessageBusClientMixin


class HealthTracker(MessageBusClientMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.worker_health: dict[str, WorkerHealthMessage] = {}

    @on_message(MessageType.WORKER_HEALTH)
    async def _on_worker_health(self, message: WorkerHealthMessage) -> None:
        """Handle the worker health message."""
        self.worker_health[message.service_id] = message

    def __contains__(self, worker_id: str) -> bool:
        return worker_id in self.worker_health

    def __getitem__(self, worker_id: str) -> WorkerHealthMessage:
        return self.worker_health[worker_id]

    def __setitem__(self, worker_id: str, health: WorkerHealthMessage) -> None:
        self.worker_health[worker_id] = health

    def __len__(self) -> int:
        return len(self.worker_health)

    def __iter__(self) -> Iterator[tuple[str, WorkerHealthMessage]]:
        return iter(self.worker_health.items())

    async def __aiter__(self) -> AsyncIterator[tuple[str, WorkerHealthMessage]]:
        for worker_id, health in self.worker_health.items():
            yield (worker_id, health)
