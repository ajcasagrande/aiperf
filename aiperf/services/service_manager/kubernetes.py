# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config import ServiceConfig
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_REGISTRATION_SECONDS,
    DEFAULT_WAIT_FOR_START_SECONDS,
    DEFAULT_WAIT_FOR_STOP_SECONDS,
)
from aiperf.common.enums import ServiceType
from aiperf.common.messages import BaseServiceMessage
from aiperf.common.models import AIPerfBaseModel
from aiperf.services.service_manager.base import BaseServiceManager
from aiperf.services.service_registry import GlobalServiceRegistry


class ServiceKubernetesRunInfo(AIPerfBaseModel):
    """Information about a service running in a Kubernetes pod."""

    pod_name: str
    node_name: str
    namespace: str


class KubernetesServiceManager(BaseServiceManager):
    """
    Service Manager for starting and stopping services in a Kubernetes cluster.
    """

    def __init__(
        self,
        required_services: dict[ServiceType, int],
        config: ServiceConfig,
    ):
        super().__init__(required_services, config)
        self.registry = GlobalServiceRegistry

    async def run_all_services(self) -> None:
        """Initialize all required services as Kubernetes pods."""
        self.debug("Initializing all required services as Kubernetes pods")
        # TODO: Implement Kubernetes
        raise NotImplementedError(
            "KubernetesServiceManager.initialize_all_services not implemented"
        )

    async def shutdown_all_services(self) -> None:
        """Stop all required services as Kubernetes pods."""
        self.debug("Stopping all required services as Kubernetes pods")
        # TODO: Implement Kubernetes
        raise NotImplementedError(
            "KubernetesServiceManager.stop_all_services not implemented"
        )

    async def kill_all_services(self) -> None:
        """Kill all required services as Kubernetes pods."""
        self.debug("Killing all required services as Kubernetes pods")
        # TODO: Implement Kubernetes
        raise NotImplementedError(
            "KubernetesServiceManager.kill_all_services not implemented"
        )

    async def wait_for_all_services_registration(
        self, timeout_seconds: float = DEFAULT_WAIT_FOR_REGISTRATION_SECONDS
    ) -> None:
        """Wait for all required services to be registered in Kubernetes."""
        self.debug("Waiting for all required services to be registered in Kubernetes")
        # TODO: Implement Kubernetes
        raise NotImplementedError(
            "KubernetesServiceManager.wait_for_all_services_registration not implemented"
        )

    async def wait_for_all_services_to_start(
        self, timeout_seconds: float = DEFAULT_WAIT_FOR_START_SECONDS
    ) -> None:
        """Wait for all required services to be started in Kubernetes."""
        self.debug("Waiting for all required services to be started in Kubernetes")
        # TODO: Implement Kubernetes
        raise NotImplementedError(
            "KubernetesServiceManager.wait_for_all_services_to_start not implemented"
        )

    async def wait_for_all_services_to_stop(
        self, timeout_seconds: float = DEFAULT_WAIT_FOR_STOP_SECONDS
    ) -> None:
        """Wait for all required services to be stopped in Kubernetes."""
        self.debug("Waiting for all required services to be stopped in Kubernetes")
        # TODO: Implement Kubernetes
        raise NotImplementedError(
            "KubernetesServiceManager.wait_for_all_services_to_stop not implemented"
        )

    async def on_message(self, message: BaseServiceMessage) -> None:
        raise NotImplementedError
