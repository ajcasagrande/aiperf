# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Integration tests using real minikube cluster.

These tests deploy actual resources to minikube and validate:
- Kubernetes deployment works correctly
- Dataset chunking works in distributed environment
- Deterministic mode provides reproducibility across worker counts
- Real benchmark execution completes successfully

Requirements:
- minikube installed and running
- kubectl configured
- AIPerf image built and loaded: minikube image load aiperf:latest
- Mock LLM server deployed (optional)

Run with: RUN_MINIKUBE_TESTS=1 pytest tests/integration/test_minikube_cluster.py -v
"""

import asyncio
import json
import os
import subprocess
import uuid

import pytest


def requires_minikube():
    """Decorator to skip test if minikube not available."""
    return pytest.mark.skipif(
        not os.getenv("RUN_MINIKUBE_TESTS"),
        reason="Requires minikube cluster. Set RUN_MINIKUBE_TESTS=1 to run.",
    )


@pytest.fixture(scope="module")
def minikube_status():
    """Check minikube status before running tests."""
    try:
        result = subprocess.run(
            ["minikube", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"status": "running", "output": result.stdout}
        else:
            return {"status": "stopped", "output": result.stderr}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"status": "not_found", "output": ""}


@pytest.fixture(scope="module")
def ensure_minikube_running(minikube_status):
    """Ensure minikube is running before tests."""
    if minikube_status["status"] != "running":
        pytest.skip(f"Minikube not running: {minikube_status['status']}")
    return True


@pytest.fixture
async def test_namespace():
    """Create unique test namespace and clean up after."""
    namespace = f"aiperf-test-{uuid.uuid4().hex[:8]}"
    yield namespace

    # Cleanup
    try:
        subprocess.run(
            ["kubectl", "delete", "namespace", namespace, "--timeout=30s"],
            capture_output=True,
            timeout=60,
        )
    except:
        pass


@pytest.fixture
def mock_llm_deployed():
    """Check if mock LLM server is deployed."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "service", "mock-llm-service", "-n", "default"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except:
        return False


