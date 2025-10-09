# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Kubernetes resource management using the Kubernetes Python API."""

import asyncio
import time
from pathlib import Path
from typing import Any

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from aiperf.common.aiperf_logger import AIPerfLogger


class KubernetesResourceManager:
    """Manages Kubernetes resources via the Kubernetes Python API."""

    def __init__(self, namespace: str, kubeconfig: Path | None = None):
        self.namespace = namespace
        self.logger = AIPerfLogger(__name__)

        # Load kubeconfig
        if kubeconfig:
            config.load_kube_config(config_file=str(kubeconfig))
        else:
            try:
                config.load_kube_config()
            except Exception:
                # Try in-cluster config if kubeconfig fails
                config.load_incluster_config()

        # Initialize API clients
        self.core_api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()
        self.rbac_api = client.RbacAuthorizationV1Api()

        # Track created resources for cleanup
        self.created_pods: list[str] = []
        self.created_services: list[str] = []
        self.created_configmaps: list[str] = []

    async def create_namespace(self) -> None:
        """Create the namespace if it doesn't exist."""
        try:
            self.core_api.read_namespace(name=self.namespace)
            self.logger.info(f"Using existing namespace: {self.namespace}")
        except ApiException as e:
            if e.status == 404:
                namespace_spec = {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {"name": self.namespace},
                }
                self.core_api.create_namespace(body=namespace_spec)
                self.logger.info(f"Created namespace: {self.namespace}")
            else:
                raise

    async def create_rbac_resources(
        self,
        service_account: dict[str, Any],
        cluster_role: dict[str, Any],
        cluster_role_binding: dict[str, Any],
    ) -> None:
        """Create RBAC resources."""
        # Create ServiceAccount
        try:
            self.core_api.create_namespaced_service_account(
                namespace=self.namespace, body=service_account
            )
            self.logger.info(
                f"Created ServiceAccount: {service_account['metadata']['name']}"
            )
        except ApiException as e:
            if e.status != 409:  # Ignore if already exists
                raise

        # Create ClusterRole
        try:
            self.rbac_api.create_cluster_role(body=cluster_role)
            self.logger.info(f"Created ClusterRole: {cluster_role['metadata']['name']}")
        except ApiException as e:
            if e.status != 409:
                raise

        # Create ClusterRoleBinding
        try:
            self.rbac_api.create_cluster_role_binding(body=cluster_role_binding)
            self.logger.info(
                f"Created ClusterRoleBinding: {cluster_role_binding['metadata']['name']}"
            )
        except ApiException as e:
            if e.status != 409:
                raise

    async def create_configmap(
        self, name: str, data: dict[str, str]
    ) -> None:
        """Create a ConfigMap."""
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": name, "namespace": self.namespace},
            "data": data,
        }

        try:
            self.core_api.create_namespaced_config_map(
                namespace=self.namespace, body=configmap
            )
            self.created_configmaps.append(name)
            self.logger.info(f"Created ConfigMap: {name}")
        except ApiException as e:
            if e.status == 409:
                # Update if exists
                self.core_api.patch_namespaced_config_map(
                    name=name, namespace=self.namespace, body=configmap
                )
                self.logger.info(f"Updated existing ConfigMap: {name}")
            else:
                raise

    async def create_service(self, service_spec: dict[str, Any]) -> None:
        """Create a Kubernetes service."""
        service_name = service_spec["metadata"]["name"]
        try:
            self.core_api.create_namespaced_service(
                namespace=self.namespace, body=service_spec
            )
            self.created_services.append(service_name)
            self.logger.info(f"Created Service: {service_name}")
        except ApiException as e:
            if e.status != 409:
                raise

    async def create_pod(self, pod_spec: dict[str, Any]) -> str:
        """Create a pod and return its name."""
        pod_name = pod_spec["metadata"]["name"]
        try:
            self.core_api.create_namespaced_pod(namespace=self.namespace, body=pod_spec)
            self.created_pods.append(pod_name)
            self.logger.debug(f"Created pod: {pod_name}")
            return pod_name
        except ApiException as e:
            if e.status == 409:
                self.logger.warning(f"Pod {pod_name} already exists")
                return pod_name
            else:
                raise

    async def wait_for_pod_ready(
        self, pod_name: str, timeout: float = 300
    ) -> bool:
        """Wait for a pod to be in Running state."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                pod = self.core_api.read_namespaced_pod(
                    name=pod_name, namespace=self.namespace
                )
                if pod.status.phase == "Running":
                    self.logger.debug(f"Pod {pod_name} is running")
                    return True
                elif pod.status.phase in ["Failed", "Unknown"]:
                    self.logger.error(f"Pod {pod_name} in {pod.status.phase} state")
                    return False
            except ApiException:
                pass

            await asyncio.sleep(2)

        self.logger.error(f"Pod {pod_name} did not become ready within {timeout}s")
        return False

    async def get_pod_logs(self, pod_name: str, tail_lines: int = 100) -> str:
        """Get logs from a pod."""
        try:
            return self.core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace,
                tail_lines=tail_lines,
            )
        except ApiException as e:
            self.logger.error(f"Failed to get logs for {pod_name}: {e}")
            return ""

    async def copy_from_pod(
        self, pod_name: str, src_path: str, dest_path: Path
    ) -> bool:
        """Copy files from pod to local filesystem."""
        try:
            # Use kubectl exec tar to copy files
            import subprocess

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                "kubectl",
                "exec",
                "-n",
                self.namespace,
                pod_name,
                "--",
                "tar",
                "cf",
                "-",
                "-C",
                str(Path(src_path).parent),
                Path(src_path).name,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                self.logger.error(f"Failed to tar files: {stderr.decode()}")
                return False

            # Extract tar locally
            extract_cmd = ["tar", "xf", "-", "-C", str(dest_path.parent)]
            extract_process = await asyncio.create_subprocess_exec(
                *extract_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            await extract_process.communicate(input=stdout)

            if extract_process.returncode != 0:
                self.logger.error("Failed to extract tar archive")
                return False

            self.logger.info(f"Copied {src_path} from {pod_name} to {dest_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to copy files from pod: {e}")
            return False

    async def delete_pod(self, pod_name: str) -> None:
        """Delete a pod."""
        try:
            self.core_api.delete_namespaced_pod(
                name=pod_name, namespace=self.namespace
            )
            self.logger.debug(f"Deleted pod: {pod_name}")
        except ApiException as e:
            if e.status != 404:
                self.logger.warning(f"Failed to delete pod {pod_name}: {e}")

    async def cleanup_all(self, delete_namespace: bool = False) -> None:
        """Cleanup all created resources."""
        self.logger.info("Cleaning up Kubernetes resources...")

        # Delete pods
        for pod_name in self.created_pods:
            await self.delete_pod(pod_name)

        # Delete services
        for service_name in self.created_services:
            try:
                self.core_api.delete_namespaced_service(
                    name=service_name, namespace=self.namespace
                )
                self.logger.debug(f"Deleted service: {service_name}")
            except ApiException:
                pass

        # Delete configmaps
        for cm_name in self.created_configmaps:
            try:
                self.core_api.delete_namespaced_config_map(
                    name=cm_name, namespace=self.namespace
                )
                self.logger.debug(f"Deleted configmap: {cm_name}")
            except ApiException:
                pass

        # Delete namespace if requested
        if delete_namespace:
            try:
                self.core_api.delete_namespace(name=self.namespace)
                self.logger.info(f"Deleted namespace: {self.namespace}")
            except ApiException:
                pass

        # Cleanup ClusterRole and ClusterRoleBinding
        try:
            self.rbac_api.delete_cluster_role(name=f"aiperf-role-{self.namespace}")
            self.rbac_api.delete_cluster_role_binding(
                name=f"aiperf-binding-{self.namespace}"
            )
        except ApiException:
            pass

        self.logger.info("Cleanup complete")
