#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

"""
Demo script showing how to integrate worker dashboard with services.

This shows how a service (like SystemController) can receive worker health messages
and update a UI dashboard.
"""

import logging
import time
from typing import Any

from aiperf.common.config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic
from aiperf.common.hooks import on_init
from aiperf.common.models.messages import WorkerHealthMessage
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.ui.worker_dashboard import WorkerDashboard, WorkerDashboardMixin

logger = logging.getLogger(__name__)


class WorkerDashboardService(BaseComponentService, WorkerDashboardMixin):
    """Example service that integrates worker dashboard with communication system."""

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        logger.debug("Initializing worker dashboard service")

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.SYSTEM_CONTROLLER

    @on_init
    async def _initialize(self) -> None:
        """Initialize the service and subscribe to worker health messages."""
        logger.debug("Initializing worker dashboard service")

        # Subscribe to worker health messages
        try:
            await self.sub_client.subscribe(
                Topic.WORKER_HEALTH, self._on_worker_health_message
            )
            logger.debug("Subscribed to WORKER_HEALTH topic")
        except Exception as e:
            logger.error(f"Failed to subscribe to WORKER_HEALTH topic: {e}")

    async def _on_worker_health_message(self, message: WorkerHealthMessage) -> None:
        """Handle incoming worker health messages and update dashboard."""
        try:
            logger.debug(f"Received worker health message from {message.service_id}")

            # Update the mixin's health data and dashboard
            self.update_worker_health(message)

        except Exception as e:
            logger.error(f"Error handling worker health message: {e}")


class WorkerDashboardIntegrationExample:
    """Example showing how to integrate worker dashboard with textual UI."""

    def __init__(self) -> None:
        self.worker_dashboard = WorkerDashboard()
        self.worker_health_data: dict[str, WorkerHealthMessage] = {}

    def simulate_worker_health_messages(self) -> None:
        """Simulate worker health messages for demo purposes."""
        import random

        # Simulate 3 workers with different health states
        workers = ["worker_0", "worker_1", "worker_2"]

        for worker_id in workers:
            # Generate fake health data
            health_message = WorkerHealthMessage(
                service_id=worker_id,
                pid=random.randint(1000, 9999),
                cpu_usage=random.uniform(0, 100),
                memory_usage=random.uniform(100, 1000),
                uptime=random.uniform(60, 3600),
                completed_tasks=random.randint(0, 1000),
                failed_tasks=random.randint(0, 50),
                total_tasks=random.randint(100, 1050),
                timestamp_ns=time.time_ns(),
                net_connections=random.randint(0, 20),
                open_files=random.randint(10, 100),
                cpu_num=random.randint(0, 7),
                io_counters=None,
                cpu_times=None,
            )

            # Update dashboard with simulated data
            self.worker_dashboard.update_worker_health(health_message)
            self.worker_health_data[worker_id] = health_message

    def get_health_summary(self) -> dict[str, Any]:
        """Get a summary of worker health for logging/debugging."""
        summary = {
            "total_workers": len(self.worker_health_data),
            "workers": {},
        }

        for worker_id, health in self.worker_health_data.items():
            summary["workers"][worker_id] = {
                "status": "healthy"
                if health.cpu_usage < 90
                and health.failed_tasks / max(health.total_tasks, 1) < 0.1
                else "warning",
                "cpu_usage": f"{health.cpu_usage:.1f}%",
                "memory": f"{health.memory_usage:.1f} MiB",
                "tasks": f"{health.completed_tasks}/{health.total_tasks}",
                "errors": health.failed_tasks,
            }

        return summary


def example_usage():
    """Example showing how to use the worker dashboard components."""

    # Create an integration example
    example = WorkerDashboardIntegrationExample()

    # Simulate some worker health messages
    example.simulate_worker_health_messages()

    # Get health summary
    summary = example.get_health_summary()
    print("Worker Health Summary:")
    print(f"Total Workers: {summary['total_workers']}")

    for worker_id, worker_info in summary["workers"].items():
        print(
            f"  {worker_id}: {worker_info['status']} - CPU: {worker_info['cpu_usage']}, "
            f"Memory: {worker_info['memory']}, Tasks: {worker_info['tasks']}, "
            f"Errors: {worker_info['errors']}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    example_usage()