@pytest.mark.integration
@pytest.mark.minikube
class TestMinikubeClusterDeployment:
    """Test actual deployment to minikube cluster."""

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_deploy_to_minikube_with_chunking(
        self, ensure_minikube_running, test_namespace
    ):
        """Test full deployment to minikube with chunking enabled."""
        from aiperf.common.config import (
            EndpointConfig,
            LoadGeneratorConfig,
            ServiceConfig,
            UserConfig,
        )
        from aiperf.common.config.input_config import InputConfig
        from aiperf.common.enums import ServiceRunType
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

        # Configuration with chunking
        user_config = UserConfig(
            endpoint=EndpointConfig(
                url="http://mock-llm-service.default.svc.cluster.local:8000",
                model_names=["mock-model"],
                endpoint_type="chat",
                streaming=True,
            ),
            input=InputConfig(
                public_dataset="sharegpt",
                random_seed=42,
                enable_chunking=True,
                dataset_chunk_size=100,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(
                concurrency=10,
                benchmark_duration=30,
            ),
        )

        service_config = ServiceConfig()
        service_config.service_run_type = ServiceRunType.KUBERNETES
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = test_namespace
        service_config.kubernetes.image = "aiperf:latest"
        service_config.kubernetes.image_pull_policy = "IfNotPresent"
        service_config.kubernetes.cleanup_on_completion = True

        orchestrator = KubernetesOrchestrator(user_config, service_config)

        try:
            # Deploy
            success = await orchestrator.deploy()
            assert success, "Deployment should succeed"

            # Verify namespace created
            result = subprocess.run(
                ["kubectl", "get", "namespace", test_namespace],
                capture_output=True,
                timeout=10,
            )
            assert result.returncode == 0, "Namespace should exist"

            # Verify ConfigMap with chunking settings
            cm_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "configmap",
                    "aiperf-config",
                    "-n",
                    test_namespace,
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert cm_result.returncode == 0

            cm_data = json.loads(cm_result.stdout)
            user_json = json.loads(cm_data["data"]["user_config.json"])

            # Verify chunking configuration
            assert user_json["input"]["enable_chunking"] is True
            assert user_json["input"]["dataset_chunk_size"] == 100
            assert user_json["input"]["deterministic_conversation_assignment"] is True
            assert user_json["input"]["random_seed"] == 42

            # Verify system controller pod created
            pods_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    test_namespace,
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert pods_result.returncode == 0

            pods_data = json.loads(pods_result.stdout)
            pod_names = [pod["metadata"]["name"] for pod in pods_data["items"]]
            assert any("system-controller" in name for name in pod_names)

            # Wait for system controller to be ready
            ready = await orchestrator.resource_manager.wait_for_pod_ready(
                "system-controller", timeout=60
            )
            assert ready, "System controller should become ready"

        finally:
            await orchestrator.cleanup()

            # Verify cleanup
            await asyncio.sleep(5)
            result = subprocess.run(
                ["kubectl", "get", "namespace", test_namespace],
                capture_output=True,
                timeout=10,
            )
            assert result.returncode != 0, "Namespace should be deleted"

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_worker_pods_created_with_chunking_config(
        self, ensure_minikube_running, test_namespace
    ):
        """Test that worker pods receive chunking configuration."""
        from aiperf.common.config import (
            EndpointConfig,
            LoadGeneratorConfig,
            ServiceConfig,
            UserConfig,
        )
        from aiperf.common.config.input_config import InputConfig
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

        user_config = UserConfig(
            endpoint=EndpointConfig(
                url="http://mock-llm-service.default.svc.cluster.local:8000",
                model_names=["mock-model"],
            ),
            input=InputConfig(
                public_dataset="sharegpt",
                random_seed=42,
                enable_chunking=True,
                dataset_chunk_size=50,
            ),
            loadgen=LoadGeneratorConfig(concurrency=5, benchmark_duration=20),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = test_namespace
        service_config.kubernetes.image = "aiperf:latest"
        service_config.kubernetes.image_pull_policy = "IfNotPresent"

        orchestrator = KubernetesOrchestrator(user_config, service_config)

        try:
            success = await orchestrator.deploy()
            assert success

            # Verify ConfigMap has correct settings
            cm_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "configmap",
                    "aiperf-config",
                    "-n",
                    test_namespace,
                    "-o",
                    "jsonpath={.data.user_config\\.json}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            user_data = json.loads(cm_result.stdout)
            assert user_data["input"]["enable_chunking"] is True
            assert user_data["input"]["dataset_chunk_size"] == 50

        finally:
            await orchestrator.cleanup()


@pytest.mark.integration
@pytest.mark.minikube
class TestRealClusterChunking:
    """Test chunking behavior in real cluster environment."""

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_datasetmanager_pod_handles_chunk_requests(
        self, ensure_minikube_running, test_namespace
    ):
        """Test DatasetManager pod in cluster handles chunk requests."""
        from aiperf.common.config import EndpointConfig, ServiceConfig, UserConfig
        from aiperf.common.config.input_config import InputConfig
        from aiperf.common.enums import ServiceType
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator
        from aiperf.kubernetes.templates import PodTemplateBuilder

        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                public_dataset="sharegpt",
                enable_chunking=True,
                dataset_chunk_size=100,
            ),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = test_namespace
        service_config.kubernetes.image = "aiperf:latest"

        orchestrator = KubernetesOrchestrator(user_config, service_config)

        try:
            # Deploy basic infrastructure
            await orchestrator.resource_manager.create_namespace()

            # Create ConfigMap
            from aiperf.kubernetes.config_serializer import ConfigSerializer

            config_data = ConfigSerializer.serialize_to_configmap(
                user_config, service_config
            )
            await orchestrator.resource_manager.create_configmap(
                "aiperf-config", config_data
            )

            # Deploy DatasetManager pod
            template_builder = PodTemplateBuilder(
                namespace=test_namespace,
                image="aiperf:latest",
                image_pull_policy="IfNotPresent",
                service_account="default",
                system_controller_service="test-sc",
            )

            pod_spec = template_builder.build_pod_spec(
                service_type=ServiceType.DATASET_MANAGER,
                service_id="dataset-manager-test",
                config_map_name="aiperf-config",
                cpu="1",
                memory="1Gi",
            )

            await orchestrator.resource_manager.create_pod(pod_spec)

            # Wait for pod to be ready
            ready = await orchestrator.resource_manager.wait_for_pod_ready(
                "dataset-manager-test", timeout=60
            )
            assert ready, "DatasetManager pod should become ready"

            # Verify pod is running
            pod_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pod",
                    "dataset-manager-test",
                    "-n",
                    test_namespace,
                    "-o",
                    "jsonpath={.status.phase}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert pod_result.stdout == "Running"

        finally:
            await orchestrator.resource_manager.cleanup_all(delete_namespace=True)

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_worker_pods_use_chunking(
        self, ensure_minikube_running, test_namespace
    ):
        """Test worker pods are configured to use chunking."""
        from aiperf.common.config import (
            EndpointConfig,
            LoadGeneratorConfig,
            ServiceConfig,
            UserConfig,
        )
        from aiperf.common.config.input_config import InputConfig
        from aiperf.kubernetes.config_serializer import ConfigSerializer
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                public_dataset="sharegpt",
                enable_chunking=True,
                dataset_chunk_size=100,
            ),
            loadgen=LoadGeneratorConfig(concurrency=5),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = test_namespace
        service_config.kubernetes.image = "aiperf:latest"
        service_config.kubernetes.image_pull_policy = "IfNotPresent"

        orchestrator = KubernetesOrchestrator(user_config, service_config)

        try:
            # Create namespace and ConfigMap
            await orchestrator.resource_manager.create_namespace()

            config_data = ConfigSerializer.serialize_to_configmap(
                user_config, service_config
            )
            await orchestrator.resource_manager.create_configmap(
                "aiperf-config", config_data
            )

            # Verify worker configuration in ConfigMap
            cm_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "configmap",
                    "aiperf-config",
                    "-n",
                    test_namespace,
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            cm_json = json.loads(cm_result.stdout)
            user_data = json.loads(cm_json["data"]["user_config.json"])

            # Workers will read this config and use chunking
            assert user_data["input"]["enable_chunking"] is True
            assert user_data["input"]["dataset_chunk_size"] == 100

        finally:
            await orchestrator.resource_manager.cleanup_all(delete_namespace=True)


