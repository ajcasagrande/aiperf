# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import uuid

from pydantic import BaseModel, Field

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    DEFAULT_SERVICE_START_TIMEOUT,
    TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceRegistrationStatus, ServiceRunType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.factories import ServiceFactory, ServiceManagerFactory
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.types import ServiceTypeT
from aiperf.controller.base_service_manager import BaseServiceManager
from aiperf.controller.k8s_utils import KubernetesUtils, PodPhase


class ServiceKubernetesRunInfo(BaseModel):
    """Information about a service running in a Kubernetes pod."""

    pod_name: str = Field(..., description="Kubernetes pod name")
    service_type: ServiceTypeT = Field(
        ...,
        description="Type of service running in the pod",
    )
    service_id: str = Field(
        ...,
        description="ID of the service running in the pod",
    )
    namespace: str = Field(..., description="Kubernetes namespace")
    node_name: str | None = Field(
        default=None, description="Node the pod is running on"
    )
    pod_ip: str | None = Field(default=None, description="Pod IP address")
    labels: dict[str, str] = Field(default_factory=dict, description="Pod labels")
    phase: PodPhase | None = Field(default=None, description="Current pod phase")


@implements_protocol(ServiceManagerProtocol)
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
        k8s_namespace: str = "default",
        kubeconfig_path: str | None = None,
        in_cluster: bool = False,
        docker_image: str | None = None,
        image_pull_policy: str = "IfNotPresent",
        service_account: str | None = None,
        node_selector: dict[str, str] | None = None,
        resource_requests: dict[str, str] | None = None,
        resource_limits: dict[str, str] | None = None,
        pod_labels: dict[str, str] | None = None,
        pod_annotations: dict[str, str] | None = None,
        python_executable: str = "python",
        **kwargs,
    ):
        """Initialize Kubernetes Service Manager.

        Args:
            required_services: Services to run and their replica counts
            service_config: Service configuration
            user_config: User configuration
            k8s_namespace: Kubernetes namespace to use
            kubeconfig_path: Path to kubeconfig file
            in_cluster: Whether running inside a Kubernetes cluster
            docker_image: Docker image to use for service pods
            image_pull_policy: Image pull policy (Always, IfNotPresent, Never)
            service_account: Service account for pods
            node_selector: Node selector for pod placement
            resource_requests: Resource requests for containers
            resource_limits: Resource limits for containers
            pod_labels: Additional labels for pods
            pod_annotations: Additional annotations for pods
            python_executable: Python executable to use in containers
            **kwargs: Additional arguments
        """
        super().__init__(required_services, service_config, user_config, **kwargs)

        # Kubernetes configuration
        self.k8s_namespace = k8s_namespace
        self.kubeconfig_path = kubeconfig_path
        self.in_cluster = in_cluster

        # Container configuration
        if not docker_image:
            raise AIPerfError("docker_image is required for Kubernetes deployment")
        self.docker_image = docker_image
        self.image_pull_policy = image_pull_policy
        self.service_account = service_account
        self.node_selector = node_selector or {}

        # Resource configuration
        self.resource_requests = resource_requests or {}
        self.resource_limits = resource_limits or {}

        # Pod metadata
        self.pod_labels = pod_labels or {}
        self.pod_annotations = pod_annotations or {}

        # Python configuration
        self.python_executable = python_executable

        # Kubernetes utilities
        self.k8s_utils = KubernetesUtils(
            namespace=self.k8s_namespace,
            kubeconfig_path=self.kubeconfig_path,
            in_cluster=self.in_cluster,
        )

        # Pod tracking
        self.kubernetes_pods: list[ServiceKubernetesRunInfo] = []

    async def _start_service_manager(self) -> None:
        """Override to check Kubernetes availability before starting."""
        # Initialize Kubernetes client
        if not await self.k8s_utils.is_kubernetes_available():
            raise AIPerfError("Kubernetes is not available or accessible")

        await self.k8s_utils.initialize()
        self.info("Kubernetes client initialized successfully")
        await super()._start_service_manager()

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        """Run a service with the given number of replicas as Kubernetes pods.

        Args:
            service_type: Type of service to run
            num_replicas: Number of replicas to start
        """
        self.debug(
            f"Starting {num_replicas} replicas of {service_type} as Kubernetes pods"
        )

        service_class = ServiceFactory.get_class_from_type(service_type)

        for replica_num in range(num_replicas):
            service_id = f"{service_type}-{uuid.uuid4().hex[:8]}"
            pod_name = f"aiperf-{service_type}-{replica_num}-{uuid.uuid4().hex[:8]}"

            # Create labels for pod
            labels = {
                "app": "aiperf",
                "component": service_type,
                "service-id": service_id,
                **self.pod_labels,
            }

            # Create environment variables
            env_vars = {
                "AIPERF_SERVICE_ID": service_id,
                "AIPERF_SERVICE_TYPE": service_type,
            }

            # Create the command to run the service
            command = self._create_service_command(
                service_class=service_class.__name__,
                service_id=service_id,
                service_type=service_type,
            )

            # Prepare resource requirements
            resources = {}
            if self.resource_requests:
                resources["requests"] = self.resource_requests
            if self.resource_limits:
                resources["limits"] = self.resource_limits

            try:
                pod_info = await self.k8s_utils.create_pod(
                    name=pod_name,
                    image=self.docker_image,
                    command=command,
                    env_vars=env_vars,
                    resources=resources if resources else None,
                    node_selector=self.node_selector,
                    service_account=self.service_account,
                    restart_policy="Never",  # Services should not restart automatically
                    labels=labels,
                    annotations=self.pod_annotations,
                )

                self.debug(
                    f"Created pod {pod_name} for {service_type} (service_id: {service_id})"
                )

                # Store pod information
                k8s_info = ServiceKubernetesRunInfo(
                    pod_name=pod_name,
                    service_type=service_type,
                    service_id=service_id,
                    namespace=pod_info.namespace,
                    node_name=pod_info.node_name,
                    pod_ip=pod_info.pod_ip,
                    labels=labels,
                    phase=pod_info.phase,
                )

                self.kubernetes_pods.append(k8s_info)

                self.info(f"Started {service_type} as Kubernetes pod {pod_name}")

            except Exception as e:
                self.error(f"Failed to start {service_type} as Kubernetes pod: {e}")
                raise

    def _create_service_command(
        self,
        service_class: str,
        service_id: str,
        service_type: ServiceTypeT,
    ) -> list[str]:
        """Create the command to run a service.

        This method creates a command that runs the service using its main() function.
        Each service module has a main() function that calls bootstrap_and_run_service.

        Args:
            service_class: Name of the service class (not used directly)
            service_id: Unique service ID
            service_type: Type of service

        Returns:
            Command list to execute
        """
        # Map service types to their corresponding module paths
        service_module_map = {
            "system_controller": "aiperf.controller.system_controller",
            "dataset_manager": "aiperf.dataset.dataset_manager",
            "timing_manager": "aiperf.timing.timing_manager",
            "record_processor": "aiperf.records.record_processor_service",
            "records_manager": "aiperf.records.records_manager",
            "worker_manager": "aiperf.workers.worker_manager",
            "worker": "aiperf.workers.worker",
        }

        module_path = service_module_map.get(service_type)
        if not module_path:
            raise AIPerfError(f"Unknown service type: {service_type}")

        # Return command as list for Kubernetes
        return [self.python_executable, "-m", module_path]

    async def stop_service(
        self, service_type: ServiceTypeT, service_id: str | None = None
    ) -> list[BaseException | None]:
        """Stop Kubernetes pods for the specified service type and optionally service ID.

        Args:
            service_type: Type of service to stop
            service_id: Specific service ID to stop (if None, stops all of this type)

        Returns:
            List of exceptions (if any) from stop operations
        """
        self.debug(f"Stopping {service_type} Kubernetes pod(s) with id: {service_id}")

        pods_to_stop = [
            pod
            for pod in self.kubernetes_pods
            if pod.service_type == service_type
            and (service_id is None or pod.service_id == service_id)
        ]

        results = []
        for pod in pods_to_stop:
            try:
                success = await self.k8s_utils.delete_pod(pod.pod_name)
                if success:
                    self.debug(
                        f"Deleted Kubernetes pod {pod.pod_name} for {service_type}"
                    )
                    # Wait for pod to actually be deleted
                    try:
                        await self.k8s_utils.wait_for_pod_phase(
                            pod.pod_name,
                            [PodPhase.SUCCEEDED, PodPhase.FAILED],
                            timeout_seconds=TASK_CANCEL_TIMEOUT_SHORT,
                        )
                        self.debug(f"Pod {pod.pod_name} successfully terminated")
                    except Exception as e:
                        self.warning(
                            f"Error waiting for pod {pod.pod_name} termination: {e}"
                        )

                    # Remove from our tracking list
                    self.kubernetes_pods.remove(pod)
                    results.append(None)
                else:
                    error = AIPerfError(
                        f"Failed to delete Kubernetes pod {pod.pod_name}"
                    )
                    self.error(str(error))
                    results.append(error)
            except Exception as e:
                self.error(f"Error stopping Kubernetes pod {pod.pod_name}: {e}")
                results.append(e)

        return results

    async def shutdown_all_services(self) -> list[BaseException | None]:
        """Stop all Kubernetes pods."""
        self.debug("Stopping all Kubernetes pods")

        results = []
        pods_to_delete = self.kubernetes_pods.copy()

        # Delete all pods in parallel
        delete_tasks = []
        for pod in pods_to_delete:
            task = asyncio.create_task(self._delete_pod_with_wait(pod))
            delete_tasks.append(task)

        if delete_tasks:
            results = await asyncio.gather(*delete_tasks, return_exceptions=True)

        # Clear our pod list
        self.kubernetes_pods.clear()
        return results

    async def kill_all_services(self) -> list[BaseException | None]:
        """Force kill all Kubernetes pods."""
        self.debug("Force killing all Kubernetes pods")

        results = []
        pods_to_delete = self.kubernetes_pods.copy()

        # Force delete all pods in parallel
        delete_tasks = []
        for pod in pods_to_delete:
            task = asyncio.create_task(
                self._delete_pod_with_wait(pod, grace_period_seconds=0, force=True)
            )
            delete_tasks.append(task)

        if delete_tasks:
            results = await asyncio.gather(*delete_tasks, return_exceptions=True)

        # Clear our pod list
        self.kubernetes_pods.clear()
        return results

    async def _delete_pod_with_wait(
        self,
        pod: ServiceKubernetesRunInfo,
        grace_period_seconds: int | None = None,
        force: bool = False,
    ) -> Exception | None:
        """Delete a pod and wait for it to finish.

        Args:
            pod: Pod information
            grace_period_seconds: Graceful termination period
            force: Force deletion

        Returns:
            Exception if deletion failed, None otherwise
        """
        try:
            success = await self.k8s_utils.delete_pod(
                pod.pod_name, grace_period_seconds=grace_period_seconds, force=force
            )
            if success:
                self.debug(f"Deleted Kubernetes pod {pod.pod_name}")
                # Wait for pod to be deleted (with timeout)
                try:
                    await self.k8s_utils.wait_for_pod_phase(
                        pod.pod_name,
                        [PodPhase.SUCCEEDED, PodPhase.FAILED],
                        timeout_seconds=TASK_CANCEL_TIMEOUT_SHORT,
                    )
                except Exception as e:
                    self.warning(
                        f"Timeout waiting for pod {pod.pod_name} deletion: {e}"
                    )
                return None
            else:
                error = AIPerfError(f"Failed to delete Kubernetes pod {pod.pod_name}")
                self.error(str(error))
                return error
        except Exception as e:
            self.error(f"Error deleting Kubernetes pod {pod.pod_name}: {e}")
            return e

    async def wait_for_all_services_registration(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None:
        """Wait for all required services to be registered.

        Args:
            stop_event: Event to check if operation should be cancelled
            timeout_seconds: Maximum time to wait in seconds

        Raises:
            Exception if any service failed to register, None otherwise
        """
        self.debug("Waiting for all required Kubernetes services to register...")

        # Get the set of required service types for checking completion
        required_types = set(self.required_services.keys())

        async def _wait_for_registration():
            while not stop_event.is_set():
                # Get all registered service types from the id map
                registered_types = {
                    service_info.service_type
                    for service_info in self.service_id_map.values()
                    if service_info.registration_status
                    == ServiceRegistrationStatus.REGISTERED
                }

                # Check if all required types are registered
                if required_types.issubset(registered_types):
                    return

                # Check if any of our pods have failed
                for pod in self.kubernetes_pods:
                    pod_info = await self.k8s_utils.get_pod(pod.pod_name)
                    if pod_info and pod_info.phase == PodPhase.FAILED:
                        # Get pod logs for debugging
                        try:
                            logs = await self.k8s_utils.get_pod_logs(
                                pod.pod_name, tail_lines=50
                            )
                            if logs.strip():
                                self.error(f"Pod {pod.pod_name} failed. Logs: {logs}")
                        except Exception:
                            pass

                        raise AIPerfError(
                            f"Kubernetes pod {pod.pod_name} for {pod.service_type} failed"
                        )

                # Wait a bit before checking again
                await asyncio.sleep(0.5)

        try:
            await asyncio.wait_for(_wait_for_registration(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            # Log which services didn't register in time
            registered_types_set = set(
                service_info.service_type
                for service_info in self.service_id_map.values()
                if service_info.registration_status
                == ServiceRegistrationStatus.REGISTERED
            )

            for service_type in required_types:
                if service_type not in registered_types_set:
                    self.error(
                        f"Service {service_type} failed to register within timeout"
                    )
                    # Check corresponding pod status
                    pod = next(
                        (
                            p
                            for p in self.kubernetes_pods
                            if p.service_type == service_type
                        ),
                        None,
                    )
                    if pod:
                        pod_info = await self.k8s_utils.get_pod(pod.pod_name)
                        self.error(
                            f"Pod {pod.pod_name} phase: {pod_info.phase if pod_info else 'Unknown'}"
                        )

                        # Log pod logs if available
                        try:
                            logs = await self.k8s_utils.get_pod_logs(
                                pod.pod_name, tail_lines=50
                            )
                            if logs.strip():
                                self.error(f"Pod {pod.pod_name} logs: {logs}")
                        except Exception:
                            pass

            raise AIPerfError(
                "Some Kubernetes services failed to register within timeout"
            ) from e

    async def wait_for_all_services_start(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_START_TIMEOUT,
    ) -> None:
        """Wait for all required services to be started.

        Args:
            stop_event: Event to check if operation should be cancelled
            timeout_seconds: Maximum time to wait in seconds
        """
        self.debug("Waiting for all required Kubernetes pods to start...")

        async def _wait_for_pods_to_start():
            while not stop_event.is_set():
                all_running = True

                for pod in self.kubernetes_pods:
                    pod_info = await self.k8s_utils.get_pod(pod.pod_name)

                    if not pod_info:
                        self.warning(f"Pod {pod.pod_name} not found")
                        all_running = False
                        continue

                    if pod_info.phase == PodPhase.PENDING:
                        all_running = False
                        continue
                    elif pod_info.phase == PodPhase.RUNNING:
                        continue
                    elif pod_info.phase == PodPhase.FAILED:
                        # Get pod logs for debugging
                        try:
                            logs = await self.k8s_utils.get_pod_logs(
                                pod.pod_name, tail_lines=50
                            )
                            if logs.strip():
                                self.error(f"Pod {pod.pod_name} failed. Logs: {logs}")
                        except Exception:
                            pass

                        raise AIPerfError(
                            f"Kubernetes pod {pod.pod_name} for {pod.service_type} failed"
                        )

                if all_running:
                    return

                await asyncio.sleep(1.0)

        try:
            await asyncio.wait_for(_wait_for_pods_to_start(), timeout=timeout_seconds)
            self.info("All Kubernetes pods are running")
        except asyncio.TimeoutError as e:
            # Log status of pods that didn't start
            for pod in self.kubernetes_pods:
                pod_info = await self.k8s_utils.get_pod(pod.pod_name)
                self.error(
                    f"Pod {pod.pod_name} ({pod.service_type}) phase: "
                    f"{pod_info.phase if pod_info else 'Unknown'}"
                )

            raise AIPerfError(
                "Some Kubernetes pods failed to start within timeout"
            ) from e
