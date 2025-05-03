import pytest
import asyncio
import json
import yaml
from unittest.mock import MagicMock, patch, call, ANY

from aiperf.system.kubernetes_manager import KubernetesManager

class TestKubernetesManager:
    """Tests for the KubernetesManager class."""

    @pytest.mark.asyncio
    async def test_init(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test initialization of KubernetesManager."""
        # Act
        manager = KubernetesManager(sample_aiperf_config)
        
        # Assert
        assert manager.config == sample_aiperf_config
        assert manager.kubernetes_config == sample_aiperf_config.kubernetes
        assert manager._manifests == {}
        mock_kubernetes_config.load_kube_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_in_cluster(self, sample_aiperf_config, mock_kubernetes_client):
        """Test initialization of KubernetesManager in a cluster."""
        # Arrange
        with patch("kubernetes.config") as mock_config:
            mock_config.load_incluster_config = MagicMock()
            
            # Act
            manager = KubernetesManager(sample_aiperf_config)
            
            # Assert
            mock_config.load_incluster_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_resources(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test applying Kubernetes resources."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        
        # Mock the private methods with async functions
        async def mock_generate_manifests():
            pass
            
        manager._generate_manifests = mock_generate_manifests
        manager._ensure_namespace = mock_generate_manifests
        manager._apply_config_map = mock_generate_manifests
        manager._ensure_pvc = mock_generate_manifests
        manager._apply_controller_deployment = mock_generate_manifests
        manager._apply_worker_deployment = mock_generate_manifests
        manager._apply_services = mock_generate_manifests
        
        # Act
        result = await manager.apply_resources()
        
        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_apply_resources_dry_run(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test applying Kubernetes resources in dry run mode."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        
        # Mock the private methods with async functions
        async def mock_generate_manifests():
            pass
            
        manager._generate_manifests = mock_generate_manifests
        manager._print_manifests = MagicMock()
        
        # Act
        result = await manager.apply_resources(dry_run=True)
        
        # Assert
        assert result is True
        manager._print_manifests.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_resources_error(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test applying Kubernetes resources with an error."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        
        # Mock the private methods with async functions
        async def mock_generate_manifests():
            raise Exception("Test error")
            
        manager._generate_manifests = mock_generate_manifests
        
        # Act
        result = await manager.apply_resources()
        
        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_resources(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test deleting Kubernetes resources."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        apps_api = mock_kubernetes_client.AppsV1Api.return_value
        
        # Act
        result = await manager.delete_resources()
        
        # Assert
        assert result is True
        apps_api.delete_namespaced_deployment.assert_any_call("aiperf-controller", "aiperf-test")
        apps_api.delete_namespaced_deployment.assert_any_call("aiperf-workers", "aiperf-test")
        core_api.delete_namespaced_service.assert_any_call("aiperf-controller", "aiperf-test")
        core_api.delete_namespaced_service.assert_any_call("aiperf-workers", "aiperf-test")
        core_api.delete_namespaced_config_map.assert_called_once_with("aiperf-config", "aiperf-test")

    @pytest.mark.asyncio
    async def test_delete_resources_error(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test deleting Kubernetes resources with an error."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        apps_api = mock_kubernetes_client.AppsV1Api.return_value
        apps_api.delete_namespaced_deployment.side_effect = Exception("Test error")
        
        # Act
        result = await manager.delete_resources()
        
        # Assert
        assert result is True  # Still returns True because errors are caught

    @pytest.mark.asyncio
    async def test_get_status(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test getting Kubernetes status."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        apps_api = mock_kubernetes_client.AppsV1Api.return_value
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        
        # Mock deployment statuses
        controller_deployment = MagicMock()
        controller_deployment.status.ready_replicas = 1
        controller_deployment.status.replicas = 1
        controller_deployment.status.available_replicas = 1
        controller_deployment.status.conditions = [MagicMock(type="Available", status="True", reason="MinimumReplicasAvailable")]
        apps_api.read_namespaced_deployment.return_value = controller_deployment
        
        # Mock pod list
        pod = MagicMock()
        pod.metadata.name = "aiperf-controller-123"
        pod.status.phase = "Running"
        pod.status.start_time = MagicMock()
        pod.status.start_time.isoformat.return_value = "2021-08-26T12:00:00Z"
        pod.status.conditions = [MagicMock(type="Ready", status="True")]
        pod.status.container_statuses = [
            MagicMock(name="controller", ready=True, restart_count=0, state=MagicMock(running=True, waiting=None, terminated=None))
        ]
        pod_list = MagicMock()
        pod_list.items = [pod]
        core_api.list_namespaced_pod.return_value = pod_list
        
        # Mock service list
        service = MagicMock()
        service.metadata.name = "aiperf-controller"
        service.spec.type = "ClusterIP"
        service.spec.cluster_ip = "10.0.0.1"
        service.spec.ports = [MagicMock(name="pub", port=5557, target_port=5557)]
        service_list = MagicMock()
        service_list.items = [service]
        core_api.list_namespaced_service.return_value = service_list
        
        # Act
        status = await manager.get_status()
        
        # Assert
        assert "controller" in status
        assert "workers" in status
        assert "pods" in status
        assert "services" in status
        assert status["controller"]["ready"] == 1
        assert status["controller"]["total"] == 1
        assert status["controller"]["available"] == 1
        assert status["pods"][0]["name"] == "aiperf-controller-123"
        assert status["pods"][0]["phase"] == "Running"
        assert status["services"][0]["name"] == "aiperf-controller"
        assert status["services"][0]["cluster_ip"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_get_status_error(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test getting Kubernetes status with an error."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        apps_api = mock_kubernetes_client.AppsV1Api.return_value
        apps_api.read_namespaced_deployment.side_effect = Exception("Test error")
        
        # Act
        status = await manager.get_status()
        
        # Assert
        assert "controller" in status
        assert "error" in status["controller"]
        assert "Test error" in status["controller"]["error"]

    @pytest.mark.asyncio
    async def test_scale_workers(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test scaling worker deployment."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        apps_api = mock_kubernetes_client.AppsV1Api.return_value
        
        # Act
        result = await manager.scale_workers(10)
        
        # Assert
        assert result is True
        apps_api.patch_namespaced_deployment.assert_called_once_with(
            "aiperf-workers",
            "aiperf-test",
            {"spec": {"replicas": 10}}
        )

    @pytest.mark.asyncio
    async def test_scale_workers_error(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test scaling worker deployment with an error."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        apps_api = mock_kubernetes_client.AppsV1Api.return_value
        apps_api.patch_namespaced_deployment.side_effect = Exception("Test error")
        
        # Act
        result = await manager.scale_workers(10)
        
        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_generate_manifests(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating Kubernetes manifests."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        manager._generate_config_map = MagicMock(return_value={"config": "map"})
        manager._generate_controller_deployment = MagicMock(return_value={"controller": "deployment"})
        manager._generate_worker_deployment = MagicMock(return_value={"worker": "deployment"})
        manager._generate_controller_service = MagicMock(return_value={"controller": "service"})
        manager._generate_worker_service = MagicMock(return_value={"worker": "service"})
        
        # Act
        await manager._generate_manifests()
        
        # Assert
        assert manager._manifests["configmap"] == {"config": "map"}
        assert manager._manifests["controller_deployment"] == {"controller": "deployment"}
        assert manager._manifests["worker_deployment"] == {"worker": "deployment"}
        assert manager._manifests["controller_service"] == {"controller": "service"}
        assert manager._manifests["worker_service"] == {"worker": "service"}

    @pytest.mark.asyncio
    async def test_ensure_namespace_existing(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test ensuring namespace when it already exists."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        
        # Act
        await manager._ensure_namespace()
        
        # Assert
        core_api.read_namespace.assert_called_once_with("aiperf-test")
        core_api.create_namespace.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_namespace_new(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test ensuring namespace when it doesn't exist."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        core_api.read_namespace.side_effect = Exception("Not found")
        
        # Act
        await manager._ensure_namespace()
        
        # Assert
        core_api.read_namespace.assert_called_once_with("aiperf-test")
        core_api.create_namespace.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_config_map(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test applying ConfigMap when it doesn't exist."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        manager._generate_config_map = MagicMock(return_value={"config": "map"})
        core_api.replace_namespaced_config_map.side_effect = Exception("Not found")
        
        # Act
        await manager._apply_config_map()
        
        # Assert
        manager._generate_config_map.assert_called_once()
        core_api.replace_namespaced_config_map.assert_called_once_with("aiperf-config", "aiperf-test", {"config": "map"})
        core_api.create_namespaced_config_map.assert_called_once_with("aiperf-test", {"config": "map"})

    @pytest.mark.asyncio
    async def test_apply_config_map_existing(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test applying ConfigMap when it already exists."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        core_api = mock_kubernetes_client.CoreV1Api.return_value
        manager._generate_config_map = MagicMock(return_value={"config": "map"})
        
        # Act
        await manager._apply_config_map()
        
        # Assert
        manager._generate_config_map.assert_called_once()
        core_api.replace_namespaced_config_map.assert_called_once_with("aiperf-config", "aiperf-test", {"config": "map"})
        core_api.create_namespaced_config_map.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_config_map(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating ConfigMap manifest."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        
        # Act
        config_map = manager._generate_config_map()
        
        # Assert
        assert config_map["apiVersion"] == "v1"
        assert config_map["kind"] == "ConfigMap"
        assert config_map["metadata"]["name"] == "aiperf-config"
        assert config_map["metadata"]["namespace"] == "aiperf-test"
        assert "config.json" in config_map["data"]
        assert "profile_name" in config_map["data"]
        assert config_map["data"]["profile_name"] == "test-profile"

    def test_generate_controller_deployment(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating controller deployment manifest."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        
        # Act
        deployment = manager._generate_controller_deployment()
        
        # Assert
        assert deployment["apiVersion"] == "apps/v1"
        assert deployment["kind"] == "Deployment"
        assert deployment["metadata"]["name"] == "aiperf-controller"
        assert deployment["metadata"]["namespace"] == "aiperf-test"
        assert deployment["spec"]["replicas"] == 1
        assert "aiperf-controller" in deployment["spec"]["selector"]["matchLabels"]["app.kubernetes.io/name"]
        assert deployment["spec"]["template"]["spec"]["containers"][0]["image"] == "aiperf:test"
        assert len(deployment["spec"]["template"]["spec"]["containers"][0]["ports"]) == 4  # 4 ZMQ ports

    def test_generate_worker_deployment(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating worker deployment manifest."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        
        # Act
        deployment = manager._generate_worker_deployment()
        
        # Assert
        assert deployment["apiVersion"] == "apps/v1"
        assert deployment["kind"] == "Deployment"
        assert deployment["metadata"]["name"] == "aiperf-workers"
        assert deployment["metadata"]["namespace"] == "aiperf-test"
        assert deployment["spec"]["replicas"] == sample_aiperf_config.workers.min_workers
        assert "aiperf-workers" in deployment["spec"]["selector"]["matchLabels"]["app.kubernetes.io/name"]
        assert deployment["spec"]["template"]["spec"]["containers"][0]["image"] == "aiperf:test"
        assert "aiperf-controller" in deployment["spec"]["template"]["spec"]["containers"][0]["command"]

    def test_generate_controller_service(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating controller service manifest."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        
        # Act
        service = manager._generate_controller_service()
        
        # Assert
        assert service["apiVersion"] == "v1"
        assert service["kind"] == "Service"
        assert service["metadata"]["name"] == "aiperf-controller"
        assert service["metadata"]["namespace"] == "aiperf-test"
        assert service["spec"]["selector"]["app.kubernetes.io/name"] == "aiperf-controller"
        assert len(service["spec"]["ports"]) == 4  # 4 ZMQ ports

    def test_generate_worker_service(self, sample_aiperf_config, mock_kubernetes_client, mock_kubernetes_config):
        """Test generating worker service manifest."""
        # Arrange
        manager = KubernetesManager(sample_aiperf_config)
        
        # Act
        service = manager._generate_worker_service()
        
        # Assert
        assert service["apiVersion"] == "v1"
        assert service["kind"] == "Service"
        assert service["metadata"]["name"] == "aiperf-workers"
        assert service["metadata"]["namespace"] == "aiperf-test"
        assert service["spec"]["selector"]["app.kubernetes.io/name"] == "aiperf-workers"
        assert len(service["spec"]["ports"]) == 1  # HTTP port 