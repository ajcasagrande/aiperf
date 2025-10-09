# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Comprehensive Kubernetes integration tests.

These tests require:
1. A running Kubernetes cluster (minikube, kind, or real cluster)
2. kubectl configured and accessible
3. Sufficient permissions to create namespaces, pods, services, etc.

Run with: RUN_K8S_TESTS=1 pytest tests/integration/test_kubernetes_integration.py -v
"""

import asyncio
import os
import uuid

import pytest

from aiperf.common.config import (
    EndpointConfig,
    LoadGeneratorConfig,
    ServiceConfig,
    UserConfig,
)
from aiperf.common.config.input_config import InputConfig
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.kubernetes.config_serializer import ConfigSerializer
from aiperf.kubernetes.orchestrator import KubernetesOrchestrator
from aiperf.kubernetes.resource_manager import KubernetesResourceManager
from aiperf.kubernetes.templates import PodTemplateBuilder


def requires_k8s_cluster():
    """Decorator to skip test if K8s cluster not available."""
    return pytest.mark.skipif(
        not os.getenv("RUN_K8S_TESTS"),
        reason="Requires Kubernetes cluster. Set RUN_K8S_TESTS=1 to run.",
    )


@pytest.mark.integration
@pytest.mark.kubernetes
class TestKubernetesResourceManager:
    """Test Kubernetes resource manager operations."""

    @pytest.fixture
    def test_namespace(self):
        """Generate unique test namespace."""
        return f"aiperf-test-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    async def resource_manager(self, test_namespace):
        """Create and cleanup resource manager."""
        manager = KubernetesResourceManager(namespace=test_namespace)
        yield manager
        # Cleanup after test
        await manager.cleanup_all(delete_namespace=True)

    @requires_k8s_cluster()
    @pytest.mark.asyncio
    async def test_namespace_creation(self, resource_manager, test_namespace):
        """Test namespace creation."""
        await resource_manager.create_namespace()

        # Verify namespace exists
        namespaces = resource_manager.core_api.list_namespace()
        namespace_names = [ns.metadata.name for ns in namespaces.items]
        assert test_namespace in namespace_names

    @requires_k8s_cluster()
    @pytest.mark.asyncio
    async def test_configmap_creation(self, resource_manager, test_namespace):
        """Test ConfigMap creation and retrieval."""
        await resource_manager.create_namespace()

        test_data = {
            "config.json": '{"test": "value"}',
            "data.txt": "test data",
        }

        await resource_manager.create_configmap("test-config", test_data)

        # Verify ConfigMap
        cm = resource_manager.core_api.read_namespaced_config_map(
            name="test-config", namespace=test_namespace
        )
        assert cm.data["config.json"] == test_data["config.json"]
        assert cm.data["data.txt"] == test_data["data.txt"]

    @requires_k8s_cluster()
    @pytest.mark.asyncio
    async def test_pod_creation_and_wait(self, resource_manager, test_namespace):
        """Test pod creation and waiting for ready state."""
        await resource_manager.create_namespace()

        pod_spec = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "test-pod",
                "namespace": test_namespace,
                "labels": {"app": "test"},
            },
            "spec": {
                "containers": [
                    {
                        "name": "test",
                        "image": "busybox:latest",
                        "command": ["sleep", "infinity"],
                    }
                ],
                "restartPolicy": "Never",
            },
        }

        pod_name = await resource_manager.create_pod(pod_spec)
        assert pod_name == "test-pod"

        # Wait for pod to be ready
        ready = await resource_manager.wait_for_pod_ready(pod_name, timeout=60)
        assert ready, "Pod should become ready"

    @requires_k8s_cluster()
    @pytest.mark.asyncio
    async def test_service_creation(self, resource_manager, test_namespace):
        """Test Kubernetes service creation."""
        await resource_manager.create_namespace()

        service_spec = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "test-service",
                "namespace": test_namespace,
            },
            "spec": {
                "selector": {"app": "test"},
                "ports": [{"port": 8000, "targetPort": 8000}],
                "type": "ClusterIP",
            },
        }

        await resource_manager.create_service(service_spec)

        # Verify service exists
        svc = resource_manager.core_api.read_namespaced_service(
            name="test-service", namespace=test_namespace
        )
        assert svc.metadata.name == "test-service"


@pytest.mark.integration
@pytest.mark.kubernetes
class TestKubernetesPodTemplates:
    """Test pod template generation."""

    @pytest.fixture
    def builder(self):
        """Create pod template builder."""
        return PodTemplateBuilder(
            namespace="test-ns",
            image="aiperf:test",
            image_pull_policy="IfNotPresent",
            service_account="test-sa",
            system_controller_service="test-svc",
        )

    def test_system_controller_pod_structure(self, builder):
        """Test system controller pod has correct structure."""
        pod = builder.build_pod_spec(
            ServiceType.SYSTEM_CONTROLLER, "sc-1", "config", "2", "2Gi"
        )

        # Verify structure
        assert pod["kind"] == "Pod"
        assert pod["metadata"]["name"] == "sc-1"
        assert pod["metadata"]["namespace"] == "test-ns"
        assert pod["metadata"]["labels"]["app"] == "aiperf"
        assert (
            pod["metadata"]["labels"]["service-type"]
            == ServiceType.SYSTEM_CONTROLLER.value
        )

        # Verify container config
        container = pod["spec"]["containers"][0]
        assert container["image"] == "aiperf:test"
        assert container["imagePullPolicy"] == "IfNotPresent"
        assert container["resources"]["limits"]["cpu"] == "2"
        assert container["resources"]["limits"]["memory"] == "2Gi"

        # Verify environment variables
        env_dict = {e["name"]: e["value"] for e in container["env"]}
        assert env_dict["AIPERF_SERVICE_TYPE"] == ServiceType.SYSTEM_CONTROLLER.value
        assert env_dict["AIPERF_SERVICE_ID"] == "sc-1"
        assert env_dict["AIPERF_CONFIG_MAP"] == "config"
        assert env_dict["AIPERF_NAMESPACE"] == "test-ns"

    def test_worker_pod_structure(self, builder):
        """Test worker pod has correct structure."""
        pod = builder.build_pod_spec(
            ServiceType.WORKER, "worker-0", "config", "4", "4Gi"
        )

        container = pod["spec"]["containers"][0]
        env_dict = {e["name"]: e["value"] for e in container["env"]}

        assert env_dict["AIPERF_SERVICE_TYPE"] == ServiceType.WORKER.value
        assert env_dict["AIPERF_SERVICE_ID"] == "worker-0"
        assert container["resources"]["limits"]["cpu"] == "4"
        assert container["resources"]["limits"]["memory"] == "4Gi"

    def test_service_account_rbac(self, builder):
        """Test service account and RBAC resources."""
        sa, role, binding = builder.build_rbac_resources()

        # Verify ServiceAccount
        assert sa["kind"] == "ServiceAccount"
        assert sa["metadata"]["name"] == "test-sa"

        # Verify ClusterRole
        assert role["kind"] == "ClusterRole"
        assert len(role["rules"]) > 0

        # Check for required permissions
        all_resources = []
        all_verbs = []
        for rule in role["rules"]:
            all_resources.extend(rule["resources"])
            all_verbs.extend(rule["verbs"])

        assert "pods" in all_resources
        assert "services" in all_resources
        assert "configmaps" in all_resources
        assert "create" in all_verbs
        assert "get" in all_verbs
        assert "list" in all_verbs

        # Verify ClusterRoleBinding
        assert binding["kind"] == "ClusterRoleBinding"
        assert binding["subjects"][0]["name"] == "test-sa"
        assert binding["roleRef"]["name"] == role["metadata"]["name"]


@pytest.mark.integration
@pytest.mark.kubernetes
class TestKubernetesOrchestrator:
    """Test Kubernetes orchestrator deployment."""

    @pytest.fixture
    def test_namespace(self):
        """Generate unique test namespace."""
        return f"aiperf-test-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def user_config(self):
        """Create test user configuration."""
        return UserConfig(
            endpoint=EndpointConfig(
                url="http://mock-llm-service.default.svc.cluster.local:8000",
                model_names=["mock-model"],
                endpoint_type="chat",
                streaming=True,
            ),
            input=InputConfig(public_dataset="sharegpt"),
            loadgen=LoadGeneratorConfig(
                benchmark_duration=30,
                concurrency=5,
            ),
        )

    @pytest.fixture
    def service_config(self, test_namespace):
        """Create test service configuration."""
        config = ServiceConfig()
        config.service_run_type = ServiceRunType.KUBERNETES
        config.kubernetes.enabled = True
        config.kubernetes.namespace = test_namespace
        config.kubernetes.image = "aiperf:latest"
        config.kubernetes.image_pull_policy = "IfNotPresent"
        config.kubernetes.cleanup_on_completion = True
        return config

    @requires_k8s_cluster()
    @pytest.mark.asyncio
    async def test_deployment_creates_resources(
        self, user_config, service_config, test_namespace
    ):
        """Test that deployment creates all required resources."""
        orchestrator = KubernetesOrchestrator(
            user_config=user_config, service_config=service_config
        )

        try:
            # Deploy
            success = await orchestrator.deploy()
            assert success, "Deployment should succeed"

            # Verify namespace
            namespaces = orchestrator.resource_manager.core_api.list_namespace()
            namespace_names = [ns.metadata.name for ns in namespaces.items]
            assert test_namespace in namespace_names

            # Verify ConfigMap
            cm = orchestrator.resource_manager.core_api.read_namespaced_config_map(
                name="aiperf-config", namespace=test_namespace
            )
            assert cm.data is not None
            assert "user_config.json" in cm.data
            assert "service_config.json" in cm.data

            # Verify system controller pod
            pods = orchestrator.resource_manager.core_api.list_namespaced_pod(
                namespace=test_namespace
            )
            pod_names = [pod.metadata.name for pod in pods.items]
            assert any("system-controller" in name for name in pod_names)

            # Verify services
            services = orchestrator.resource_manager.core_api.list_namespaced_service(
                namespace=test_namespace
            )
            service_names = [svc.metadata.name for svc in services.items]
            assert "aiperf-system-controller" in service_names

        finally:
            # Cleanup
            await orchestrator.cleanup()

    @requires_k8s_cluster()
    @pytest.mark.asyncio
    async def test_deployment_cleanup(
        self, user_config, service_config, test_namespace
    ):
        """Test that cleanup removes all resources."""
        orchestrator = KubernetesOrchestrator(
            user_config=user_config, service_config=service_config
        )

        try:
            # Deploy
            success = await orchestrator.deploy()
            assert success

            # Cleanup
            await orchestrator.cleanup()

            # Wait for cleanup
            await asyncio.sleep(5)

            # Verify namespace is gone
            namespaces = orchestrator.resource_manager.core_api.list_namespace()
            namespace_names = [ns.metadata.name for ns in namespaces.items]
            assert test_namespace not in namespace_names

        except Exception:
            # Ensure cleanup even if test fails
            await orchestrator.cleanup()
            raise


@pytest.mark.integration
@pytest.mark.kubernetes
class TestConfigSerialization:
    """Test configuration serialization for Kubernetes."""

    def test_config_roundtrip(self):
        """Test that configs survive serialization roundtrip."""
        user_config = UserConfig(
            endpoint=EndpointConfig(
                url="http://test:8000",
                model_names=["model1", "model2"],
            ),
            loadgen=LoadGeneratorConfig(
                concurrency=100,
                benchmark_duration=300,
            ),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = "test-ns"
        service_config.kubernetes.worker_cpu = "8"
        service_config.kubernetes.worker_memory = "16Gi"

        # Serialize
        data = ConfigSerializer.serialize_to_configmap(user_config, service_config)

        # Deserialize
        restored_user, restored_service = ConfigSerializer.deserialize_from_configmap(
            data
        )

        # Verify critical fields
        assert restored_user.endpoint.url == user_config.endpoint.url
        assert restored_user.endpoint.model_names == user_config.endpoint.model_names
        assert restored_user.loadgen.concurrency == user_config.loadgen.concurrency
        assert restored_service.kubernetes.enabled == service_config.kubernetes.enabled
        assert (
            restored_service.kubernetes.namespace == service_config.kubernetes.namespace
        )
        assert (
            restored_service.kubernetes.worker_cpu
            == service_config.kubernetes.worker_cpu
        )


def test_module_imports():
    """Test that all Kubernetes modules can be imported."""
    from aiperf.kubernetes import (
        KubernetesOrchestrator,
        KubernetesResourceManager,
        PodTemplateBuilder,
    )
    from aiperf.kubernetes.config_serializer import ConfigSerializer
    from aiperf.kubernetes.entrypoint import main
    from aiperf.orchestrator.kubernetes_cli_bridge import KubernetesCliBridge
    from aiperf.orchestrator.kubernetes_runner import run_aiperf_kubernetes

    assert all(
        [
            KubernetesOrchestrator,
            KubernetesResourceManager,
            PodTemplateBuilder,
            ConfigSerializer,
            main,
            KubernetesCliBridge,
            run_aiperf_kubernetes,
        ]
    )