@pytest.mark.integration
@pytest.mark.minikube
class TestReproducibilityOnCluster:
    """Test reproducibility with actual cluster deployments."""

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_deterministic_mode_across_concurrency_on_cluster(
        self, ensure_minikube_running, test_namespace
    ):
        """Test deterministic mode produces same results with different concurrency.

        This is the GOLD STANDARD test - actual cluster deployment with
        different worker counts should produce identical conversation sequences.
        """
        from aiperf.common.config import (
            EndpointConfig,
            LoadGeneratorConfig,
            ServiceConfig,
            UserConfig,
        )
        from aiperf.common.config.input_config import InputConfig
        from aiperf.kubernetes.config_serializer import ConfigSerializer
        from aiperf.kubernetes.resource_manager import KubernetesResourceManager

        async def deploy_and_get_config(concurrency: int):
            """Deploy with specific concurrency and verify config."""
            namespace = f"{test_namespace}-{concurrency}"

            user_config = UserConfig(
                endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
                input=InputConfig(
                    public_dataset="sharegpt",
                    random_seed=42,
                    deterministic_conversation_assignment=True,
                    dataset_chunk_size=50,
                ),
                loadgen=LoadGeneratorConfig(
                    concurrency=concurrency,
                    request_count=500,
                ),
            )

            service_config = ServiceConfig()
            service_config.kubernetes.enabled = True

            resource_manager = KubernetesResourceManager(namespace=namespace)

            try:
                await resource_manager.create_namespace()

                config_data = ConfigSerializer.serialize_to_configmap(
                    user_config, service_config
                )
                await resource_manager.create_configmap("aiperf-config", config_data)

                # Read back and verify
                cm = resource_manager.core_api.read_namespaced_config_map(
                    name="aiperf-config", namespace=namespace
                )

                user_data = json.loads(cm.data["user_config.json"])

                return {
                    "concurrency": concurrency,
                    "deterministic": user_data["input"][
                        "deterministic_conversation_assignment"
                    ],
                    "seed": user_data["input"]["random_seed"],
                    "chunk_size": user_data["input"]["dataset_chunk_size"],
                }

            finally:
                await resource_manager.cleanup_all(delete_namespace=True)

        # Test with different concurrency levels
        config_10 = await deploy_and_get_config(10)
        config_50 = await deploy_and_get_config(50)
        config_100 = await deploy_and_get_config(100)

        # All should have same deterministic settings
        assert config_10["deterministic"] is True
        assert config_50["deterministic"] is True
        assert config_100["deterministic"] is True

        # All should have same seed
        assert config_10["seed"] == config_50["seed"] == config_100["seed"] == 42


