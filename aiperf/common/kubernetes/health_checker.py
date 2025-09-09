# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Health checking utilities for AIPerf Kubernetes integration."""

import asyncio
from datetime import datetime

try:
    from kubernetes import client, config
    from kubernetes.client import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    config = None
    ApiException = Exception

from aiperf.common.exceptions import HealthCheckError
from aiperf.common.mixins import AIPerfLoggerMixin


class HealthChecker(AIPerfLoggerMixin):
    """
    Health checking utility for AIPerf services running in Kubernetes.

    Provides health monitoring capabilities for AIPerf service pods,
    including readiness checks, liveness monitoring, and service health reporting.
    """

    def __init__(self, namespace: str):
        super().__init__()

        if not KUBERNETES_AVAILABLE:
            raise HealthCheckError(
                "Kubernetes client library is not available. "
                "Install it with: pip install kubernetes"
            )

        self.namespace = namespace
        self._init_kubernetes_client()

        # Health check configuration
        self.check_interval = 10  # Default check interval in seconds
        self.unhealthy_threshold = 3  # Number of failed checks before marking unhealthy

        # Health status tracking
        self._health_status: dict[str, dict] = {}
        self._monitoring_active = False
        self._monitoring_task: asyncio.Task | None = None

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
                raise HealthCheckError(f"Could not configure Kubernetes client: {e}")

        self.core_v1_api = client.CoreV1Api()

    async def check_pod_health(self, pod_name: str) -> dict[str, any]:
        """
        Check the health status of a specific pod.

        Args:
            pod_name: Name of the pod to check

        Returns:
            Dictionary containing health information:
            - 'healthy': Boolean indicating overall health
            - 'phase': Pod phase (Running, Pending, etc.)
            - 'ready': Boolean indicating if pod is ready
            - 'conditions': List of pod conditions
            - 'container_states': List of container states
            - 'restart_count': Total restart count
            - 'last_check': Timestamp of last check
        """
        try:
            pod = self.core_v1_api.read_namespaced_pod(
                name=pod_name, namespace=self.namespace
            )

            health_info = {
                "healthy": False,
                "phase": pod.status.phase,
                "ready": False,
                "conditions": [],
                "container_states": [],
                "restart_count": 0,
                "last_check": datetime.now().isoformat(),
                "node_name": pod.spec.node_name,
                "pod_ip": pod.status.pod_ip,
            }

            # Check pod conditions
            if pod.status.conditions:
                for condition in pod.status.conditions:
                    condition_info = {
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason,
                        "message": condition.message,
                        "last_transition_time": condition.last_transition_time.isoformat()
                        if condition.last_transition_time
                        else None,
                    }
                    health_info["conditions"].append(condition_info)

                    # Check if pod is ready
                    if condition.type == "Ready" and condition.status == "True":
                        health_info["ready"] = True

            # Check container states
            if pod.status.container_statuses:
                for container_status in pod.status.container_statuses:
                    container_info = {
                        "name": container_status.name,
                        "ready": container_status.ready,
                        "restart_count": container_status.restart_count,
                        "image": container_status.image,
                        "state": "unknown",
                    }

                    health_info["restart_count"] += container_status.restart_count

                    # Determine container state
                    if container_status.state.running:
                        container_info["state"] = "running"
                        container_info["started_at"] = (
                            container_status.state.running.started_at.isoformat()
                            if container_status.state.running.started_at
                            else None
                        )
                    elif container_status.state.waiting:
                        container_info["state"] = "waiting"
                        container_info["reason"] = container_status.state.waiting.reason
                        container_info["message"] = (
                            container_status.state.waiting.message
                        )
                    elif container_status.state.terminated:
                        container_info["state"] = "terminated"
                        container_info["exit_code"] = (
                            container_status.state.terminated.exit_code
                        )
                        container_info["reason"] = (
                            container_status.state.terminated.reason
                        )
                        container_info["message"] = (
                            container_status.state.terminated.message
                        )

                    health_info["container_states"].append(container_info)

            # Determine overall health
            health_info["healthy"] = (
                pod.status.phase == "Running"
                and health_info["ready"]
                and all(
                    container["ready"] for container in health_info["container_states"]
                )
            )

            return health_info

        except ApiException as e:
            if e.status == 404:
                return {
                    "healthy": False,
                    "phase": "NotFound",
                    "ready": False,
                    "conditions": [],
                    "container_states": [],
                    "restart_count": 0,
                    "last_check": datetime.now().isoformat(),
                    "error": f"Pod {pod_name} not found",
                }
            else:
                self.error(f"Error checking health for pod {pod_name}: {e}")
                raise HealthCheckError(f"Failed to check pod health: {e}")

    async def check_service_health(self, service_name: str) -> dict[str, any]:
        """
        Check the health of all pods behind a service.

        Args:
            service_name: Name of the service to check

        Returns:
            Dictionary containing service health information
        """
        try:
            # Get service endpoints to find pod IPs
            endpoints = self.core_v1_api.read_namespaced_endpoints(
                name=service_name, namespace=self.namespace
            )

            service_health = {
                "service_name": service_name,
                "healthy": False,
                "total_pods": 0,
                "healthy_pods": 0,
                "ready_pods": 0,
                "pod_health": [],
                "last_check": datetime.now().isoformat(),
            }

            # Get all pod IPs from endpoints
            pod_ips = []
            for subset in endpoints.subsets or []:
                for address in subset.addresses or []:
                    pod_ips.append(address.ip)
                for address in subset.not_ready_addresses or []:
                    pod_ips.append(address.ip)

            # Find pods by IP
            if pod_ips:
                pods = self.core_v1_api.list_namespaced_pod(
                    namespace=self.namespace,
                    field_selector=f"status.podIP in ({','.join(pod_ips)})",
                )

                service_health["total_pods"] = len(pods.items)

                for pod in pods.items:
                    pod_health = await self.check_pod_health(pod.metadata.name)
                    service_health["pod_health"].append(pod_health)

                    if pod_health["healthy"]:
                        service_health["healthy_pods"] += 1
                    if pod_health["ready"]:
                        service_health["ready_pods"] += 1

            # Service is healthy if at least one pod is healthy
            service_health["healthy"] = service_health["healthy_pods"] > 0

            return service_health

        except ApiException as e:
            if e.status == 404:
                return {
                    "service_name": service_name,
                    "healthy": False,
                    "total_pods": 0,
                    "healthy_pods": 0,
                    "ready_pods": 0,
                    "pod_health": [],
                    "last_check": datetime.now().isoformat(),
                    "error": f"Service {service_name} not found",
                }
            else:
                self.error(f"Error checking health for service {service_name}: {e}")
                raise HealthCheckError(f"Failed to check service health: {e}")

    async def get_system_health_summary(self) -> dict[str, any]:
        """
        Get overall health summary for AIPerf system.

        Returns:
            Dictionary containing system-wide health information
        """
        try:
            # Get all AIPerf pods
            pods = self.core_v1_api.list_namespaced_pod(
                namespace=self.namespace, label_selector="app=aiperf"
            )

            health_summary = {
                "overall_healthy": False,
                "total_pods": len(pods.items),
                "healthy_pods": 0,
                "ready_pods": 0,
                "unhealthy_pods": 0,
                "services": {},
                "issues": [],
                "last_check": datetime.now().isoformat(),
            }

            # Group pods by service type
            service_pods = {}
            for pod in pods.items:
                labels = pod.metadata.labels or {}
                service_type = labels.get("aiperf.nvidia.com/service-type", "unknown")

                if service_type not in service_pods:
                    service_pods[service_type] = []
                service_pods[service_type].append(pod.metadata.name)

            # Check health for each service type
            for service_type, pod_names in service_pods.items():
                service_summary = {
                    "total_pods": len(pod_names),
                    "healthy_pods": 0,
                    "ready_pods": 0,
                    "pods": [],
                }

                for pod_name in pod_names:
                    pod_health = await self.check_pod_health(pod_name)
                    service_summary["pods"].append(
                        {
                            "name": pod_name,
                            "healthy": pod_health["healthy"],
                            "ready": pod_health["ready"],
                            "phase": pod_health["phase"],
                            "restart_count": pod_health["restart_count"],
                        }
                    )

                    if pod_health["healthy"]:
                        service_summary["healthy_pods"] += 1
                        health_summary["healthy_pods"] += 1
                    else:
                        health_summary["unhealthy_pods"] += 1

                        # Add to issues list
                        if pod_health["phase"] != "Running":
                            health_summary["issues"].append(
                                f"Pod {pod_name} ({service_type}) is in {pod_health['phase']} phase"
                            )

                    if pod_health["ready"]:
                        service_summary["ready_pods"] += 1
                        health_summary["ready_pods"] += 1

                health_summary["services"][service_type] = service_summary

            # System is healthy if critical services are healthy
            critical_services = [
                "system_controller",
                "worker_manager",
                "records_manager",
            ]
            critical_healthy = True

            for critical_service in critical_services:
                if critical_service in health_summary["services"]:
                    service_info = health_summary["services"][critical_service]
                    if service_info["healthy_pods"] == 0:
                        critical_healthy = False
                        health_summary["issues"].append(
                            f"Critical service {critical_service} has no healthy pods"
                        )

            health_summary["overall_healthy"] = (
                critical_healthy and health_summary["healthy_pods"] > 0
            )

            return health_summary

        except ApiException as e:
            self.error(f"Error getting system health summary: {e}")
            raise HealthCheckError(f"Failed to get system health: {e}")

    async def start_monitoring(self, check_interval: int = 30):
        """
        Start continuous health monitoring.

        Args:
            check_interval: Interval between health checks in seconds
        """
        if self._monitoring_active:
            self.warning("Health monitoring is already active")
            return

        self.check_interval = check_interval
        self._monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.info(f"Started health monitoring with {check_interval}s interval")

    async def stop_monitoring(self):
        """Stop continuous health monitoring."""
        if not self._monitoring_active:
            return

        self._monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self.info("Stopped health monitoring")

    async def _monitoring_loop(self):
        """Internal monitoring loop."""
        while self._monitoring_active:
            try:
                # Get system health
                health_summary = await self.get_system_health_summary()

                # Log health status
                if health_summary["overall_healthy"]:
                    self.debug(
                        f"System health: {health_summary['healthy_pods']}/{health_summary['total_pods']} pods healthy"
                    )
                else:
                    self.warning(
                        f"System unhealthy: {health_summary['healthy_pods']}/{health_summary['total_pods']} pods healthy. "
                        f"Issues: {'; '.join(health_summary['issues'])}"
                    )

                # Store health status
                self._health_status = health_summary

            except Exception as e:
                self.error(f"Error in health monitoring loop: {e}")

            # Wait for next check
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break

    def get_cached_health_status(self) -> dict[str, any] | None:
        """
        Get the last cached health status.

        Returns:
            Dictionary with last health check results, or None if no data available
        """
        return self._health_status.copy() if self._health_status else None
