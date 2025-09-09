# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Kubernetes service discovery utilities for AIPerf."""

import asyncio
import os

try:
    from kubernetes import client, config
    from kubernetes.client import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    config = None
    ApiException = Exception

from aiperf.common.exceptions import ServiceDiscoveryError
from aiperf.common.mixins import AIPerfLoggerMixin


class KubernetesServiceDiscovery(AIPerfLoggerMixin):
    """
    Kubernetes-native service discovery for AIPerf services.

    This class provides service discovery capabilities using Kubernetes Services
    and Endpoints, allowing AIPerf components to discover each other dynamically
    in a Kubernetes cluster environment.
    """

    def __init__(self, namespace: str | None = None):
        super().__init__()

        if not KUBERNETES_AVAILABLE:
            raise ServiceDiscoveryError(
                "Kubernetes client library is not available. "
                "Install it with: pip install kubernetes"
            )

        self.namespace = namespace or self._get_current_namespace()
        self._init_kubernetes_client()

        # Cache for service endpoints
        self._service_cache: dict[str, dict[str, str]] = {}
        self._cache_ttl = 30  # Cache TTL in seconds
        self._last_cache_update = 0.0

        self.debug(
            f"KubernetesServiceDiscovery initialized for namespace: {self.namespace}"
        )

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
                self.debug("Using local kubeconfig for service discovery")
            except config.ConfigException as e:
                raise ServiceDiscoveryError(
                    f"Could not configure Kubernetes client: {e}"
                )

        self.core_v1_api = client.CoreV1Api()

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

    async def discover_service(
        self, service_name: str, port_name: str | None = None
    ) -> dict[str, str] | None:
        """
        Discover a service by name and return its connection information.

        Args:
            service_name: Name of the Kubernetes service to discover
            port_name: Optional specific port name to retrieve

        Returns:
            Dictionary containing service connection information with keys:
            - 'host': Service hostname/IP
            - 'port': Service port number
            - 'ports': Dictionary of all available ports (name -> port)
        """
        try:
            service = self.core_v1_api.read_namespaced_service(
                name=service_name, namespace=self.namespace
            )

            # Get service connection info
            service_info = {
                "host": f"{service_name}.{self.namespace}.svc.cluster.local",
                "cluster_ip": service.spec.cluster_ip,
                "ports": {},
            }

            # Extract port information
            for port in service.spec.ports or []:
                port_info = {
                    "port": port.port,
                    "target_port": port.target_port,
                    "protocol": port.protocol or "TCP",
                }

                if port.name:
                    service_info["ports"][port.name] = port_info
                else:
                    service_info["ports"]["default"] = port_info

            # Set default port
            if port_name and port_name in service_info["ports"]:
                service_info["port"] = service_info["ports"][port_name]["port"]
            elif "default" in service_info["ports"]:
                service_info["port"] = service_info["ports"]["default"]["port"]
            elif service_info["ports"]:
                # Use first available port
                first_port = next(iter(service_info["ports"].values()))
                service_info["port"] = first_port["port"]

            self.debug(f"Discovered service {service_name}: {service_info}")
            return service_info

        except ApiException as e:
            if e.status == 404:
                self.debug(
                    f"Service {service_name} not found in namespace {self.namespace}"
                )
                return None
            else:
                self.error(f"Error discovering service {service_name}: {e}")
                raise ServiceDiscoveryError(
                    f"Failed to discover service {service_name}: {e}"
                )

    async def discover_zmq_proxy(self) -> dict[str, str] | None:
        """
        Discover the ZMQ proxy service specifically.

        Returns:
            Dictionary with ZMQ proxy connection information
        """
        proxy_service = await self.discover_service("aiperf-zmq-proxy")
        if not proxy_service:
            return None

        # Map well-known ZMQ ports
        zmq_info = {
            "host": proxy_service["host"],
            "frontend_port": None,
            "backend_port": None,
            "control_port": None,
        }

        # Try to map ports by name or common port numbers
        ports = proxy_service.get("ports", {})

        if "frontend" in ports:
            zmq_info["frontend_port"] = ports["frontend"]["port"]
        elif "pub-sub" in ports:
            zmq_info["frontend_port"] = ports["pub-sub"]["port"]

        if "backend" in ports:
            zmq_info["backend_port"] = ports["backend"]["port"]
        elif "push-pull" in ports:
            zmq_info["backend_port"] = ports["push-pull"]["port"]

        if "control" in ports:
            zmq_info["control_port"] = ports["control"]["port"]

        # Fall back to common port numbers if names don't match
        for port_name, port_info in ports.items():
            port_num = port_info["port"]
            if port_num == 5555 and not zmq_info["frontend_port"]:
                zmq_info["frontend_port"] = port_num
            elif port_num == 5556 and not zmq_info["backend_port"]:
                zmq_info["backend_port"] = port_num
            elif port_num == 5557 and not zmq_info["control_port"]:
                zmq_info["control_port"] = port_num

        self.debug(f"ZMQ proxy discovery result: {zmq_info}")
        return zmq_info

    async def list_aiperf_services(self) -> list[dict[str, str]]:
        """
        List all AIPerf services in the current namespace.

        Returns:
            List of service information dictionaries
        """
        try:
            services = self.core_v1_api.list_namespaced_service(
                namespace=self.namespace, label_selector="app=aiperf"
            )

            service_list = []
            for service in services.items:
                service_info = {
                    "name": service.metadata.name,
                    "namespace": service.metadata.namespace,
                    "host": f"{service.metadata.name}.{service.metadata.namespace}.svc.cluster.local",
                    "cluster_ip": service.spec.cluster_ip,
                    "labels": service.metadata.labels or {},
                    "ports": {},
                }

                # Extract port information
                for port in service.spec.ports or []:
                    port_info = {
                        "port": port.port,
                        "target_port": port.target_port,
                        "protocol": port.protocol or "TCP",
                    }

                    if port.name:
                        service_info["ports"][port.name] = port_info
                    else:
                        service_info["ports"]["default"] = port_info

                service_list.append(service_info)

            self.debug(f"Found {len(service_list)} AIPerf services")
            return service_list

        except ApiException as e:
            self.error(f"Error listing AIPerf services: {e}")
            raise ServiceDiscoveryError(f"Failed to list services: {e}")

    async def wait_for_service(
        self, service_name: str, timeout_seconds: float = 60.0
    ) -> bool:
        """
        Wait for a service to become available.

        Args:
            service_name: Name of the service to wait for
            timeout_seconds: Maximum time to wait

        Returns:
            True if service becomes available, False if timeout
        """
        self.info(f"Waiting for service {service_name} to become available...")

        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            service_info = await self.discover_service(service_name)
            if service_info:
                self.info(f"Service {service_name} is now available")
                return True

            await asyncio.sleep(2)  # Wait 2 seconds before retrying

        self.warning(
            f"Service {service_name} did not become available within {timeout_seconds} seconds"
        )
        return False

    async def get_service_endpoints(self, service_name: str) -> list[dict[str, str]]:
        """
        Get the actual pod endpoints for a service.

        Args:
            service_name: Name of the service

        Returns:
            List of endpoint dictionaries with 'ip' and 'ports' keys
        """
        try:
            endpoints = self.core_v1_api.read_namespaced_endpoints(
                name=service_name, namespace=self.namespace
            )

            endpoint_list = []
            for subset in endpoints.subsets or []:
                # Get port information
                ports = {}
                for port in subset.ports or []:
                    port_info = {"port": port.port, "protocol": port.protocol or "TCP"}
                    if port.name:
                        ports[port.name] = port_info
                    else:
                        ports["default"] = port_info

                # Get address information
                for address in subset.addresses or []:
                    endpoint_info = {
                        "ip": address.ip,
                        "hostname": getattr(address, "hostname", None),
                        "node_name": getattr(address, "node_name", None),
                        "ports": ports,
                    }
                    endpoint_list.append(endpoint_info)

            self.debug(
                f"Found {len(endpoint_list)} endpoints for service {service_name}"
            )
            return endpoint_list

        except ApiException as e:
            if e.status == 404:
                self.debug(f"Endpoints for service {service_name} not found")
                return []
            else:
                self.error(f"Error getting endpoints for service {service_name}: {e}")
                raise ServiceDiscoveryError(
                    f"Failed to get endpoints for {service_name}: {e}"
                )