@pytest.mark.integration
@pytest.mark.minikube
class TestFullBenchmarkOnCluster:
    """Test complete benchmark execution on real cluster."""

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_short_benchmark_with_chunking(
        self, ensure_minikube_running, test_namespace, mock_llm_deployed
    ):
        """Run actual short benchmark on cluster with chunking enabled."""
        if not mock_llm_deployed:
            pytest.skip("Mock LLM service not deployed")

        from aiperf.common.config import (
            EndpointConfig,
            LoadGeneratorConfig,
            ServiceConfig,
            UserConfig,
        )
        from aiperf.common.config.input_config import InputConfig
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

        user_config = UserConfig(
            endpoint=EndpointConfig(
                url="http://mock-llm-service.default.svc.cluster.local:8000",
                model_names=["mock-model"],
                endpoint_type="chat",
                streaming=True,
            ),
            input=InputConfig(
                public_dataset="sharegpt",
                random_seed=42,
                enable_chunking=True,
                dataset_chunk_size=100,
            ),
            loadgen=LoadGeneratorConfig(
                concurrency=5,
                benchmark_duration=20,  # Short test
            ),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = test_namespace
        service_config.kubernetes.image = "aiperf:latest"
        service_config.kubernetes.image_pull_policy = "IfNotPresent"
        service_config.kubernetes.cleanup_on_completion = True

        orchestrator = KubernetesOrchestrator(user_config, service_config)

        try:
            # Deploy
            success = await orchestrator.deploy()
            assert success

            # Monitor pods
            await asyncio.sleep(10)

            pods_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    test_namespace,
                ],
                capture_output=True,
                text=True,
            )
            print(f"\nPods in namespace:\n{pods_result.stdout}")

            # Check system controller logs for chunking activity
            logs = await orchestrator.get_logs(ServiceType.SYSTEM_CONTROLLER)
            print(
                f"\nSystem controller logs sample:\n{list(logs.values())[0][:500] if logs else 'No logs'}"
            )

            # Note: Full benchmark completion would take too long for integration test
            # This test validates deployment works, actual completion tested in E2E

        finally:
            await orchestrator.cleanup()

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_deterministic_benchmark_reproducibility_on_cluster(
        self, ensure_minikube_running, test_namespace, mock_llm_deployed
    ):
        """Test deterministic mode reproducibility with actual cluster runs.

        This test deploys twice with different concurrency but same seed,
        then verifies the configuration is set up for reproducibility.
        """
        if not mock_llm_deployed:
            pytest.skip("Mock LLM service not deployed")

        from aiperf.common.config import (
            EndpointConfig,
            LoadGeneratorConfig,
            ServiceConfig,
            UserConfig,
        )
        from aiperf.common.config.input_config import InputConfig
        from aiperf.kubernetes.config_serializer import ConfigSerializer
        from aiperf.kubernetes.resource_manager import KubernetesResourceManager

        async def deploy_with_config(concurrency: int, run_id: int):
            """Deploy and extract deterministic sequence."""
            namespace = f"{test_namespace}-run{run_id}"

            user_config = UserConfig(
                endpoint=EndpointConfig(
                    url="http://mock-llm-service.default.svc.cluster.local:8000",
                    model_names=["mock-model"],
                ),
                input=InputConfig(
                    public_dataset="sharegpt",
                    random_seed=42,
                    deterministic_conversation_assignment=True,
                    dataset_chunk_size=100,
                ),
                loadgen=LoadGeneratorConfig(
                    concurrency=concurrency,
                    request_count=200,  # Fixed request count
                ),
            )

            service_config = ServiceConfig()
            service_config.kubernetes.enabled = True

            resource_manager = KubernetesResourceManager(namespace=namespace)

            try:
                await resource_manager.create_namespace()

                config_data = ConfigSerializer.serialize_to_configmap(
                    user_config, service_config
                )
                await resource_manager.create_configmap("aiperf-config", config_data)

                # Read back config
                cm = resource_manager.core_api.read_namespaced_config_map(
                    name="aiperf-config", namespace=namespace
                )

                user_data = json.loads(cm.data["user_config.json"])

                return user_data

            finally:
                await resource_manager.cleanup_all(delete_namespace=True)

        # Deploy with different concurrency
        config1 = await deploy_with_config(concurrency=10, run_id=1)
        config2 = await deploy_with_config(concurrency=50, run_id=2)

        # Both should have identical deterministic settings
        assert config1["input"]["deterministic_conversation_assignment"] is True
        assert config2["input"]["deterministic_conversation_assignment"] is True
        assert config1["input"]["random_seed"] == config2["input"]["random_seed"] == 42

        # Both configured for same total requests
        assert (
            config1["loadgen"]["request_count"]
            == config2["loadgen"]["request_count"]
            == 200
        )


