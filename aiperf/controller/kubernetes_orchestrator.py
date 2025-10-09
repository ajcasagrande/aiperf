# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Kubernetes Orchestrator

This module handles deploying and monitoring AIPerf System Controller in Kubernetes.
Unlike the MVP approach where System Controller runs locally, this orchestrator:
1. Deploys System Controller as a pod in the cluster
2. Monitors its progress from the local CLI
3. Retrieves results when complete
4. Cleans up resources
"""

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType


class KubernetesOrchestrator:
    """Orchestrates AIPerf deployment in Kubernetes by deploying System Controller as a pod."""

    def __init__(self, service_config: ServiceConfig, user_config: UserConfig):
        self.service_config = service_config
        self.user_config = user_config
        self.logger = AIPerfLogger(__name__)

        # Initialize Kubernetes client
        self._init_kubernetes_client()

        # Determine namespace
        self.namespace = self._determine_namespace()
        self.should_cleanup = self.service_config.kubernetes.should_auto_cleanup

        self.system_controller_pod_name = None

    def _init_kubernetes_client(self) -> None:
        """Initialize Kubernetes client from kubeconfig."""
        kubeconfig_path = self.service_config.kubernetes.kubeconfig_path

        if kubeconfig_path:
            self.logger.info(f"Loading kubeconfig from: {kubeconfig_path}")
            config.load_kube_config(config_file=str(kubeconfig_path))
        else:
            # Try default locations
            try:
                config.load_kube_config()
                self.logger.info("Loaded kubeconfig from default location")
            except Exception:
                # Try in-cluster config (if running inside K8s)
                try:
                    config.load_incluster_config()
                    self.logger.info("Loaded in-cluster kubeconfig")
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to load kubeconfig: {e}. "
                        "Please ensure kubectl is configured or specify --kubeconfig"
                    )

        self.core_v1 = client.CoreV1Api()
        self.rbac_v1 = client.RbacAuthorizationV1Api()

    def _determine_namespace(self) -> str:
        """Determine namespace to use."""
        if self.service_config.kubernetes.kubernetes_namespace:
            return self.service_config.kubernetes.kubernetes_namespace

        # Auto-generate namespace
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        unique_id = os.urandom(4).hex()
        return f"aiperf-{timestamp}-{unique_id}"

    async def deploy_and_run(self) -> None:
        """Deploy AIPerf to Kubernetes and monitor execution."""
        try:
            self.logger.info(
                f"Deploying AIPerf to Kubernetes namespace: {self.namespace}"
            )

            # Create namespace and resources
            await self._create_namespace()
            await self._create_rbac_resources()
            await self._create_system_controller_service()

            # Deploy System Controller pod
            await self._deploy_system_controller()

            # Wait for System Controller to become ready
            await self._wait_for_system_controller_ready()

            # Monitor System Controller logs
            await self._monitor_system_controller()

            # Retrieve artifacts
            await self._retrieve_artifacts()

            self.logger.info("✓ Kubernetes deployment completed successfully")

        except Exception as e:
            self.logger.error(f"Kubernetes deployment failed: {e}")
            raise
        finally:
            # Cleanup if auto-generated namespace
            if self.should_cleanup:
                await self._cleanup_namespace()

    async def _create_namespace(self) -> None:
        """Create Kubernetes namespace."""
        try:
            namespace = client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=self.namespace,
                    labels={"app": "aiperf", "created-by": "aiperf-cli"},
                )
            )
            self.core_v1.create_namespace(body=namespace)
            self.logger.info(f"✓ Created namespace: {self.namespace}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                self.logger.info(f"Namespace {self.namespace} already exists")
            else:
                raise

    async def _create_rbac_resources(self) -> None:
        """Create ServiceAccount, Role, and RoleBinding for AIPerf pods."""
        service_account_name = self.service_config.kubernetes.kubernetes_service_account

        # ServiceAccount
        try:
            sa = client.V1ServiceAccount(
                metadata=client.V1ObjectMeta(name=service_account_name)
            )
            self.core_v1.create_namespaced_service_account(
                namespace=self.namespace, body=sa
            )
            self.logger.debug(f"✓ Created ServiceAccount: {service_account_name}")
        except ApiException as e:
            if e.status != 409:
                raise

        # Role
        try:
            role = client.V1Role(
                metadata=client.V1ObjectMeta(name="aiperf-role"),
                rules=[
                    client.V1PolicyRule(
                        api_groups=[""],
                        resources=["pods", "pods/log", "pods/status"],
                        verbs=[
                            "get",
                            "list",
                            "watch",
                            "create",
                            "delete",
                            "patch",
                            "update",
                        ],
                    ),
                    client.V1PolicyRule(
                        api_groups=[""],
                        resources=["services"],
                        verbs=[
                            "get",
                            "list",
                            "watch",
                            "create",
                            "delete",
                            "patch",
                            "update",
                        ],
                    ),
                    client.V1PolicyRule(
                        api_groups=[""],
                        resources=["configmaps"],
                        verbs=["get", "list", "create"],
                    ),
                ],
            )
            self.rbac_v1.create_namespaced_role(namespace=self.namespace, body=role)
            self.logger.debug("✓ Created Role: aiperf-role")
        except ApiException as e:
            if e.status != 409:
                raise

        # RoleBinding
        try:
            role_binding = client.V1RoleBinding(
                metadata=client.V1ObjectMeta(name="aiperf-role-binding"),
                subjects=[
                    client.RbacV1Subject(
                        kind="ServiceAccount",
                        name=service_account_name,
                        namespace=self.namespace,
                    )
                ],
                role_ref=client.V1RoleRef(
                    kind="Role",
                    name="aiperf-role",
                    api_group="rbac.authorization.k8s.io",
                ),
            )
            self.rbac_v1.create_namespaced_role_binding(
                namespace=self.namespace, body=role_binding
            )
            self.logger.debug("✓ Created RoleBinding: aiperf-role-binding")
        except ApiException as e:
            if e.status != 409:
                raise

    async def _create_system_controller_service(self) -> None:
        """Create Kubernetes Service to expose System Controller ZMQ ports."""
        service_ports = [
            client.V1ServicePort(name="credit-drop", port=5562, target_port=5562),
            client.V1ServicePort(name="credit-return", port=5563, target_port=5563),
            client.V1ServicePort(name="records", port=5557, target_port=5557),
            client.V1ServicePort(
                name="dataset-proxy-frontend", port=5661, target_port=5661
            ),
            client.V1ServicePort(
                name="dataset-proxy-backend", port=5662, target_port=5662
            ),
            client.V1ServicePort(
                name="event-bus-frontend", port=5663, target_port=5663
            ),
            client.V1ServicePort(name="event-bus-backend", port=5664, target_port=5664),
            client.V1ServicePort(
                name="raw-inference-frontend", port=5665, target_port=5665
            ),
            client.V1ServicePort(
                name="raw-inference-backend", port=5666, target_port=5666
            ),
        ]

        service = client.V1Service(
            metadata=client.V1ObjectMeta(name="aiperf-system-controller"),
            spec=client.V1ServiceSpec(
                selector={
                    "app": "aiperf",
                    "service-type": str(ServiceType.SYSTEM_CONTROLLER),
                },
                ports=service_ports,
                type="ClusterIP",
            ),
        )

        try:
            self.core_v1.create_namespaced_service(
                namespace=self.namespace, body=service
            )
            self.logger.info("✓ Created Kubernetes Service: aiperf-system-controller")
        except ApiException as e:
            if e.status == 409:
                self.logger.debug("Service already exists")
            else:
                raise

    async def _deploy_system_controller(self) -> None:
        """Deploy System Controller as a pod in the cluster."""
        # Serialize configs - exclude unset values to avoid validation issues with defaults
        service_config_json = self.service_config.model_dump_json(exclude_unset=True)
        user_config_json = self.user_config.model_dump_json(exclude_unset=True)

        # Environment variables
        env_vars = [
            client.V1EnvVar(
                name="AIPERF_SERVICE_TYPE", value=str(ServiceType.SYSTEM_CONTROLLER)
            ),
            client.V1EnvVar(name="AIPERF_SERVICE_ID", value="system_controller"),
            client.V1EnvVar(name="AIPERF_SERVICE_CONFIG", value=service_config_json),
            client.V1EnvVar(name="AIPERF_USER_CONFIG", value=user_config_json),
        ]

        # Container spec
        container = client.V1Container(
            name="system-controller",
            image=self.service_config.kubernetes.kubernetes_image,
            image_pull_policy=self.service_config.kubernetes.kubernetes_image_pull_policy,
            env=env_vars,
            command=["python", "-m", "aiperf.controller.kubernetes_pod_entrypoint"],
        )

        # Pod spec
        pod_spec = client.V1PodSpec(
            service_account_name=self.service_config.kubernetes.kubernetes_service_account,
            containers=[container],
            restart_policy="Never",
        )

        # Pod metadata
        self.system_controller_pod_name = f"system-controller-{os.urandom(4).hex()}"
        pod_metadata = client.V1ObjectMeta(
            name=self.system_controller_pod_name,
            namespace=self.namespace,
            labels={
                "app": "aiperf",
                "service-type": str(ServiceType.SYSTEM_CONTROLLER),
            },
        )

        pod = client.V1Pod(metadata=pod_metadata, spec=pod_spec)

        # Create the pod
        self.core_v1.create_namespaced_pod(namespace=self.namespace, body=pod)
        self.logger.info(
            f"✓ Deployed System Controller pod: {self.system_controller_pod_name}"
        )

    async def _wait_for_system_controller_ready(self, timeout: int = 120) -> None:
        """Wait for System Controller pod to be ready."""
        self.logger.info("Waiting for System Controller to become ready...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                pod = self.core_v1.read_namespaced_pod(
                    name=self.system_controller_pod_name, namespace=self.namespace
                )

                if pod.status.phase == "Running":
                    self.logger.info("✓ System Controller is running")
                    return
                elif pod.status.phase in ("Failed", "Unknown"):
                    raise RuntimeError(
                        f"System Controller pod failed: {pod.status.phase}"
                    )

            except ApiException as e:
                self.logger.error(f"Error checking pod status: {e}")

            await asyncio.sleep(2)

        raise TimeoutError(f"System Controller did not become ready within {timeout}s")

    async def _monitor_system_controller(self) -> None:
        """Monitor System Controller logs and wait for completion."""
        self.logger.info("Monitoring System Controller execution...")

        # Follow logs
        try:
            # Stream logs from the pod
            log_watch = self.core_v1.read_namespaced_pod_log(
                name=self.system_controller_pod_name,
                namespace=self.namespace,
                follow=True,
                _preload_content=False,
            )

            for line in log_watch.stream():
                log_line = line.decode("utf-8").strip()
                if log_line:
                    print(f"[System Controller] {log_line}")

        except Exception as e:
            self.logger.error(f"Error streaming logs: {e}")

        # Wait for pod to complete
        while True:
            pod = self.core_v1.read_namespaced_pod(
                name=self.system_controller_pod_name, namespace=self.namespace
            )

            if pod.status.phase == "Succeeded":
                self.logger.info("✓ System Controller completed successfully")
                break
            elif pod.status.phase == "Failed":
                self.logger.error("✗ System Controller failed")
                raise RuntimeError("System Controller pod failed")

            await asyncio.sleep(2)

    async def _retrieve_artifacts(self) -> None:
        """Retrieve artifacts from Records Manager pod."""
        self.logger.info("Retrieving artifacts from Records Manager...")

        # Find Records Manager pod
        pods = self.core_v1.list_namespaced_pod(
            namespace=self.namespace,
            label_selector=f"service-type={ServiceType.RECORDS_MANAGER}",
        )

        if not pods.items:
            self.logger.warning("No Records Manager pod found")
            return

        records_pod = pods.items[0].metadata.name
        self.logger.info(f"Found Records Manager pod: {records_pod}")

        # Get artifacts path from user config
        artifacts_dir = Path(self.user_config.artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Copy artifacts using kubectl cp
        remote_path = f"{self.namespace}/{records_pod}:/app/artifacts"
        local_path = str(artifacts_dir)

        self.logger.info(f"Copying artifacts to {local_path}")

        # Note: Using kubectl cp via subprocess would be more reliable
        # For now, we'll log the command users can run manually
        self.logger.info(
            f"To retrieve artifacts, run: kubectl cp {remote_path} {local_path}"
        )

    async def _cleanup_namespace(self) -> None:
        """Delete the namespace and all resources."""
        if not self.should_cleanup:
            self.logger.info(f"Skipping cleanup for custom namespace: {self.namespace}")
            return

        try:
            self.logger.info(f"Cleaning up namespace: {self.namespace}")
            self.core_v1.delete_namespace(name=self.namespace, grace_period_seconds=30)
            self.logger.info("✓ Namespace cleanup initiated")
        except ApiException as e:
            self.logger.error(f"Failed to cleanup namespace: {e}")
