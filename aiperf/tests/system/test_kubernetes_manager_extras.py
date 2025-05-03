import pytest
import asyncio
import json
import yaml
from unittest.mock import MagicMock, patch, call, ANY

from aiperf.system.kubernetes_manager import KubernetesManager

class TestKubernetesManagerExtras:
    """Additional tests for the KubernetesManager class."""

    @pytest.mark.asyncio
    async def test_apply_pvc_new(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test creating a new PVC."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        core_api.read_namespaced_persistent_volume_claim.side_effect = Exception("PVC not found")
        
        # Act
        await manager._ensure_pvc()
        
        # Assert
        core_api.create_namespaced_persistent_volume_claim.assert_called_once()
        create_args = core_api.create_namespaced_persistent_volume_claim.call_args[0]
        assert create_args[0] == "aiperf-test"  # namespace
        assert create_args[1]["metadata"]["name"] == "test-pvc"  # PVC name from config
        assert create_args[1]["spec"]["accessModes"] == ["ReadWriteOnce"]

    @pytest.mark.asyncio
    async def test_apply_pvc_existing(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test with an existing PVC."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        # Mock PVC already exists
        existing_pvc = MagicMock()
        core_api.read_namespaced_persistent_volume_claim.return_value = existing_pvc
        
        # Act
        await manager._ensure_pvc()
        
        # Assert
        core_api.read_namespaced_persistent_volume_claim.assert_called_once_with(
            "test-pvc", "aiperf-test"
        )
        core_api.create_namespaced_persistent_volume_claim.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_pvc_disabled(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test with PVC disabled."""
        # Arrange
        config = sample_aiperf_config
        config.kubernetes.persistent_volume_claim = None
        manager = KubernetesManager(config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        
        # Act
        await manager._ensure_pvc()
        
        # Assert
        core_api.read_namespaced_persistent_volume_claim.assert_not_called()
        core_api.create_namespaced_persistent_volume_claim.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_manifests_with_custom_resources(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating Kubernetes manifests with custom resources."""
        # Arrange
        config = sample_aiperf_config
        # Add custom resources to the config
        config.kubernetes.resource_requests = {"cpu": "500m", "memory": "512Mi", "nvidia.com/gpu": "1"}
        config.kubernetes.resource_limits = {"cpu": "2", "memory": "4Gi", "nvidia.com/gpu": "1"}
        config.kubernetes.node_selector = {"gpu": "true", "cloud": "aws"}
        config.kubernetes.tolerations = [
            {"key": "nvidia.com/gpu", "operator": "Exists", "effect": "NoSchedule"}
        ]
        
        manager = KubernetesManager(config)
        
        # Act
        await manager._generate_manifests()
        
        # Assert
        # Check worker deployment
        worker_deployment = manager._manifests["worker_deployment"]
        assert worker_deployment["spec"]["template"]["spec"]["nodeSelector"] == {"gpu": "true", "cloud": "aws"}
        assert worker_deployment["spec"]["template"]["spec"]["tolerations"] == [
            {"key": "nvidia.com/gpu", "operator": "Exists", "effect": "NoSchedule"}
        ]
        
        worker_resources = worker_deployment["spec"]["template"]["spec"]["containers"][0]["resources"]
        assert worker_resources["requests"]["cpu"] == "500m"
        assert worker_resources["requests"]["memory"] == "512Mi"
        assert worker_resources["requests"]["nvidia.com/gpu"] == "1"
        assert worker_resources["limits"]["cpu"] == "2"
        assert worker_resources["limits"]["memory"] == "4Gi"
        assert worker_resources["limits"]["nvidia.com/gpu"] == "1"

    @pytest.mark.asyncio
    async def test_generate_controller_deployment_with_custom_images(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating controller deployment with custom image."""
        # Arrange
        config = sample_aiperf_config
        config.kubernetes.controller_image = "aiperf-controller:custom"
        
        manager = KubernetesManager(config)
        
        # Act
        controller_deployment = manager._generate_controller_deployment()
        
        # Assert
        assert controller_deployment["spec"]["template"]["spec"]["containers"][0]["image"] == "aiperf-controller:custom"

    @pytest.mark.asyncio
    async def test_generate_worker_deployment_with_custom_images(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating worker deployment with custom image."""
        # Arrange
        config = sample_aiperf_config
        config.kubernetes.worker_image = "aiperf-worker:custom"
        
        manager = KubernetesManager(config)
        
        # Act
        worker_deployment = manager._generate_worker_deployment()
        
        # Assert
        assert worker_deployment["spec"]["template"]["spec"]["containers"][0]["image"] == "aiperf-worker:custom"

    @pytest.mark.asyncio
    async def test_generate_config_map_with_secrets_enabled(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating config map with secrets enabled."""
        # Arrange
        config = sample_aiperf_config
        # Add sensitive data to endpoint config
        config.endpoints[0].auth = {"api_key": "secretkey123"}
        config.kubernetes.use_secrets = True
        
        manager = KubernetesManager(config)
        
        # Act
        config_map = manager._generate_config_map()
        
        # Assert
        config_data = yaml.safe_load(config_map["data"]["config.yaml"])
        # Check that sensitive data is not in the config map
        assert "auth" not in config_data["endpoints"][0]

    @pytest.mark.asyncio
    async def test_get_status_with_worker_deployment(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test getting status with worker deployment."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        apps_api = mock_kubernetes_client.AppsV1Api.return_value
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        
        # Mock deployment statuses
        controller_deployment = MagicMock()
        controller_deployment.status.ready_replicas = 1
        controller_deployment.status.replicas = 1
        controller_deployment.status.available_replicas = 1
        controller_deployment.status.conditions = [MagicMock(type="Available", status="True")]
        
        workers_deployment = MagicMock()
        workers_deployment.status.ready_replicas = 3
        workers_deployment.status.replicas = 5
        workers_deployment.status.available_replicas = 3
        workers_deployment.status.conditions = [MagicMock(type="Available", status="True")]
        
        apps_api.read_namespaced_deployment.side_effect = lambda name, namespace: (
            controller_deployment if name == "aiperf-controller" else workers_deployment
        )
        
        # Mock pod list
        controller_pod = MagicMock()
        controller_pod.metadata.name = "aiperf-controller-123"
        controller_pod.status.phase = "Running"
        controller_pod.status.start_time = MagicMock()
        controller_pod.status.start_time.isoformat.return_value = "2021-08-26T12:00:00Z"
        
        worker_pod1 = MagicMock()
        worker_pod1.metadata.name = "aiperf-workers-123"
        worker_pod1.status.phase = "Running"
        worker_pod1.status.start_time = MagicMock()
        worker_pod1.status.start_time.isoformat.return_value = "2021-08-26T12:01:00Z"
        
        worker_pod2 = MagicMock()
        worker_pod2.metadata.name = "aiperf-workers-456"
        worker_pod2.status.phase = "Pending"
        worker_pod2.status.start_time = MagicMock()
        worker_pod2.status.start_time.isoformat.return_value = "2021-08-26T12:02:00Z"
        
        pod_list = MagicMock()
        pod_list.items = [controller_pod, worker_pod1, worker_pod2]
        core_api.list_namespaced_pod.return_value = pod_list
        
        # Mock service list
        service_list = MagicMock()
        service_list.items = [MagicMock(), MagicMock()]
        core_api.list_namespaced_service.return_value = service_list
        
        # Act
        status = await manager.get_status()
        
        # Assert
        assert "controller" in status
        assert "workers" in status
        assert "pods" in status
        assert status["controller"]["ready"] == 1
        assert status["controller"]["total"] == 1
        assert status["workers"]["ready"] == 3
        assert status["workers"]["total"] == 5
        assert len(status["pods"]) == 3
        assert status["pods"][0]["name"] == "aiperf-controller-123"
        assert status["pods"][1]["name"] == "aiperf-workers-123"
        assert status["pods"][1]["phase"] == "Running"
        assert status["pods"][2]["name"] == "aiperf-workers-456"
        assert status["pods"][2]["phase"] == "Pending"

    @pytest.mark.asyncio
    async def test_apply_services(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test applying services."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        
        # Mock existing services
        core_api.list_namespaced_service.return_value = MagicMock(items=[])
        
        # Generate manifests
        manager._manifests = {
            "controller_service": {"metadata": {"name": "aiperf-controller"}},
            "worker_service": {"metadata": {"name": "aiperf-workers"}}
        }
        
        # Act
        await manager._apply_services()
        
        # Assert
        assert core_api.create_namespaced_service.call_count == 2
        core_api.create_namespaced_service.assert_any_call(
            "aiperf-test",
            {"metadata": {"name": "aiperf-controller"}}
        )
        core_api.create_namespaced_service.assert_any_call(
            "aiperf-test",
            {"metadata": {"name": "aiperf-workers"}}
        )

    @pytest.mark.asyncio
    async def test_apply_services_existing(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test applying services when they already exist."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        
        # Mock existing services
        existing_service1 = MagicMock()
        existing_service1.metadata.name = "aiperf-controller"
        existing_service2 = MagicMock()
        existing_service2.metadata.name = "aiperf-workers"
        core_api.list_namespaced_service.return_value = MagicMock(items=[existing_service1, existing_service2])
        
        # Generate manifests
        manager._manifests = {
            "controller_service": {"metadata": {"name": "aiperf-controller"}},
            "worker_service": {"metadata": {"name": "aiperf-workers"}}
        }
        
        # Act
        await manager._apply_services()
        
        # Assert
        assert core_api.create_namespaced_service.call_count == 0
        assert core_api.replace_namespaced_service.call_count == 2
        core_api.replace_namespaced_service.assert_any_call(
            "aiperf-controller",
            "aiperf-test",
            {"metadata": {"name": "aiperf-controller"}}
        )
        core_api.replace_namespaced_service.assert_any_call(
            "aiperf-workers",
            "aiperf-test",
            {"metadata": {"name": "aiperf-workers"}}
        ) 