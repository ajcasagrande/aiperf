# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging

from aiperf.common.health_models import WorkerHealthMessage, WorkerHealthSummary


class HealthTracker:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.worker_health: dict[str, WorkerHealthMessage] = {}

    def update_worker_health(self, worker_id: str, health: WorkerHealthMessage) -> None:
        self.worker_health[worker_id] = health

    def get_worker_health(self, worker_id: str) -> WorkerHealthMessage | None:
        return self.worker_health.get(worker_id)

    def get_worker_health_summary(self) -> dict[str, WorkerHealthMessage]:
        return self.worker_health

    def total_summary(self) -> WorkerHealthSummary:
        return WorkerHealthSummary(
            workers=[health for health in self.worker_health.values()],
        )
