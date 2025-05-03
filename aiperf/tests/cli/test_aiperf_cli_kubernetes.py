import pytest
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock, call, ANY

from aiperf.cli.aiperf_cli import (
    parse_args,
    run_profile,
    k8s_apply,
    k8s_delete,
    k8s_status,
    main_async,
    main
)


class TestAIPerfCLIKubernetes:
    """Tests for the AIPerf CLI with Kubernetes functionality."""

    def test_parse_args_run_kubernetes(self):
        """Test argument parsing for run with Kubernetes options."""
        test_args = [
            "run", "config.yaml", 
            "--kubernetes",
            "--k8s-namespace", "test-namespace",
            "--k8s-image", "aiperf:test",
            "--k8s-service-account", "aiperf-sa",
            "--k8s-persistent-volume-claim", "data-pvc",
            "--log-level", "DEBUG"
        ]
        with patch.object(sys, "argv", ["aiperf_cli.py"] + test_args):
            args = parse_args()
            assert args.command == "run"
            assert args.config == "config.yaml"
            assert args.kubernetes is True
            assert args.k8s_namespace == "test-namespace"
            assert args.k8s_image == "aiperf:test"
            assert args.k8s_service_account == "aiperf-sa"
            assert args.k8s_persistent_volume_claim == "data-pvc"
            assert args.k8s_no_config_map is False
            assert args.log_level == "DEBUG"

    def test_parse_args_kubernetes_apply(self):
        """Test argument parsing for Kubernetes apply."""
        test_args = [
            "kubernetes", "apply", "config.yaml",
            "--namespace", "test-namespace",
            "--dry-run",
            "--log-level", "DEBUG"
        ]
        with patch.object(sys, "argv", ["aiperf_cli.py"] + test_args):
            args = parse_args()
            assert args.command == "kubernetes"
            assert args.k8s_command == "apply"
            assert args.config == "config.yaml"
            assert args.namespace == "test-namespace"
            assert args.dry_run is True
            assert args.log_level == "DEBUG"

    def test_parse_args_kubernetes_delete(self):
        """Test argument parsing for Kubernetes delete."""
        test_args = [
            "kubernetes", "delete", "config.yaml",
            "--namespace", "test-namespace",
            "--log-level", "DEBUG"
        ]
        with patch.object(sys, "argv", ["aiperf_cli.py"] + test_args):
            args = parse_args()
            assert args.command == "kubernetes"
            assert args.k8s_command == "delete"
            assert args.config == "config.yaml"
            assert args.namespace == "test-namespace"
            assert args.log_level == "DEBUG"

    def test_parse_args_kubernetes_status(self):
        """Test argument parsing for Kubernetes status."""
        test_args = [
            "kubernetes", "status",
            "--namespace", "test-namespace",
            "--log-level", "DEBUG"
        ]
        with patch.object(sys, "argv", ["aiperf_cli.py"] + test_args):
            args = parse_args()
            assert args.command == "kubernetes"
            assert args.k8s_command == "status"
            assert args.namespace == "test-namespace"
            assert args.log_level == "DEBUG"

    @pytest.mark.asyncio
    async def test_run_profile_kubernetes(self, sample_config_file):
        """Test running a profile with Kubernetes enabled."""
        # Mock arguments
        args = MagicMock()
        args.config = sample_config_file
        args.kubernetes = True
        args.k8s_namespace = "test-namespace"
        args.k8s_image = "aiperf:test"
        args.k8s_service_account = "aiperf-sa"
        args.k8s_no_config_map = False
        args.k8s_persistent_volume_claim = "data-pvc"
        
        # Mock SystemController
        with patch("aiperf.cli.aiperf_cli.SystemController") as mock_controller_cls:
            # Mock controller instance
            mock_controller = MagicMock()
            mock_controller.initialize = AsyncMock(return_value=True)
            mock_controller.ready_check = AsyncMock(return_value=True)
            mock_controller.start_profile = AsyncMock(return_value=True)
            mock_controller.wait_for_shutdown = AsyncMock()
            mock_controller.shutdown = AsyncMock()
            mock_controller_cls.return_value = mock_controller
            
            # Act
            result = await run_profile(args)
            
            # Assert
            assert result == 0
            mock_controller_cls.assert_called_once()
            
            # Get the config that was passed to SystemController
            config_arg = mock_controller_cls.call_args[0][0]
            assert config_arg.kubernetes.enabled is True
            assert config_arg.kubernetes.namespace == "test-namespace"
            assert config_arg.kubernetes.image == "aiperf:test"
            assert config_arg.kubernetes.service_account == "aiperf-sa"
            assert config_arg.kubernetes.use_config_map is True
            assert config_arg.kubernetes.persistent_volume_claim == "data-pvc"
            assert config_arg.communication.type == "zmq"

    @pytest.mark.asyncio
    async def test_k8s_apply(self, sample_config_file):
        """Test Kubernetes apply command."""
        # Mock arguments
        args = MagicMock()
        args.config = sample_config_file
        args.namespace = "test-namespace"
        args.dry_run = True
        
        # Mock KubernetesManager
        with patch("aiperf.cli.aiperf_cli.KubernetesManager") as mock_k8s_manager_cls:
            # Mock manager instance
            mock_k8s_manager = MagicMock()
            mock_k8s_manager.apply_resources = AsyncMock(return_value=True)
            mock_k8s_manager_cls.return_value = mock_k8s_manager
            
            # Act
            result = await k8s_apply(args)
            
            # Assert
            assert result == 0
            mock_k8s_manager_cls.assert_called_once()
            
            # Get the config that was passed to KubernetesManager
            config_arg = mock_k8s_manager_cls.call_args[0][0]
            assert config_arg.kubernetes.enabled is True
            assert config_arg.kubernetes.namespace == "test-namespace"
            
            # Check that apply_resources was called with dry_run=True
            mock_k8s_manager.apply_resources.assert_called_once_with(dry_run=True)

    @pytest.mark.asyncio
    async def test_k8s_apply_failure(self, sample_config_file):
        """Test Kubernetes apply command with failure."""
        # Mock arguments
        args = MagicMock()
        args.config = sample_config_file
        args.namespace = "test-namespace"
        args.dry_run = False
        
        # Mock KubernetesManager
        with patch("aiperf.cli.aiperf_cli.KubernetesManager") as mock_k8s_manager_cls:
            # Mock manager instance
            mock_k8s_manager = MagicMock()
            mock_k8s_manager.apply_resources = AsyncMock(return_value=False)
            mock_k8s_manager_cls.return_value = mock_k8s_manager
            
            # Act
            result = await k8s_apply(args)
            
            # Assert
            assert result == 1
            mock_k8s_manager.apply_resources.assert_called_once_with(dry_run=False)

    @pytest.mark.asyncio
    async def test_k8s_delete(self, sample_config_file):
        """Test Kubernetes delete command."""
        # Mock arguments
        args = MagicMock()
        args.config = sample_config_file
        args.namespace = "test-namespace"
        
        # Mock KubernetesManager
        with patch("aiperf.cli.aiperf_cli.KubernetesManager") as mock_k8s_manager_cls:
            # Mock manager instance
            mock_k8s_manager = MagicMock()
            mock_k8s_manager.delete_resources = AsyncMock(return_value=True)
            mock_k8s_manager_cls.return_value = mock_k8s_manager
            
            # Act
            result = await k8s_delete(args)
            
            # Assert
            assert result == 0
            mock_k8s_manager_cls.assert_called_once()
            
            # Get the config that was passed to KubernetesManager
            config_arg = mock_k8s_manager_cls.call_args[0][0]
            assert config_arg.kubernetes.enabled is True
            assert config_arg.kubernetes.namespace == "test-namespace"
            
            # Check that delete_resources was called
            mock_k8s_manager.delete_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_k8s_status(self):
        """Test Kubernetes status command."""
        # Mock arguments
        args = MagicMock()
        args.namespace = "test-namespace"
        
        # Mock KubernetesManager
        with patch("aiperf.cli.aiperf_cli.KubernetesManager") as mock_k8s_manager_cls:
            # Mock manager instance
            mock_k8s_manager = MagicMock()
            mock_k8s_manager.get_status = AsyncMock(return_value={
                "controller": {"ready": 1, "total": 1},
                "workers": {"ready": 3, "total": 5},
                "pods": [
                    {"name": "pod1", "phase": "Running"},
                    {"name": "pod2", "phase": "Running"},
                    {"name": "pod3", "phase": "Pending"}
                ]
            })
            mock_k8s_manager_cls.return_value = mock_k8s_manager
            
            # Act
            result = await k8s_status(args)
            
            # Assert
            assert result == 0
            mock_k8s_manager_cls.assert_called_once()
            
            # Get the config that was passed to KubernetesManager
            config_arg = mock_k8s_manager_cls.call_args[0][0]
            assert config_arg.kubernetes.enabled is True
            assert config_arg.kubernetes.namespace == "test-namespace"
            
            # Check that get_status was called
            mock_k8s_manager.get_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_async_kubernetes_apply(self):
        """Test main_async with Kubernetes apply command."""
        # Mock parse_args
        with patch("aiperf.cli.aiperf_cli.parse_args") as mock_parse_args:
            args = MagicMock()
            args.command = "kubernetes"
            args.k8s_command = "apply"
            args.log_level = "INFO"
            mock_parse_args.return_value = args
            
            # Mock setup_logging
            with patch("aiperf.cli.aiperf_cli.setup_logging") as mock_setup_logging:
                # Mock k8s_apply
                with patch("aiperf.cli.aiperf_cli.k8s_apply") as mock_k8s_apply:
                    mock_k8s_apply.return_value = 0
                    
                    # Act
                    result = await main_async()
                    
                    # Assert
                    assert result == 0
                    mock_parse_args.assert_called_once()
                    mock_setup_logging.assert_called_once_with("INFO")
                    mock_k8s_apply.assert_called_once_with(args)

    @pytest.mark.asyncio
    async def test_main_async_kubernetes_delete(self):
        """Test main_async with Kubernetes delete command."""
        # Mock parse_args
        with patch("aiperf.cli.aiperf_cli.parse_args") as mock_parse_args:
            args = MagicMock()
            args.command = "kubernetes"
            args.k8s_command = "delete"
            args.log_level = "INFO"
            mock_parse_args.return_value = args
            
            # Mock setup_logging
            with patch("aiperf.cli.aiperf_cli.setup_logging") as mock_setup_logging:
                # Mock k8s_delete
                with patch("aiperf.cli.aiperf_cli.k8s_delete") as mock_k8s_delete:
                    mock_k8s_delete.return_value = 0
                    
                    # Act
                    result = await main_async()
                    
                    # Assert
                    assert result == 0
                    mock_parse_args.assert_called_once()
                    mock_setup_logging.assert_called_once_with("INFO")
                    mock_k8s_delete.assert_called_once_with(args)

    @pytest.mark.asyncio
    async def test_main_async_kubernetes_status(self):
        """Test main_async with Kubernetes status command."""
        # Mock parse_args
        with patch("aiperf.cli.aiperf_cli.parse_args") as mock_parse_args:
            args = MagicMock()
            args.command = "kubernetes"
            args.k8s_command = "status"
            args.log_level = "INFO"
            mock_parse_args.return_value = args
            
            # Mock setup_logging
            with patch("aiperf.cli.aiperf_cli.setup_logging") as mock_setup_logging:
                # Mock k8s_status
                with patch("aiperf.cli.aiperf_cli.k8s_status") as mock_k8s_status:
                    mock_k8s_status.return_value = 0
                    
                    # Act
                    result = await main_async()
                    
                    # Assert
                    assert result == 0
                    mock_parse_args.assert_called_once()
                    mock_setup_logging.assert_called_once_with("INFO")
                    mock_k8s_status.assert_called_once_with(args)

    @pytest.mark.asyncio
    async def test_main_async_kubernetes_unknown_command(self):
        """Test main_async with unknown Kubernetes command."""
        # Mock parse_args
        with patch("aiperf.cli.aiperf_cli.parse_args") as mock_parse_args:
            args = MagicMock()
            args.command = "kubernetes"
            args.k8s_command = "unknown"
            args.log_level = "INFO"
            mock_parse_args.return_value = args
            
            # Mock setup_logging
            with patch("aiperf.cli.aiperf_cli.setup_logging") as mock_setup_logging:
                # Act
                result = await main_async()
                
                # Assert
                assert result == 1
                mock_parse_args.assert_called_once()
                mock_setup_logging.assert_called_once_with("INFO")

    def test_main(self):
        """Test main entry point."""
        with patch("aiperf.cli.aiperf_cli.asyncio.run") as mock_run:
            mock_run.return_value = 0
            
            # Act
            result = main()
            
            # Assert
            assert result == 0
            mock_run.assert_called_once_with(main_async()) 