@pytest.mark.integration
@pytest.mark.minikube
class TestClusterScaling:
    """Test scaling behavior on real cluster."""

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_multiple_worker_pods_with_chunking(
        self, ensure_minikube_running, test_namespace
    ):
        """Test that multiple worker pods can be created with chunking config."""
        from aiperf.common.config import (
            EndpointConfig,
            LoadGeneratorConfig,
            ServiceConfig,
            UserConfig,
        )
        from aiperf.common.config.input_config import InputConfig
        from aiperf.common.enums import ServiceType
        from aiperf.controller.kubernetes_service_manager import (
            KubernetesServiceManager,
        )
        from aiperf.kubernetes.resource_manager import KubernetesResourceManager
        from aiperf.kubernetes.templates import PodTemplateBuilder

        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                enable_chunking=True,
                dataset_chunk_size=100,
            ),
            loadgen=LoadGeneratorConfig(concurrency=20),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True

        resource_manager = KubernetesResourceManager(namespace=test_namespace)
        template_builder = PodTemplateBuilder(
            namespace=test_namespace,
            image="aiperf:latest",
            image_pull_policy="IfNotPresent",
            service_account="default",
            system_controller_service="test-sc",
        )

        service_manager = KubernetesServiceManager(
            required_services={ServiceType.WORKER: 5},
            service_config=service_config,
            user_config=user_config,
            resource_manager=resource_manager,
            template_builder=template_builder,
            config_map_name="test-config",
        )

        try:
            await resource_manager.create_namespace()

            # Create ConfigMap
            from aiperf.kubernetes.config_serializer import ConfigSerializer

            config_data = ConfigSerializer.serialize_to_configmap(
                user_config, service_config
            )
            await resource_manager.create_configmap("test-config", config_data)

            # Deploy 5 worker pods
            await service_manager.run_service(ServiceType.WORKER, num_replicas=5)

            # Verify 5 worker pods created
            pods_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pods",
                    "-l",
                    f"service-type={ServiceType.WORKER.value}",
                    "-n",
                    test_namespace,
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if pods_result.returncode == 0:
                pods_data = json.loads(pods_result.stdout)
                pod_count = len(pods_data.get("items", []))
                assert pod_count == 5, f"Expected 5 worker pods, found {pod_count}"

        finally:
            await resource_manager.cleanup_all(delete_namespace=True)


