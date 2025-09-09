# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import uuid
from typing import Any

try:
    from kubernetes import client, config
    from kubernetes.client import ApiException
    from kubernetes.client.models import V1Pod

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    config = None
    ApiException = Exception
    V1Pod = Any

from pydantic import BaseModel, Field

from aiperf.common.config import ServiceConfig, SystemControllerConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceRunType
from aiperf.common.exceptions import ServiceManagerError
from aiperf.common.factories import ServiceFactory, ServiceManagerFactory
from aiperf.common.kubernetes import (
    HealthChecker,
    KubernetesServiceDiscovery,
    PodManager,
)
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.service_registry import ServiceRegistry
from aiperf.common.types import ServiceTypeT
from aiperf.controller.base_service_manager import BaseServiceManager


class ServiceKubernetesRunInfo(BaseModel):
    """Information about a service running in a Kubernetes pod."""

    pod_name: str
    node_name: str | None = None
    namespace: str
    service_type: ServiceTypeT
    service_id: str
    pod_labels: dict[str, str] = Field(default_factory=dict)


@implements_protocol(ServiceManagerProtocol)
@ServiceManagerFactory.register(ServiceRunType.KUBERNETES)
class KubernetesServiceManager(BaseServiceManager):
    """
    Service Manager for starting and stopping services in a Kubernetes cluster.

    This service manager creates and manages Kubernetes pods for AIPerf services,
    providing integration with Kubernetes-native features like service discovery,
    health checks, and resource management.
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        log_queue: Any = None,
        system_config: SystemControllerConfig | None = None,
        **kwargs,
    ):
        if not KUBERNETES_AVAILABLE:
            raise ServiceManagerError(
                "Kubernetes client library is not available. "
                "Install it with: pip install kubernetes"
            )

        super().__init__(required_services, service_config, user_config, **kwargs)

        self.log_queue = log_queue
        self.system_config = system_config
        self.k8s_run_info: list[ServiceKubernetesRunInfo] = []

        # Initialize Kubernetes client
        self._init_kubernetes_client()

        # Get current namespace
        self.namespace = self._get_current_namespace()

        # Container image configuration
        self.container_image = self._get_container_image()

        # Initialize Kubernetes utilities
        self.service_discovery = KubernetesServiceDiscovery(self.namespace)
        self.pod_manager = PodManager(self.namespace)
        self.health_checker = HealthChecker(self.namespace)

        # Kubernetes configuration from service config
        self.k8s_config = getattr(service_config, "kubernetes", None)

        self.debug(
            f"KubernetesServiceManager initialized in namespace: {self.namespace}"
        )

        # Start health monitoring if enabled
        if self.k8s_config and self.k8s_config.monitoring:
            asyncio.create_task(self.health_checker.start_monitoring())

    def _init_kubernetes_client(self) -> None:
        """Initialize the Kubernetes client."""
        try:
            # Try to load in-cluster configuration first
            config.load_incluster_config()
            self.debug("Using in-cluster Kubernetes configuration")
        except config.ConfigException:
            try:
                # Fall back to local kubeconfig
                config.load_kube_config()
                self.debug("Using local kubeconfig")
            except config.ConfigException as e:
                raise ServiceManagerError(f"Could not configure Kubernetes client: {e}")

        self.core_v1_api = client.CoreV1Api()
        self.apps_v1_api = client.AppsV1Api()
        self.autoscaling_v2_api = client.AutoscalingV2Api()

    def _get_current_namespace(self) -> str:
        """Get the current Kubernetes namespace."""
        # Try to get from environment variable first
        namespace = os.getenv("KUBERNETES_NAMESPACE")
        if namespace:
            return namespace

        # Try to read from service account token
        try:
            with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
                return f.read().strip()
        except FileNotFoundError:
            # Default to 'default' namespace if running outside cluster
            self.warning("Could not determine current namespace, using 'default'")
            return "default"

    def _get_container_image(self) -> str:
        """Get the container image to use for AIPerf services."""
        # Check environment variable first
        image = os.getenv("AIPERF_CONTAINER_IMAGE")
        if image:
            return image

        # Default image configuration
        registry = os.getenv("AIPERF_IMAGE_REGISTRY", "docker.io")
        repository = os.getenv("AIPERF_IMAGE_REPOSITORY", "nvidia/aiperf")
        tag = os.getenv("AIPERF_IMAGE_TAG", "latest")

        return f"{registry}/{repository}:{tag}"

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        """Run a service as Kubernetes pods."""
        self.debug(f"Creating {num_replicas} {service_type} pod(s)")

        service_class = ServiceFactory.get_class_from_type(service_type)

        # Create pods for the number of replicas requested
        for i in range(num_replicas):
            service_id = f"{service_type}_{uuid.uuid4().hex[:8]}"

            # Register expected service with ServiceRegistry
            await ServiceRegistry.expect_service(service_id, service_class.service_type)

            # Create pod specification
            pod_spec = self._create_pod_spec(service_type, service_id)

            try:
                # Create the pod
                pod = self.core_v1_api.create_namespaced_pod(
                    namespace=self.namespace, body=pod_spec
                )

                self.info(f"Created {service_type} pod: {pod.metadata.name}")

                # Store run information
                run_info = ServiceKubernetesRunInfo(
                    pod_name=pod.metadata.name,
                    namespace=self.namespace,
                    service_type=service_type,
                    service_id=service_id,
                    pod_labels=pod.metadata.labels or {},
                )
                self.k8s_run_info.append(run_info)

            except ApiException as e:
                self.error(f"Failed to create {service_type} pod: {e}")
                raise ServiceManagerError(f"Failed to create {service_type} pod: {e}")

    async def stop_service(
        self, service_type: ServiceTypeT, service_id: str | None = None
    ) -> list[BaseException | None]:
        """Stop services of a specific type."""
        self.debug(f"Stopping {service_type} service(s)")

        # Find matching services to stop
        services_to_stop = [
            info
            for info in self.k8s_run_info
            if info.service_type == service_type
            and (service_id is None or info.service_id == service_id)
        ]

        if not services_to_stop:
            self.warning(f"No {service_type} services found to stop")
            return []

        # Stop pods gracefully
        results = []
        for service_info in services_to_stop:
            try:
                await self._delete_pod_gracefully(service_info)
                self.k8s_run_info.remove(service_info)
                results.append(None)
            except Exception as e:
                self.error(f"Failed to stop pod {service_info.pod_name}: {e}")
                results.append(e)

        return results

    async def shutdown_all_services(self) -> list[BaseException | None]:
        """Stop all managed services gracefully."""
        self.debug("Shutting down all managed services")

        if not self.k8s_run_info:
            self.debug("No services to shut down")
            return []

        # Stop all pods gracefully in parallel
        tasks = []
        for service_info in list(self.k8s_run_info):
            task = asyncio.create_task(self._delete_pod_gracefully(service_info))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Clear run information
        self.k8s_run_info.clear()

        return results

    async def kill_all_services(self) -> list[BaseException | None]:
        """Forcefully kill all managed services."""
        self.debug("Force killing all managed services")

        if not self.k8s_run_info:
            self.debug("No services to kill")
            return []

        # Kill all pods immediately
        results = []
        for service_info in list(self.k8s_run_info):
            try:
                self.core_v1_api.delete_namespaced_pod(
                    name=service_info.pod_name,
                    namespace=service_info.namespace,
                    grace_period_seconds=0,  # Immediate deletion
                )
                self.debug(f"Force deleted pod: {service_info.pod_name}")
                results.append(None)
            except ApiException as e:
                if e.status == 404:  # Pod already deleted
                    results.append(None)
                else:
                    self.error(
                        f"Failed to force delete pod {service_info.pod_name}: {e}"
                    )
                    results.append(e)

        # Clear run information
        self.k8s_run_info.clear()

        return results

    async def wait_for_all_services_registration(
        self,
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None:
        """Wait for all required services to be registered."""
        self.info("Waiting for all managed services to register...")

        # Wait for pods to be ready first
        pod_ready_tasks = []
        for service_info in self.k8s_run_info:
            task = asyncio.create_task(
                self.pod_manager.wait_for_pod_ready(
                    service_info.pod_name,
                    timeout_seconds=min(timeout_seconds, 300),  # Max 5 min per pod
                )
            )
            pod_ready_tasks.append(task)

        if pod_ready_tasks:
            self.debug("Waiting for pods to become ready...")
            ready_results = await asyncio.gather(
                *pod_ready_tasks, return_exceptions=True
            )

            failed_pods = []
            for i, result in enumerate(ready_results):
                if isinstance(result, Exception) or result is False:
                    failed_pods.append(self.k8s_run_info[i].pod_name)

            if failed_pods:
                self.warning(
                    f"The following pods failed to become ready: {failed_pods}"
                )

        # Then wait for service registry
        return await ServiceRegistry.wait_for_all(timeout_seconds)

    def _create_pod_spec(
        self, service_type: ServiceTypeT, service_id: str
    ) -> dict[str, Any]:
        """Create a Kubernetes pod specification for a service."""

        # Base labels for the pod
        labels = {
            "app": "aiperf",
            "app.kubernetes.io/name": "aiperf",
            "app.kubernetes.io/component": str(service_type).replace("_", "-"),
            "app.kubernetes.io/instance": service_id,
            "aiperf.nvidia.com/service-type": str(service_type),
            "aiperf.nvidia.com/service-id": service_id,
        }

        # Environment variables
        env_vars = [
            {"name": "AIPERF_SERVICE_RUN_TYPE", "value": "kubernetes"},
            {"name": "AIPERF_ZMQ_TCP_HOST", "value": "aiperf-zmq-proxy"},
            {
                "name": "KUBERNETES_NAMESPACE",
                "valueFrom": {"fieldRef": {"fieldPath": "metadata.namespace"}},
            },
            {
                "name": "POD_NAME",
                "valueFrom": {"fieldRef": {"fieldPath": "metadata.name"}},
            },
            {
                "name": "POD_IP",
                "valueFrom": {"fieldRef": {"fieldPath": "status.podIP"}},
            },
            {
                "name": "NODE_NAME",
                "valueFrom": {"fieldRef": {"fieldPath": "spec.nodeName"}},
            },
        ]

        # Add log level if configured
        if hasattr(self.service_config, "log_level"):
            env_vars.append(
                {
                    "name": "AIPERF_LOG_LEVEL",
                    "value": str(self.service_config.log_level),
                }
            )

        # Command and args based on service type
        command, args = self._get_service_command_args(service_type, service_id)

        # Resource requirements
        resources = self._get_service_resources(service_type)

        # Volume mounts
        volume_mounts = [
            {"name": "tmp", "mountPath": "/tmp"},
            {"name": "cache", "mountPath": "/app/cache"},
        ]

        # Volumes
        volumes = [
            {"name": "tmp", "emptyDir": {}},
            {"name": "cache", "emptyDir": {}},
        ]

        # Health check probes for services that support them
        probes = self._get_service_probes(service_type)

        # Container specification
        container_spec = {
            "name": str(service_type).replace("_", "-"),
            "image": self.container_image,
            "command": command,
            "args": args,
            "env": env_vars,
            "resources": resources,
            "volumeMounts": volume_mounts,
            "securityContext": {
                "allowPrivilegeEscalation": False,
                "readOnlyRootFilesystem": True,
                "runAsNonRoot": True,
                "runAsUser": 1000,
                "capabilities": {"drop": ["ALL"]},
            },
        }

        # Add probes if available
        if probes.get("liveness"):
            container_spec["livenessProbe"] = probes["liveness"]
        if probes.get("readiness"):
            container_spec["readinessProbe"] = probes["readiness"]

        # Pod specification
        pod_spec = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": f"aiperf-{service_type.replace('_', '-')}-{service_id.split('_')[-1]}",
                "labels": labels,
                "annotations": {
                    "aiperf.nvidia.com/created-by": "kubernetes-service-manager",
                    "aiperf.nvidia.com/service-type": str(service_type),
                    "aiperf.nvidia.com/service-id": service_id,
                },
            },
            "spec": {
                "restartPolicy": "Never",  # AIPerf manages its own lifecycle
                "securityContext": {
                    "runAsNonRoot": True,
                    "runAsUser": 1000,
                    "runAsGroup": 1000,
                    "fsGroup": 1000,
                    "seccompProfile": {"type": "RuntimeDefault"},
                },
                "containers": [container_spec],
                "volumes": volumes,
            },
        }

        return pod_spec

    def _get_service_command_args(
        self, service_type: ServiceTypeT, service_id: str
    ) -> tuple[list[str], list[str]]:
        """Get command and arguments for a specific service type."""
        base_command = ["aiperf"]

        if service_type.lower() == "worker":
            return base_command, [
                "service",
                "--service-type",
                "worker",
                "--service-id",
                service_id,
            ]
        elif service_type.lower().endswith("_manager"):
            manager_type = service_type.lower().replace("_manager", "")
            return base_command, [
                "service",
                "--service-type",
                service_type,
                "--service-id",
                service_id,
            ]
        else:
            # Generic service
            return base_command, [
                "service",
                "--service-type",
                service_type,
                "--service-id",
                service_id,
            ]

    def _get_service_resources(self, service_type: ServiceTypeT) -> dict[str, Any]:
        """Get resource requirements for a specific service type."""
        # Check if we have Kubernetes-specific configuration
        if self.k8s_config and self.k8s_config.cluster:
            cluster_config = self.k8s_config.cluster
            service_config = getattr(cluster_config, service_type.lower(), None)

            if service_config:
                return {
                    "requests": {
                        "memory": service_config.memory_request,
                        "cpu": service_config.cpu_request,
                    },
                    "limits": {
                        "memory": service_config.memory_limit,
                        "cpu": service_config.cpu_limit,
                    },
                }

        # Default resource requirements
        default_resources = {
            "requests": {"memory": "256Mi", "cpu": "200m"},
            "limits": {"memory": "512Mi", "cpu": "500m"},
        }

        # Service-specific resource requirements
        service_resources = {
            "worker": {
                "requests": {"memory": "1Gi", "cpu": "500m"},
                "limits": {"memory": "2Gi", "cpu": "1"},
            },
            "records_manager": {
                "requests": {"memory": "1Gi", "cpu": "500m"},
                "limits": {"memory": "4Gi", "cpu": "2"},
            },
            "dataset_manager": {
                "requests": {"memory": "512Mi", "cpu": "300m"},
                "limits": {"memory": "2Gi", "cpu": "1"},
            },
        }

        return service_resources.get(service_type.lower(), default_resources)

    def _get_service_probes(self, service_type: ServiceTypeT) -> dict[str, Any]:
        """Get health check probes for a specific service type."""
        # Check if health checks are disabled
        if self.k8s_config and self.k8s_config.cluster:
            service_config = getattr(
                self.k8s_config.cluster, service_type.lower(), None
            )
            if service_config and not service_config.enable_health_checks:
                return {}

        # Only add probes for services that have health endpoints
        if service_type.lower() in ["worker", "system_controller"]:
            health_port = 8080
            if self.k8s_config and self.k8s_config.cluster:
                service_config = getattr(
                    self.k8s_config.cluster, service_type.lower(), None
                )
                if service_config:
                    health_port = service_config.health_check_port

            return {
                "liveness": {
                    "httpGet": {"path": "/health", "port": health_port},
                    "initialDelaySeconds": 30,
                    "periodSeconds": 10,
                    "timeoutSeconds": 5,
                    "failureThreshold": 3,
                },
                "readiness": {
                    "httpGet": {"path": "/ready", "port": health_port},
                    "initialDelaySeconds": 5,
                    "periodSeconds": 5,
                    "timeoutSeconds": 3,
                    "failureThreshold": 3,
                },
            }

        return {}

    async def _delete_pod_gracefully(
        self, service_info: ServiceKubernetesRunInfo
    ) -> None:
        """Delete a pod gracefully with proper cleanup."""
        try:
            # Check if pod still exists
            try:
                pod = self.core_v1_api.read_namespaced_pod(
                    name=service_info.pod_name, namespace=service_info.namespace
                )
            except ApiException as e:
                if e.status == 404:
                    self.debug(f"Pod {service_info.pod_name} already deleted")
                    return
                raise

            # Delete pod with grace period
            self.core_v1_api.delete_namespaced_pod(
                name=service_info.pod_name,
                namespace=service_info.namespace,
                grace_period_seconds=TASK_CANCEL_TIMEOUT_SHORT,
            )

            self.debug(f"Requested deletion of pod: {service_info.pod_name}")

            # Wait for pod to be deleted
            await self._wait_for_pod_deletion(
                service_info.pod_name, service_info.namespace
            )

        except ApiException as e:
            if e.status == 404:  # Already deleted
                return
            raise ServiceManagerError(
                f"Failed to delete pod {service_info.pod_name}: {e}"
            )

    async def _wait_for_pod_deletion(
        self, pod_name: str, namespace: str, timeout_seconds: int = 30
    ) -> None:
        """Wait for a pod to be completely deleted."""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            try:
                self.core_v1_api.read_namespaced_pod(name=pod_name, namespace=namespace)
                # Pod still exists, wait a bit more
                await asyncio.sleep(1)
            except ApiException as e:
                if e.status == 404:
                    # Pod deleted successfully
                    self.debug(f"Pod {pod_name} successfully deleted")
                    return
                # Some other error occurred
                raise

        self.warning(
            f"Pod {pod_name} deletion timed out after {timeout_seconds} seconds"
        )
