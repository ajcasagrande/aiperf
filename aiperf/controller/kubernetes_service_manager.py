# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio

from pydantic import BaseModel

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    DEFAULT_SERVICE_START_TIMEOUT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.common.factories import ServiceManagerFactory
from aiperf.common.models import ServiceRunInfo
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.types import ServiceTypeT
from aiperf.controller.base_service_manager import BaseServiceManager
from aiperf.kubernetes.resource_manager import KubernetesResourceManager
from aiperf.kubernetes.templates import PodTemplateBuilder


class ServiceKubernetesRunInfo(BaseModel):
    """Information about a service running in a Kubernetes pod."""

    pod_name: str
    node_name: str | None = None
    namespace: str


@implements_protocol(ServiceManagerProtocol)
@ServiceManagerFactory.register(ServiceRunType.KUBERNETES)
class KubernetesServiceManager(BaseServiceManager):
    """Service Manager for starting and stopping services in a Kubernetes cluster."""

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        resource_manager: KubernetesResourceManager | None = None,
        template_builder: PodTemplateBuilder | None = None,
        config_map_name: str | None = None,
        **kwargs,
    ):
        super().__init__(required_services, service_config, user_config, **kwargs)

        # When running inside a K8s pod, create our own resource manager and template builder
        if resource_manager is None:
            import os

            namespace = os.getenv("AIPERF_NAMESPACE", "default")
            self.resource_manager = KubernetesResourceManager(namespace=namespace)
        else:
            self.resource_manager = resource_manager

        if template_builder is None:
            import os

            namespace = os.getenv("AIPERF_NAMESPACE", "default")
            svc_name = os.getenv(
                "AIPERF_SYSTEM_CONTROLLER_SERVICE", "aiperf-system-controller"
            )
            # When running inside a pod, use the same image as the current pod
            image = os.getenv("AIPERF_IMAGE", service_config.kubernetes.image)
            self.template_builder = PodTemplateBuilder(
                namespace=namespace,
                image=image,
                image_pull_policy="Never",
                service_account=service_config.kubernetes.service_account,
                system_controller_service=svc_name,
            )
        else:
            self.template_builder = template_builder

        if config_map_name is None:
            import os

            self.config_map_name = os.getenv("AIPERF_CONFIG_MAP", "aiperf-config")
        else:
            self.config_map_name = config_map_name

        self.pod_run_info: dict[str, ServiceKubernetesRunInfo] = {}

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        """Run a service as Kubernetes pod(s)."""
        self.logger.info(f"Deploying {num_replicas} pod(s) for {service_type}")

        for i in range(num_replicas):
            # K8s names must be DNS-compliant (lowercase, hyphens, no underscores)
            base_name = service_type.value.replace("_", "-")
            service_id = f"{base_name}-{i}" if num_replicas > 1 else base_name

            # Get resource requirements
            cpu, memory = self._get_resource_requirements(service_type)

            # Build pod spec
            pod_spec = self.template_builder.build_pod_spec(
                service_type=service_type,
                service_id=service_id,
                config_map_name=self.config_map_name,
                cpu=cpu,
                memory=memory,
            )

            # Create pod
            pod_name = await self.resource_manager.create_pod(pod_spec)

            # Track pod
            self.pod_run_info[service_id] = ServiceKubernetesRunInfo(
                pod_name=pod_name,
                namespace=self.resource_manager.namespace,
            )

            # Wait for pod to be ready
            await self.resource_manager.wait_for_pod_ready(pod_name, timeout=120)

    def _get_resource_requirements(self, service_type: ServiceTypeT) -> tuple[str, str]:
        """Get CPU and memory requirements for service type."""
        # Worker pods get custom resources if configured
        if service_type == ServiceType.WORKER:
            return (
                self.service_config.kubernetes.worker_cpu,
                self.service_config.kubernetes.worker_memory,
            )

        # Scalable services get moderate resources
        if service_type == ServiceType.RECORD_PROCESSOR:
            return "2", "2Gi"

        # Singleton services get minimal resources
        return "1", "1Gi"

    async def stop_service(
        self, service_type: ServiceTypeT, service_id: str | None = None
    ) -> list[BaseException | None]:
        """Stop service pod(s)."""
        self.logger.debug(f"Stopping service {service_type}")
        errors: list[BaseException | None] = []

        # Find matching pods
        pods_to_stop = []
        if service_id:
            if service_id in self.pod_run_info:
                pods_to_stop.append(service_id)
        else:
            # Stop all pods of this type
            for sid, info in self.pod_run_info.items():
                if sid.startswith(service_type.value):
                    pods_to_stop.append(sid)

        # Delete pods
        for sid in pods_to_stop:
            try:
                info = self.pod_run_info[sid]
                await self.resource_manager.delete_pod(info.pod_name)
                del self.pod_run_info[sid]
            except Exception as e:
                errors.append(e)

        return errors

    async def shutdown_all_services(self) -> list[BaseException | None]:
        """Stop all service pods."""
        self.logger.info("Shutting down all services")
        errors: list[BaseException | None] = []

        for service_id, info in list(self.pod_run_info.items()):
            try:
                await self.resource_manager.delete_pod(info.pod_name)
            except Exception as e:
                errors.append(e)

        self.pod_run_info.clear()
        return errors

    async def kill_all_services(self) -> list[BaseException | None]:
        """Kill all service pods (same as shutdown for K8s)."""
        return await self.shutdown_all_services()

    async def wait_for_all_services_registration(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None:
        """Wait for all required services to register via message bus."""
        # Services register by sending RegisterServiceCommand via ZMQ
        # This is handled by the SystemController's message handler
        # We just need to wait for the service_map to be populated

        import time

        start_time = time.time()
        last_warning_time = 0

        while time.time() - start_time < timeout_seconds:
            if stop_event.is_set():
                raise asyncio.CancelledError("Stop event set during service registration")

            # Check if all required services are registered
            all_registered = True
            missing = []
            for service_type, count in self.required_services.items():
                registered = len(self.service_map.get(service_type, []))
                if registered < count:
                    all_registered = False
                    missing.append(f"{service_type.value}({registered}/{count})")

            if all_registered:
                self.logger.info("✓ All required services registered successfully")
                return

            # Log warning every 5 seconds
            elapsed = time.time() - start_time
            if elapsed - last_warning_time >= 5:
                self.logger.warning(
                    f"Waiting for service registration [{int(elapsed)}s/{int(timeout_seconds)}s]: "
                    f"Missing: {', '.join(missing)}"
                )
                last_warning_time = elapsed

            await asyncio.sleep(1)

        # Log which services are missing
        missing_services = []
        for service_type, count in self.required_services.items():
            registered = len(self.service_map.get(service_type, []))
            if registered < count:
                missing_services.append(f"{service_type.value} ({registered}/{count})")

        self.logger.error(f"Missing services: {', '.join(missing_services)}")

        raise TimeoutError(
            f"Not all services registered within {timeout_seconds} seconds"
        )

    async def wait_for_all_services_start(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_START_TIMEOUT,
    ) -> None:
        """Wait for all required services to start."""
        # In K8s mode, we consider services started once pods are running
        # and they've registered with the system controller
        self.logger.info("All services started (pods running and registered)")
