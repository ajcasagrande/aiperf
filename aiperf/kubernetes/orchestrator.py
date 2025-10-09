# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Kubernetes orchestrator for deploying AIPerf on K8s clusters."""

import asyncio
import time
from datetime import datetime
from pathlib import Path

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.config.zmq_config import ZMQTCPConfig
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.kubernetes.config_serializer import ConfigSerializer
from aiperf.kubernetes.resource_manager import KubernetesResourceManager
from aiperf.kubernetes.templates import PodTemplateBuilder


class KubernetesOrchestrator:
    """Orchestrates AIPerf deployment on Kubernetes clusters."""

    def __init__(
        self,
        user_config: UserConfig,
        service_config: ServiceConfig,
    ):
        self.user_config = user_config
        self.service_config = service_config
        self.logger = AIPerfLogger(__name__)

        # Generate namespace if not specified
        if not service_config.kubernetes.namespace:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.namespace = f"aiperf-{timestamp}"
            self.auto_generated_namespace = True
        else:
            self.namespace = service_config.kubernetes.namespace
            self.auto_generated_namespace = False

        # Initialize resource manager
        self.resource_manager = KubernetesResourceManager(
            namespace=self.namespace,
            kubeconfig=service_config.kubernetes.kubeconfig,
        )

        # Service names
        self.system_controller_service = "aiperf-system-controller"
        self.config_map_name = "aiperf-config"

        # Template builder
        self.template_builder = PodTemplateBuilder(
            namespace=self.namespace,
            image=service_config.kubernetes.image,
            image_pull_policy=service_config.kubernetes.image_pull_policy,
            service_account=service_config.kubernetes.service_account,
            system_controller_service=self.system_controller_service,
        )

    async def deploy(self) -> bool:
        """Deploy AIPerf to Kubernetes cluster."""
        try:
            self.logger.info(f"Deploying AIPerf to namespace: {self.namespace}")

            # Create namespace
            await self.resource_manager.create_namespace()

            # Create RBAC resources
            sa, role, binding = self.template_builder.build_rbac_resources()
            await self.resource_manager.create_rbac_resources(sa, role, binding)

            # Configure ZMQ TCP for K8s
            await self._configure_zmq_for_kubernetes()

            # Serialize configuration to ConfigMap
            config_data = ConfigSerializer.serialize_to_configmap(
                self.user_config, self.service_config
            )
            await self.resource_manager.create_configmap(
                self.config_map_name, config_data
            )

            # Deploy system controller pod
            await self._deploy_system_controller()

            # Create services for ZMQ communication
            sc_service = self.template_builder.build_system_controller_service()
            await self.resource_manager.create_service(sc_service)

            tm_service = self.template_builder.build_timing_manager_service()
            await self.resource_manager.create_service(tm_service)

            rm_service = self.template_builder.build_records_manager_service()
            await self.resource_manager.create_service(rm_service)

            self.logger.info("AIPerf deployment complete")
            return True

        except Exception as e:
            self.logger.error(f"Failed to deploy AIPerf: {e}")
            await self.cleanup()
            return False

    async def _configure_zmq_for_kubernetes(self) -> None:
        """Configure ZMQ to use TCP with Kubernetes service DNS."""
        if not self.service_config.zmq_tcp:
            # Create ZMQ TCP config pointing to system controller service
            self.service_config.zmq_tcp = ZMQTCPConfig(
                host=f"{self.system_controller_service}.{self.namespace}.svc.cluster.local"
            )
            self.service_config.zmq_ipc = None

        # Force Kubernetes service run type
        self.service_config.service_run_type = ServiceRunType.KUBERNETES

    async def _deploy_system_controller(self) -> None:
        """Deploy the system controller pod."""
        self.logger.info("Deploying system controller pod")

        pod_spec = self.template_builder.build_pod_spec(
            service_type=ServiceType.SYSTEM_CONTROLLER,
            service_id="system-controller",
            config_map_name=self.config_map_name,
            cpu="2",
            memory="2Gi",
        )

        pod_name = await self.resource_manager.create_pod(pod_spec)

        # Wait for system controller to be ready
        ready = await self.resource_manager.wait_for_pod_ready(pod_name, timeout=300)
        if not ready:
            raise RuntimeError("System controller pod failed to start")

        self.logger.info("System controller pod is ready")

    async def wait_for_completion(self, timeout: float = 3600) -> bool:
        """Wait for benchmark to complete."""
        self.logger.info("Waiting for benchmark to complete...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check if system controller pod has completed
            try:
                pod = self.resource_manager.core_api.read_namespaced_pod(
                    name="system-controller", namespace=self.namespace
                )

                if pod.status.phase in ["Succeeded", "Failed"]:
                    self.logger.info(f"Benchmark completed: {pod.status.phase}")
                    return pod.status.phase == "Succeeded"

            except Exception as e:
                self.logger.warning(f"Error checking pod status: {e}")

            await asyncio.sleep(10)

        self.logger.error("Benchmark did not complete within timeout")
        return False

    async def retrieve_artifacts(self, local_dir: Path) -> bool:
        """Retrieve artifacts from records manager pod to local filesystem."""
        self.logger.info("Retrieving artifacts from cluster...")

        try:
            # Find records manager pod
            pods = self.resource_manager.core_api.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"service-type={ServiceType.RECORDS_MANAGER.value}",
            )

            if not pods.items:
                self.logger.error("Records manager pod not found")
                return False

            records_pod = pods.items[0].metadata.name

            # Copy artifacts from pod
            src_path = str(self.user_config.output.artifact_directory)
            success = await self.resource_manager.copy_from_pod(
                pod_name=records_pod,
                src_path=src_path,
                dest_path=local_dir,
            )

            if success:
                self.logger.info(f"Artifacts retrieved to {local_dir}")

            return success

        except Exception as e:
            self.logger.error(f"Failed to retrieve artifacts: {e}")
            return False

    async def cleanup(self) -> None:
        """Cleanup Kubernetes resources."""
        if self.service_config.kubernetes.cleanup_on_completion or self.auto_generated_namespace:
            self.logger.info("Cleaning up Kubernetes resources...")
            await self.resource_manager.cleanup_all(
                delete_namespace=self.auto_generated_namespace
            )
        else:
            self.logger.info(
                f"Skipping cleanup (namespace: {self.namespace}). "
                "Resources remain in cluster for debugging."
            )

    async def get_logs(self, service_type: ServiceType | None = None) -> dict[str, str]:
        """Get logs from pods."""
        logs = {}

        try:
            label_selector = "app=aiperf"
            if service_type:
                label_selector += f",service-type={service_type.value}"

            pods = self.resource_manager.core_api.list_namespaced_pod(
                namespace=self.namespace, label_selector=label_selector
            )

            for pod in pods.items:
                pod_name = pod.metadata.name
                pod_logs = await self.resource_manager.get_pod_logs(
                    pod_name, tail_lines=100
                )
                logs[pod_name] = pod_logs

        except Exception as e:
            self.logger.error(f"Failed to get logs: {e}")

        return logs
