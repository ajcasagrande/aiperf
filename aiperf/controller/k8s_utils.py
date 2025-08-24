# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum
from aiperf.common.exceptions import AIPerfError

# Optional import for Kubernetes client
try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False

    # Fallback types for when Kubernetes is not available
    class _MockClient:
        pass

    class _MockConfig:
        pass

    client = _MockClient()  # type: ignore
    config = _MockConfig()  # type: ignore
    ApiException = Exception


class PodPhase(CaseInsensitiveStrEnum):
    """Kubernetes pod phases."""

    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ContainerState(CaseInsensitiveStrEnum):
    """Kubernetes container states."""

    WAITING = "waiting"
    RUNNING = "running"
    TERMINATED = "terminated"


class PodInfo(BaseModel):
    """Information about a Kubernetes pod."""

    name: str = Field(..., description="Pod name")
    namespace: str = Field(..., description="Pod namespace")
    phase: PodPhase = Field(..., description="Pod phase")
    node_name: str | None = Field(
        default=None, description="Node the pod is running on"
    )
    pod_ip: str | None = Field(default=None, description="Pod IP address")
    host_ip: str | None = Field(default=None, description="Host IP address")
    start_time: str | None = Field(default=None, description="Pod start time")
    container_statuses: list[dict[str, Any]] = Field(
        default_factory=list, description="Container statuses"
    )


