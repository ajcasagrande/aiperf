import pytest
import asyncio
import os
from unittest.mock import MagicMock, patch, AsyncMock, call, ANY

from aiperf.system.system_controller import SystemController
from aiperf.common.models import SystemState


class TestSystemControllerKubernetes:
    """Tests for SystemController with Kubernetes integration."""

    @pytest.mark.asyncio
    async def test_init_with_kubernetes_enabled(self, sample_aiperf_config, mock_kubernetes_client):
        """Test initialization with Kubernetes enabled."""
        with patch("aiperf.system.system_controller.KubernetesManager") as mock_k8s_manager:
            # Arrange
            mock_k8s_manager_instance = MagicMock()
            mock_k8s_manager.return_value = mock_k8s_manager_instance
            
            # Act
            controller = SystemController(sample_aiperf_config)
            await controller.initialize()
            
            # Assert
            mock_k8s_manager.assert_called_once_with(sample_aiperf_config)
            assert controller._kubernetes_manager is not None
            assert controller.state == SystemState.READY

    @pytest.mark.asyncio
    async def test_init_with_kubernetes_disabled(self, sample_aiperf_config_no_k8s):
        """Test initialization with Kubernetes disabled."""
        # Arrange
        controller = SystemController(sample_aiperf_config_no_k8s)
        
        # Act
        await controller.initialize()
        
        # Assert
        assert controller._kubernetes_manager is None
        assert controller.state == SystemState.READY

    @pytest.mark.asyncio
    async def test_start_profile_with_kubernetes(self, sample_aiperf_config, mock_kubernetes_client):
        """Test starting profile with Kubernetes scaling."""
        with patch("aiperf.system.system_controller.KubernetesManager") as mock_k8s_manager:
            # Arrange
            mock_k8s_manager_instance = MagicMock()
            mock_k8s_manager_instance.scale_workers = AsyncMock(return_value=True)
            mock_k8s_manager.return_value = mock_k8s_manager_instance
            
            controller = SystemController(sample_aiperf_config)
            await controller.initialize()
            controller.state = SystemState.READY  # Force ready state
            
            # Act
            result = await controller.start_profile()
            
            # Assert
            assert result is True
            assert controller.state == SystemState.RUNNING
            mock_k8s_manager_instance.scale_workers.assert_called_once_with(
                sample_aiperf_config.workers.min_workers
            )

    @pytest.mark.asyncio
    async def test_start_profile_with_kubernetes_scaling_error(self, sample_aiperf_config, mock_kubernetes_client):
        """Test starting profile with Kubernetes scaling error."""
        with patch("aiperf.system.system_controller.KubernetesManager") as mock_k8s_manager:
            # Arrange
            mock_k8s_manager_instance = MagicMock()
            mock_k8s_manager_instance.scale_workers = AsyncMock(side_effect=Exception("Scaling error"))
            mock_k8s_manager.return_value = mock_k8s_manager_instance
            
            controller = SystemController(sample_aiperf_config)
            await controller.initialize()
            controller.state = SystemState.READY  # Force ready state
            
            # Act
            result = await controller.start_profile()
            
            # Assert
            assert result is True  # Should still return True as this is non-fatal
            assert controller.state == SystemState.RUNNING
            mock_k8s_manager_instance.scale_workers.assert_called_once_with(
                sample_aiperf_config.workers.min_workers
            )

    @pytest.mark.asyncio
    async def test_shutdown_with_kubernetes(self, sample_aiperf_config, mock_kubernetes_client):
        """Test shutting down with Kubernetes scaling to zero."""
        with patch("aiperf.system.system_controller.KubernetesManager") as mock_k8s_manager:
            # Arrange
            mock_k8s_manager_instance = MagicMock()
            mock_k8s_manager_instance.scale_workers = AsyncMock(return_value=True)
            mock_k8s_manager.return_value = mock_k8s_manager_instance
            
            controller = SystemController(sample_aiperf_config)
            await controller.initialize()
            controller.state = SystemState.READY  # Force ready state
            
            # Act
            result = await controller.shutdown()
            
            # Assert
            assert result is True
            assert controller.state == SystemState.STOPPED
            mock_k8s_manager_instance.scale_workers.assert_called_once_with(0)
            
    @pytest.mark.asyncio
    async def test_shutdown_with_kubernetes_scaling_error(self, sample_aiperf_config, mock_kubernetes_client):
        """Test shutting down with Kubernetes scaling error."""
        with patch("aiperf.system.system_controller.KubernetesManager") as mock_k8s_manager:
            # Arrange
            mock_k8s_manager_instance = MagicMock()
            mock_k8s_manager_instance.scale_workers = AsyncMock(side_effect=Exception("Scaling error"))
            mock_k8s_manager.return_value = mock_k8s_manager_instance
            
            controller = SystemController(sample_aiperf_config)
            await controller.initialize()
            controller.state = SystemState.READY  # Force ready state
            
            # Act
            result = await controller.shutdown()
            
            # Assert
            assert result is True  # Should still return True as this is non-fatal
            assert controller.state == SystemState.STOPPED
            mock_k8s_manager_instance.scale_workers.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_register_worker_kubernetes(self, sample_aiperf_config, mock_kubernetes_client):
        """Test worker registration in Kubernetes mode."""
        with patch("aiperf.system.system_controller.KubernetesManager") as mock_k8s_manager:
            # Arrange
            mock_k8s_manager_instance = MagicMock()
            mock_k8s_manager.return_value = mock_k8s_manager_instance
            
            controller = SystemController(sample_aiperf_config)
            await controller.initialize()
            worker_id = "test-worker-1"
            worker_data = {"endpoint": "test-endpoint", "status": "ready"}
            
            # Act
            result = await controller.register_worker(worker_id, worker_data)
            
            # Assert
            assert result is True
            assert worker_id in controller._workers_registry
            assert controller._workers_registry[worker_id] == worker_data

    @pytest.mark.asyncio
    async def test_get_worker_config_kubernetes(self, sample_aiperf_config, mock_kubernetes_client):
        """Test getting worker configuration in Kubernetes mode."""
        with patch("aiperf.system.system_controller.KubernetesManager") as mock_k8s_manager:
            # Arrange
            mock_k8s_manager_instance = MagicMock()
            mock_k8s_manager.return_value = mock_k8s_manager_instance
            
            controller = SystemController(sample_aiperf_config)
            await controller.initialize()
            
            # Act
            config = await controller.get_worker_config()
            
            # Assert
            assert config is not None
            assert "endpoint_config" in config
            # Should contain the test endpoint from sample config
            assert config["endpoint_config"]["name"] == "test-endpoint"
            assert config["endpoint_config"]["url"] == "https://api.example.com/v1/completions" 