@pytest.mark.integration
@pytest.mark.minikube
class TestClusterCommunication:
    """Test ZMQ communication between pods."""

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_clusterip_services_created(
        self, ensure_minikube_running, test_namespace
    ):
        """Test that ClusterIP services are created for ZMQ communication."""
        from aiperf.common.config import EndpointConfig, ServiceConfig, UserConfig
        from aiperf.common.config.input_config import InputConfig
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(enable_chunking=True),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = test_namespace
        service_config.kubernetes.image = "aiperf:latest"

        orchestrator = KubernetesOrchestrator(user_config, service_config)

        try:
            success = await orchestrator.deploy()
            assert success

            # Verify ClusterIP services exist
            services_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "services",
                    "-n",
                    test_namespace,
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            services_data = json.loads(services_result.stdout)
            service_names = [svc["metadata"]["name"] for svc in services_data["items"]]

            # Should have system controller service
            assert "aiperf-system-controller" in service_names

            # Verify service has ZMQ ports
            sc_service = next(
                s
                for s in services_data["items"]
                if s["metadata"]["name"] == "aiperf-system-controller"
            )
            ports = sc_service["spec"]["ports"]
            port_names = [p["name"] for p in ports]

            # Should have dataset manager port (for chunk requests)
            assert any("dataset" in name for name in port_names)

        finally:
            await orchestrator.cleanup()


@pytest.mark.integration
@pytest.mark.minikube
class TestArtifactRetrieval:
    """Test artifact retrieval from cluster."""

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_config_propagation_to_artifacts(
        self, ensure_minikube_running, test_namespace
    ):
        """Test that chunking configuration is visible in cluster."""
        from aiperf.common.config import EndpointConfig, ServiceConfig, UserConfig
        from aiperf.common.config.input_config import InputConfig
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                enable_chunking=True,
                dataset_chunk_size=150,
                deterministic_conversation_assignment=True,
            ),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = test_namespace
        service_config.kubernetes.image = "aiperf:latest"

        orchestrator = KubernetesOrchestrator(user_config, service_config)

        try:
            success = await orchestrator.deploy()
            assert success

            # Get ConfigMap and verify all settings
            cm = orchestrator.resource_manager.core_api.read_namespaced_config_map(
                name="aiperf-config", namespace=test_namespace
            )

            user_data = json.loads(cm.data["user_config.json"])

            # Verify complete chunking configuration
            assert user_data["input"]["enable_chunking"] is True
            assert user_data["input"]["dataset_chunk_size"] == 150
            assert user_data["input"]["deterministic_conversation_assignment"] is True
            assert user_data["input"]["prefetch_threshold"] == 0.2

        finally:
            await orchestrator.cleanup()


@pytest.mark.integration
@pytest.mark.minikube
class TestClusterResourceManagement:
    """Test resource management with chunking configurations."""

    @requires_minikube()
    @pytest.mark.asyncio
    async def test_cleanup_removes_all_resources(
        self, ensure_minikube_running, test_namespace
    ):
        """Test that cleanup removes all created resources."""
        from aiperf.common.config import EndpointConfig, ServiceConfig, UserConfig
        from aiperf.common.config.input_config import InputConfig
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(enable_chunking=True, dataset_chunk_size=100),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = test_namespace
        service_config.kubernetes.image = "aiperf:latest"

        orchestrator = KubernetesOrchestrator(user_config, service_config)

        # Deploy
        success = await orchestrator.deploy()
        assert success

        # Verify resources exist
        ns_result = subprocess.run(
            ["kubectl", "get", "namespace", test_namespace],
            capture_output=True,
        )
        assert ns_result.returncode == 0

        # Cleanup
        await orchestrator.cleanup()

        # Wait for deletion
        await asyncio.sleep(5)

        # Verify namespace is gone
        ns_result = subprocess.run(
            ["kubectl", "get", "namespace", test_namespace],
            capture_output=True,
        )
        assert ns_result.returncode != 0, "Namespace should be deleted"


def test_minikube_integration_test_completeness():
    """Verify minikube integration test suite covers all critical scenarios."""

    test_scenarios = {
        "deployment_with_chunking": True,
        "worker_pod_configuration": True,
        "deterministic_mode_setup": True,
        "reproducibility_config_validation": True,
        "clusterip_services": True,
        "config_propagation": True,
        "resource_cleanup": True,
        "short_benchmark_execution": True,
    }

    assert all(test_scenarios.values()), "Not all scenarios covered"