class KubernetesUtils:
    """Utilities for interacting with Kubernetes API."""

    def __init__(
        self,
        namespace: str = "default",
        kubeconfig_path: str | None = None,
        in_cluster: bool = False,
    ):
        """Initialize Kubernetes utilities.

        Args:
            namespace: Kubernetes namespace to use
            kubeconfig_path: Path to kubeconfig file (if not using default)
            in_cluster: Whether running inside a Kubernetes cluster
        """
        if not KUBERNETES_AVAILABLE:
            raise AIPerfError(
                "Kubernetes client library not available. "
                "Install with: pip install kubernetes"
            )

        self.namespace = namespace
        self.kubeconfig_path = kubeconfig_path
        self.in_cluster = in_cluster

        # Kubernetes API clients (initialized lazily)
        self._v1_api: Any | None = None
        self._apps_v1_api: Any | None = None

        self.logger = logging.getLogger(__name__)

    async def initialize(self) -> None:
        """Initialize Kubernetes API clients."""
        try:
            if self.in_cluster:
                # Load in-cluster config
                config.load_incluster_config()
            elif self.kubeconfig_path:
                # Load config from specific file
                config.load_kube_config(config_file=self.kubeconfig_path)
            else:
                # Load default kubeconfig
                config.load_kube_config()

            self._v1_api = client.CoreV1Api()
            self._apps_v1_api = client.AppsV1Api()

            # Test connection by listing namespaces
            await self._run_k8s_operation(lambda: self._v1_api.list_namespace(limit=1))

        except Exception as e:
            raise AIPerfError(f"Failed to initialize Kubernetes client: {e}") from e

    async def create_pod(
        self,
        name: str,
        image: str,
        command: list[str],
        args: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        resources: dict[str, Any] | None = None,
        node_selector: dict[str, str] | None = None,
        service_account: str | None = None,
        restart_policy: str = "Never",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> PodInfo:
        """Create a Kubernetes pod.

        Args:
            name: Pod name
            image: Container image
            command: Command to run
            args: Command arguments
            env_vars: Environment variables
            resources: Resource requests/limits
            node_selector: Node selector
            service_account: Service account name
            restart_policy: Pod restart policy
            labels: Pod labels
            annotations: Pod annotations

        Returns:
            Created pod information

        Raises:
            AIPerfError: If pod creation fails
        """
        try:
            # Prepare environment variables
            env_list = []
            if env_vars:
                for key, value in env_vars.items():
                    env_list.append(client.V1EnvVar(name=key, value=str(value)))

            # Prepare resource requirements
            resource_requirements = None
            if resources:
                resource_requirements = client.V1ResourceRequirements(
                    requests=resources.get("requests", {}),
                    limits=resources.get("limits", {}),
                )

            # Create container spec
            container = client.V1Container(
                name=name,
                image=image,
                command=command,
                args=args or [],
                env=env_list,
                resources=resource_requirements,
            )

            # Create pod spec
            pod_spec = client.V1PodSpec(
                containers=[container],
                restart_policy=restart_policy,
                node_selector=node_selector or {},
                service_account_name=service_account,
            )

            # Create metadata
            metadata = client.V1ObjectMeta(
                name=name,
                namespace=self.namespace,
                labels=labels or {},
                annotations=annotations or {},
            )

            # Create pod
            pod_body = client.V1Pod(
                api_version="v1",
                kind="Pod",
                metadata=metadata,
                spec=pod_spec,
            )

            result = await self._run_k8s_operation(
                lambda: self._v1_api.create_namespaced_pod(
                    namespace=self.namespace, body=pod_body
                )
            )

            return self._pod_to_info(result)

        except Exception as e:
            raise AIPerfError(f"Failed to create pod {name}: {e}") from e

    async def get_pod(self, name: str) -> PodInfo | None:
        """Get information about a pod.

        Args:
            name: Pod name

        Returns:
            Pod information or None if not found
        """
        try:
            result = await self._run_k8s_operation(
                lambda: self._v1_api.read_namespaced_pod(
                    name=name, namespace=self.namespace
                )
            )
            return self._pod_to_info(result)

        except ApiException as e:
            if e.status == 404:
                return None
            raise AIPerfError(f"Error getting pod {name}: {e}") from e

    async def delete_pod(
        self, name: str, grace_period_seconds: int | None = None, force: bool = False
    ) -> bool:
        """Delete a pod.

        Args:
            name: Pod name
            grace_period_seconds: Graceful termination period
            force: Force deletion

        Returns:
            True if deletion was initiated successfully
        """
        try:
            delete_options = client.V1DeleteOptions()
            if grace_period_seconds is not None:
                delete_options.grace_period_seconds = grace_period_seconds
            if force:
                delete_options.grace_period_seconds = 0

            await self._run_k8s_operation(
                lambda: self._v1_api.delete_namespaced_pod(
                    name=name, namespace=self.namespace, body=delete_options
                )
            )
            return True

        except ApiException as e:
            if e.status == 404:
                # Pod already deleted
                return True
            raise AIPerfError(f"Error deleting pod {name}: {e}") from e

    async def list_pods(
        self, label_selector: str | None = None, field_selector: str | None = None
    ) -> list[PodInfo]:
        """List pods in the namespace.

        Args:
            label_selector: Label selector filter
            field_selector: Field selector filter

        Returns:
            List of pod information
        """
        try:
            result = await self._run_k8s_operation(
                lambda: self._v1_api.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=label_selector,
                    field_selector=field_selector,
                )
            )

            return [self._pod_to_info(pod) for pod in result.items]

        except Exception as e:
            raise AIPerfError(f"Error listing pods: {e}") from e

    async def wait_for_pod_phase(
        self,
        name: str,
        target_phases: list[PodPhase],
        timeout_seconds: float = 300.0,
        check_interval: float = 2.0,
    ) -> PodPhase:
        """Wait for a pod to reach one of the target phases.

        Args:
            name: Pod name
            target_phases: List of acceptable phases
            timeout_seconds: Maximum time to wait
            check_interval: How often to check

        Returns:
            Final pod phase

        Raises:
            AIPerfError: If timeout is reached or pod fails
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            pod_info = await self.get_pod(name)

            if pod_info is None:
                raise AIPerfError(f"Pod {name} not found")

            if pod_info.phase in target_phases:
                return pod_info.phase

            # Check for failure conditions
            if pod_info.phase == PodPhase.FAILED:
                raise AIPerfError(f"Pod {name} failed")

            # Check timeout
            if (asyncio.get_event_loop().time() - start_time) > timeout_seconds:
                raise AIPerfError(
                    f"Timeout waiting for pod {name} to reach phases {target_phases}. "
                    f"Current phase: {pod_info.phase}"
                )

            await asyncio.sleep(check_interval)

    async def get_pod_logs(
        self,
        name: str,
        container: str | None = None,
        tail_lines: int | None = None,
        since_seconds: int | None = None,
    ) -> str:
        """Get logs from a pod.

        Args:
            name: Pod name
            container: Container name (if pod has multiple containers)
            tail_lines: Number of lines to retrieve from the end
            since_seconds: Logs since this many seconds ago

        Returns:
            Pod logs as string
        """
        try:
            result = await self._run_k8s_operation(
                lambda: self._v1_api.read_namespaced_pod_log(
                    name=name,
                    namespace=self.namespace,
                    container=container,
                    tail_lines=tail_lines,
                    since_seconds=since_seconds,
                )
            )
            return result

        except Exception as e:
            raise AIPerfError(f"Error getting logs for pod {name}: {e}") from e

    async def is_kubernetes_available(self) -> bool:
        """Check if Kubernetes is available and accessible.

        Returns:
            True if Kubernetes is available
        """
        if not KUBERNETES_AVAILABLE:
            return False

        try:
            await self.initialize()
            return True
        except Exception:
            return False

    def _pod_to_info(self, pod: Any) -> PodInfo:
        """Convert Kubernetes pod object to PodInfo.

        Args:
            pod: Kubernetes pod object

        Returns:
            PodInfo object
        """
        container_statuses = []
        if pod.status and pod.status.container_statuses:
            for status in pod.status.container_statuses:
                container_statuses.append(
                    {
                        "name": status.name,
                        "ready": status.ready,
                        "restart_count": status.restart_count,
                        "state": self._get_container_state(status.state),
                    }
                )

        return PodInfo(
            name=pod.metadata.name,
            namespace=pod.metadata.namespace,
            phase=PodPhase(pod.status.phase) if pod.status else PodPhase.UNKNOWN,
            node_name=pod.spec.node_name if pod.spec else None,
            pod_ip=pod.status.pod_ip if pod.status else None,
            host_ip=pod.status.host_ip if pod.status else None,
            start_time=str(pod.status.start_time)
            if pod.status and pod.status.start_time
            else None,
            container_statuses=container_statuses,
        )

    def _get_container_state(self, state: Any) -> str:
        """Get container state as string.

        Args:
            state: Container state object

        Returns:
            State as string
        """
        if state.running:
            return ContainerState.RUNNING
        elif state.waiting:
            return ContainerState.WAITING
        elif state.terminated:
            return ContainerState.TERMINATED
        else:
            return "unknown"

    async def _run_k8s_operation(self, operation) -> Any:
        """Run a Kubernetes operation with async wrapper.

        Args:
            operation: Function to execute

        Returns:
            Operation result
        """
        # Run Kubernetes operation in thread pool since the client is synchronous
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, operation)
