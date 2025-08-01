# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from collections.abc import AsyncIterator, Iterator

from aiperf.common.models import ProcessHealth


class HealthTracker:
    def __init__(self):
        self.process_health: dict[str, ProcessHealth] = {}

    def __contains__(self, service_id: str) -> bool:
        return service_id in self.process_health

    def __getitem__(self, service_id: str) -> ProcessHealth:
        return self.process_health[service_id]

    def __setitem__(self, service_id: str, health: ProcessHealth) -> None:
        self.process_health[service_id] = health

    def __len__(self) -> int:
        return len(self.process_health)

    def __iter__(self) -> Iterator[tuple[str, ProcessHealth]]:
        return iter(self.process_health.items())

    async def __aiter__(self) -> AsyncIterator[tuple[str, ProcessHealth]]:
        for service_id, health in self.process_health.items():
            yield (service_id, health)
