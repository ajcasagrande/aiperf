# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pod lifecycle management utilities for AIPerf Kubernetes integration."""

import asyncio
from typing import Any

try:
    from kubernetes import client, config
    from kubernetes.client import ApiException, V1Pod

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    config = None
    ApiException = Exception
    V1Pod = Any

from aiperf.common.exceptions import ServiceManagerError
from aiperf.common.mixins import AIPerfLoggerMixin


class PodManager(AIPerfLoggerMixin):
    """
    Kubernetes pod lifecycle management utility.

    Provides high-level operations for managing AIPerf service pods
    in Kubernetes, including creation, monitoring, and cleanup.
    """

    def __init__(self, namespace: str):
        super().__init__()

        if not KUBERNETES_AVAILABLE:
            raise ServiceManagerError(
                "Kubernetes client library is not available. "
                "Install it with: pip install kubernetes"
            )

        self.namespace = namespace
        self._init_kubernetes_client()

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

    async def wait_for_pod_ready(
        self, pod_name: str, timeout_seconds: float = 300.0
    ) -> bool:
        """
        Wait for a pod to become ready.

        Args:
            pod_name: Name of the pod to wait for
            timeout_seconds: Maximum time to wait

        Returns:
            True if pod becomes ready, False if timeout or failure
        """
        self.debug(f"Waiting for pod {pod_name} to become ready...")

        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            try:
                pod = self.core_v1_api.read_namespaced_pod(
                    name=pod_name, namespace=self.namespace
                )

                # Check pod phase
                if pod.status.phase == "Running":
                    # Check if all containers are ready
                    if pod.status.container_statuses:
                        all_ready = all(
                            container.ready
                            for container in pod.status.container_statuses
                        )
                        if all_ready:
                            self.debug(f"Pod {pod_name} is ready")
                            return True
                    else:
                        # No container statuses yet, but pod is running
                        self.debug(
                            f"Pod {pod_name} is running but container statuses not available yet"
                        )

                elif pod.status.phase == "Failed":
                    self.error(f"Pod {pod_name} failed to start")
                    return False

                elif pod.status.phase == "Succeeded":
                    self.debug(f"Pod {pod_name} completed successfully")
                    return True

                # Log current status for debugging
                self.debug(
                    f"Pod {pod_name} status: phase={pod.status.phase}, "
                    f"ready={self._get_ready_condition(pod)}"
                )

            except ApiException as e:
                if e.status == 404:
                    self.debug(f"Pod {pod_name} not found yet")
                else:
                    self.error(f"Error checking pod {pod_name} status: {e}")
                    return False

            await asyncio.sleep(2)  # Check every 2 seconds

        self.warning(
            f"Pod {pod_name} did not become ready within {timeout_seconds} seconds"
        )
        return False

    def _get_ready_condition(self, pod: V1Pod) -> str | None:
        """Get the Ready condition status from a pod."""
        if not pod.status.conditions:
            return None

        for condition in pod.status.conditions:
            if condition.type == "Ready":
                return condition.status

        return None

    async def get_pod_logs(
        self, pod_name: str, container_name: str | None = None, lines: int = 100
    ) -> str:
        """
        Get logs from a pod.

        Args:
            pod_name: Name of the pod
            container_name: Optional container name (for multi-container pods)
            lines: Number of lines to retrieve

        Returns:
            Pod logs as string
        """
        try:
            logs = self.core_v1_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace,
                container=container_name,
                tail_lines=lines,
            )
            return logs

        except ApiException as e:
            if e.status == 404:
                return f"Pod {pod_name} not found"
            else:
                self.error(f"Error getting logs for pod {pod_name}: {e}")
                return f"Error retrieving logs: {e}"

    async def get_pod_status(self, pod_name: str) -> dict[str, Any] | None:
        """
        Get detailed status information for a pod.

        Args:
            pod_name: Name of the pod

        Returns:
            Dictionary with pod status information
        """
        try:
            pod = self.core_v1_api.read_namespaced_pod(
                name=pod_name, namespace=self.namespace
            )

            status_info = {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "phase": pod.status.phase,
                "node_name": pod.spec.node_name,
                "pod_ip": pod.status.pod_ip,
                "start_time": pod.status.start_time,
                "conditions": [],
                "containers": [],
            }

            # Extract conditions
            if pod.status.conditions:
                for condition in pod.status.conditions:
                    status_info["conditions"].append(
                        {
                            "type": condition.type,
                            "status": condition.status,
                            "reason": condition.reason,
                            "message": condition.message,
                            "last_transition_time": condition.last_transition_time,
                        }
                    )

            # Extract container statuses
            if pod.status.container_statuses:
                for container_status in pod.status.container_statuses:
                    container_info = {
                        "name": container_status.name,
                        "ready": container_status.ready,
                        "restart_count": container_status.restart_count,
                        "image": container_status.image,
                        "state": {},
                    }

                    # Get container state
                    if container_status.state.running:
                        container_info["state"] = {
                            "type": "running",
                            "started_at": container_status.state.running.started_at,
                        }
                    elif container_status.state.waiting:
                        container_info["state"] = {
                            "type": "waiting",
                            "reason": container_status.state.waiting.reason,
                            "message": container_status.state.waiting.message,
                        }
                    elif container_status.state.terminated:
                        container_info["state"] = {
                            "type": "terminated",
                            "exit_code": container_status.state.terminated.exit_code,
                            "reason": container_status.state.terminated.reason,
                            "message": container_status.state.terminated.message,
                            "started_at": container_status.state.terminated.started_at,
                            "finished_at": container_status.state.terminated.finished_at,
                        }

                    status_info["containers"].append(container_info)

            return status_info

        except ApiException as e:
            if e.status == 404:
                return None
            else:
                self.error(f"Error getting status for pod {pod_name}: {e}")
                raise ServiceManagerError(f"Failed to get pod status: {e}")

    async def list_aiperf_pods(
        self, service_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        List all AIPerf pods in the namespace.

        Args:
            service_type: Optional filter by service type

        Returns:
            List of pod information dictionaries
        """
        try:
            # Build label selector
            label_selector = "app=aiperf"
            if service_type:
                label_selector += f",aiperf.nvidia.com/service-type={service_type}"

            pods = self.core_v1_api.list_namespaced_pod(
                namespace=self.namespace, label_selector=label_selector
            )

            pod_list = []
            for pod in pods.items:
                pod_info = {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "phase": pod.status.phase,
                    "node_name": pod.spec.node_name,
                    "pod_ip": pod.status.pod_ip,
                    "labels": pod.metadata.labels or {},
                    "annotations": pod.metadata.annotations or {},
                    "creation_timestamp": pod.metadata.creation_timestamp,
                    "ready": False,
                }

                # Check if pod is ready
                if pod.status.conditions:
                    for condition in pod.status.conditions:
                        if condition.type == "Ready" and condition.status == "True":
                            pod_info["ready"] = True
                            break

                # Extract service information from labels
                labels = pod.metadata.labels or {}
                pod_info["service_type"] = labels.get("aiperf.nvidia.com/service-type")
                pod_info["service_id"] = labels.get("aiperf.nvidia.com/service-id")

                pod_list.append(pod_info)

            self.debug(f"Found {len(pod_list)} AIPerf pods")
            return pod_list

        except ApiException as e:
            self.error(f"Error listing AIPerf pods: {e}")
            raise ServiceManagerError(f"Failed to list pods: {e}")

    async def delete_pods_by_label(
        self, label_selector: str, grace_period_seconds: int = 30
    ) -> list[str]:
        """
        Delete pods matching a label selector.

        Args:
            label_selector: Kubernetes label selector
            grace_period_seconds: Grace period for pod deletion

        Returns:
            List of deleted pod names
        """
        try:
            # First, list pods to delete
            pods = self.core_v1_api.list_namespaced_pod(
                namespace=self.namespace, label_selector=label_selector
            )

            deleted_pods = []
            for pod in pods.items:
                try:
                    self.core_v1_api.delete_namespaced_pod(
                        name=pod.metadata.name,
                        namespace=self.namespace,
                        grace_period_seconds=grace_period_seconds,
                    )
                    deleted_pods.append(pod.metadata.name)
                    self.debug(f"Requested deletion of pod: {pod.metadata.name}")
                except ApiException as e:
                    if e.status != 404:  # Ignore if already deleted
                        self.error(f"Failed to delete pod {pod.metadata.name}: {e}")

            return deleted_pods

        except ApiException as e:
            self.error(f"Error deleting pods with selector {label_selector}: {e}")
            raise ServiceManagerError(f"Failed to delete pods: {e}")

    async def wait_for_pod_deletion(
        self, pod_names: list[str], timeout_seconds: float = 120.0
    ) -> bool:
        """
        Wait for pods to be completely deleted.

        Args:
            pod_names: List of pod names to wait for deletion
            timeout_seconds: Maximum time to wait

        Returns:
            True if all pods are deleted, False if timeout
        """
        if not pod_names:
            return True

        self.debug(f"Waiting for {len(pod_names)} pods to be deleted...")

        start_time = asyncio.get_event_loop().time()
        remaining_pods = set(pod_names)

        while (
            remaining_pods
            and (asyncio.get_event_loop().time() - start_time) < timeout_seconds
        ):
            for pod_name in list(remaining_pods):
                try:
                    self.core_v1_api.read_namespaced_pod(
                        name=pod_name, namespace=self.namespace
                    )
                    # Pod still exists
                except ApiException as e:
                    if e.status == 404:
                        # Pod deleted successfully
                        remaining_pods.remove(pod_name)
                        self.debug(f"Pod {pod_name} successfully deleted")

            if remaining_pods:
                await asyncio.sleep(2)  # Wait before retrying

        if remaining_pods:
            self.warning(
                f"The following pods were not deleted within timeout: {remaining_pods}"
            )
            return False
        else:
            self.debug("All pods successfully deleted")
            return True
