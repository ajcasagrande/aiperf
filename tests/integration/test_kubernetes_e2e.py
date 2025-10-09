# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""End-to-end integration tests for Kubernetes deployment."""

import asyncio
import os
import time
from pathlib import Path

import pytest

from aiperf.common.config import EndpointConfig, ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType
from aiperf.kubernetes.orchestrator import KubernetesOrchestrator


@pytest.mark.integration
@pytest.mark.kubernetes
class TestKubernetesE2E:
    """End-to-end integration tests requiring a Kubernetes cluster."""

    @pytest.fixture
    def test_namespace(self):
        """Generate a unique test namespace."""
        import uuid

        return f"aiperf-test-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def user_config(self):
        """Create test user configuration."""
        return UserConfig(
            endpoint=EndpointConfig(
                url="http://vllm-service.default.svc.cluster.local:8000",
                model_names=["facebook/opt-125m"],
            ),
            input={"public_dataset": "sharegpt"},
            load_generator={"benchmark_duration": 30, "concurrency": 5},
        )

    @pytest.fixture
    def service_config(self, test_namespace):
        """Create test service configuration."""
        config = ServiceConfig()
        config.kubernetes.enabled = True
        config.kubernetes.namespace = test_namespace
        config.kubernetes.image = "aiperf:latest"
        config.kubernetes.cleanup_on_completion = True
        return config

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("RUN_K8S_TESTS"),
        reason="Requires Kubernetes cluster. Set RUN_K8S_TESTS=1 to run.",
    )
    async def test_full_deployment_lifecycle(
        self, user_config, service_config, test_namespace
    ):
        """Test complete deployment lifecycle."""
        orchestrator = KubernetesOrchestrator(
            user_config=user_config, service_config=service_config
        )

        try:
            # Deploy
            success = await orchestrator.deploy()
            assert success, "Deployment should succeed"

            # Verify namespace exists
            namespaces = orchestrator.resource_manager.core_api.list_namespace()
            namespace_names = [ns.metadata.name for ns in namespaces.items]
            assert test_namespace in namespace_names

            # Verify system controller pod exists
            pods = orchestrator.resource_manager.core_api.list_namespaced_pod(
                namespace=test_namespace
            )
            pod_names = [pod.metadata.name for pod in pods.items]
            assert any("system-controller" in name for name in pod_names)

            # Verify service exists
            services = orchestrator.resource_manager.core_api.list_namespaced_service(
                namespace=test_namespace
            )
            service_names = [svc.metadata.name for svc in services.items]
            assert "aiperf-system-controller" in service_names

        finally:
            # Cleanup
            await orchestrator.cleanup()

            # Verify cleanup
            await asyncio.sleep(5)
            namespaces = orchestrator.resource_manager.core_api.list_namespace()
            namespace_names = [ns.metadata.name for ns in namespaces.items]
            assert test_namespace not in namespace_names

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("RUN_K8S_TESTS"),
        reason="Requires Kubernetes cluster. Set RUN_K8S_TESTS=1 to run.",
    )
    async def test_pod_template_generation(self, service_config):
        """Test that pod templates are generated correctly."""
        from aiperf.kubernetes.templates import PodTemplateBuilder

        builder = PodTemplateBuilder(
            namespace="test-ns",
            image="aiperf:test",
            image_pull_policy="IfNotPresent",
            service_account="test-sa",
            system_controller_service="test-controller",
        )

        # Test each service type
        for service_type in [
            ServiceType.SYSTEM_CONTROLLER,
            ServiceType.DATASET_MANAGER,
            ServiceType.WORKER,
        ]:
            pod_spec = builder.build_pod_spec(
                service_type=service_type,
                service_id=f"{service_type.value}-test",
                config_map_name="test-config",
            )

            assert pod_spec["kind"] == "Pod"
            assert pod_spec["spec"]["containers"][0]["image"] == "aiperf:test"
            assert len(pod_spec["spec"]["containers"][0]["env"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("RUN_K8S_TESTS"),
        reason="Requires Kubernetes cluster. Set RUN_K8S_TESTS=1 to run.",
    )
    async def test_config_map_creation(self, user_config, service_config, test_namespace):
        """Test ConfigMap creation and retrieval."""
        from aiperf.kubernetes.config_serializer import ConfigSerializer
        from aiperf.kubernetes.resource_manager import KubernetesResourceManager

        resource_manager = KubernetesResourceManager(namespace=test_namespace)

        try:
            # Create namespace
            await resource_manager.create_namespace()

            # Create ConfigMap
            config_data = ConfigSerializer.serialize_to_configmap(
                user_config, service_config
            )
            await resource_manager.create_configmap("test-config", config_data)

            # Retrieve ConfigMap
            cm = resource_manager.core_api.read_namespaced_config_map(
                name="test-config", namespace=test_namespace
            )

            assert cm.data is not None
            assert "user_config.json" in cm.data
            assert "service_config.json" in cm.data

            # Verify deserialization works
            restored_user, restored_service = ConfigSerializer.deserialize_from_configmap(
                cm.data
            )
            assert restored_user.endpoint.url == user_config.endpoint.url

        finally:
            # Cleanup
            await resource_manager.cleanup_all(delete_namespace=True)


@pytest.mark.integration
class TestKubernetesServiceManager:
    """Integration tests for KubernetesServiceManager."""

    @pytest.mark.skipif(
        not os.getenv("RUN_K8S_TESTS"),
        reason="Requires Kubernetes cluster. Set RUN_K8S_TESTS=1 to run.",
    )
    def test_service_manager_initialization(self):
        """Test that KubernetesServiceManager can be initialized."""
        from aiperf.common.enums import ServiceRunType, ServiceType
        from aiperf.controller.kubernetes_service_manager import (
            KubernetesServiceManager,
        )
        from aiperf.kubernetes.resource_manager import KubernetesResourceManager
        from aiperf.kubernetes.templates import PodTemplateBuilder

        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"])
        )
        service_config = ServiceConfig()
        service_config.service_run_type = ServiceRunType.KUBERNETES

        resource_manager = KubernetesResourceManager(namespace="test")
        template_builder = PodTemplateBuilder(
            namespace="test",
            image="aiperf:test",
            image_pull_policy="IfNotPresent",
            service_account="test-sa",
            system_controller_service="test-controller",
        )

        manager = KubernetesServiceManager(
            required_services={ServiceType.DATASET_MANAGER: 1},
            service_config=service_config,
            user_config=user_config,
            resource_manager=resource_manager,
            template_builder=template_builder,
            config_map_name="test-config",
        )

        assert manager is not None
        assert manager.resource_manager == resource_manager
        assert manager.template_builder == template_builder
