# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceRunType
from aiperf.common.factories import ServiceManagerFactory
from aiperf.common.types import ServiceTypeT
from aiperf.services.system_controller.base_service_manager import BaseServiceManager


class ServiceKubernetesRunInfo(BaseModel):
    """Information about a service running in a Kubernetes pod."""

    pod_name: str
    node_name: str
    namespace: str


@ServiceManagerFactory.register(ServiceRunType.KUBERNETES)
class KubernetesServiceManager(BaseServiceManager):
    """
    Service Manager for starting and stopping services in a Kubernetes cluster.
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str,
        **kwargs,
    ):
        super().__init__(
            required_services, service_config, user_config, service_id, **kwargs
        )

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        """Run a service as a Kubernetes pod."""
        self.logger.debug(f"Running service {service_type} as a Kubernetes pod")
        # TODO: Implement Kubernetes
        raise NotImplementedError(
            "KubernetesServiceManager.run_service not implemented"
        )

    async def shutdown_all_services(self) -> list[BaseException | None]:
        """Stop all required services as Kubernetes pods."""
        self.logger.debug("Stopping all required services as Kubernetes pods")
        # TODO: Implement Kubernetes
        raise NotImplementedError(
            "KubernetesServiceManager.stop_all_services not implemented"
        )

    async def kill_all_services(self) -> list[BaseException | None]:
        """Kill all required services as Kubernetes pods."""
        self.logger.debug("Killing all required services as Kubernetes pods")
        # TODO: Implement Kubernetes
        raise NotImplementedError(
            "KubernetesServiceManager.kill_all_services not implemented"
        )
