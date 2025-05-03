import pytest
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock, call, ANY

from aiperf.cli.worker_cli import (
    parse_args,
    run_worker,
    shutdown,
    main_async,
    main
)


class TestWorkerCLI:
    """Tests for the worker CLI."""

    def test_parse_args(self):
        """Test argument parsing."""
        # Test with minimum required arguments
        test_args = ["run", "--controller", "localhost"]
        with patch.object(sys, "argv", ["worker_cli.py"] + test_args):
            args = parse_args()
            assert args.command == "run"
            assert args.controller == "localhost"
            assert args.pub_port == 5557  # Default
            assert args.sub_port == 5558  # Default
            assert args.req_port == 5559  # Default
            assert args.rep_port == 5560  # Default
            assert args.worker_id is None  # Default
            assert args.log_level == "INFO"  # Default
            assert args.log_file is None  # Default
        
        # Test with all arguments
        test_args = [
            "run",
            "--controller", "k8s-controller.aiperf.svc.cluster.local",
            "--pub-port", "6001",
            "--sub-port", "6002",
            "--req-port", "6003",
            "--rep-port", "6004",
            "--worker-id", "k8s-worker-1",
            "--log-level", "DEBUG",
            "--log-file", "/tmp/worker.log"
        ]
        with patch.object(sys, "argv", ["worker_cli.py"] + test_args):
            args = parse_args()
            assert args.command == "run"
            assert args.controller == "k8s-controller.aiperf.svc.cluster.local"
            assert args.pub_port == 6001
            assert args.sub_port == 6002
            assert args.req_port == 6003
            assert args.rep_port == 6004
            assert args.worker_id == "k8s-worker-1"
            assert args.log_level == "DEBUG"
            assert args.log_file == "/tmp/worker.log"

    @pytest.mark.asyncio
    async def test_run_worker_success(self):
        """Test successful worker run."""
        # Mock command line arguments
        args = MagicMock()
        args.controller = "localhost"
        args.pub_port = 5557
        args.sub_port = 5558
        args.req_port = 5559
        args.rep_port = 5560
        args.worker_id = "test-worker-1"
        args.log_level = "INFO"
        args.log_file = None
        
        # Mock ZMQCommunication
        with patch("aiperf.cli.worker_cli.ZMQCommunication") as mock_zmq:
            # Mock the communication instance
            mock_comm = MagicMock()
            mock_comm.initialize = AsyncMock(return_value=True)
            mock_comm.request = AsyncMock()
            mock_comm.request.side_effect = [
                # First request for worker config
                {
                    "status": "success",
                    "endpoint_config": {
                        "name": "test-endpoint",
                        "url": "https://api.example.com/v1/completions",
                        "api_type": "openai",
                        "headers": {"Content-Type": "application/json"}
                    }
                },
                # Second request for worker registration
                {
                    "status": "success"
                }
            ]
            mock_comm.subscribe = AsyncMock()
            mock_comm.shutdown = AsyncMock()
            mock_zmq.return_value = mock_comm
            
            # Mock Worker
            with patch("aiperf.cli.worker_cli.Worker") as mock_worker_cls:
                # Mock worker instance
                mock_worker = MagicMock()
                mock_worker.initialize = AsyncMock(return_value=True)
                mock_worker.publish_identity = AsyncMock(return_value=True)
                mock_worker.shutdown = AsyncMock()
                mock_worker_cls.return_value = mock_worker
                
                # Act
                # Create a timeout to avoid hanging in the test
                shutdown_event = asyncio.Event()
                
                # Run with timeout to avoid hanging
                result_task = asyncio.create_task(run_worker(args))
                
                # Wait a small amount of time for initialization
                await asyncio.sleep(0.1)
                
                # Trigger shutdown by setting the event that worker is waiting for
                mock_comm.subscribe.assert_called_once_with("system.shutdown", ANY)
                shutdown_callback = mock_comm.subscribe.call_args[0][1]
                shutdown_callback({"command": "shutdown"})
                
                # Wait for result
                result = await result_task
                
                # Assert
                assert result == 0
                mock_zmq.assert_called_once_with(
                    component_id="test-worker-1",
                    pub_address="tcp://localhost:5557",
                    sub_address="tcp://localhost:5558",
                    req_address="tcp://localhost:5559",
                    rep_address="tcp://localhost:5560"
                )
                mock_comm.initialize.assert_called_once()
                assert mock_comm.request.call_count == 2
                # First request should be for config
                assert mock_comm.request.call_args_list[0][0][0] == "system_controller"
                assert mock_comm.request.call_args_list[0][0][1]["command"] == "get_worker_config"
                # Second request should be for registration
                assert mock_comm.request.call_args_list[1][0][0] == "system_controller"
                assert mock_comm.request.call_args_list[1][0][1]["command"] == "register_worker"
                assert mock_comm.request.call_args_list[1][0][1]["worker_id"] == "test-worker-1"
                
                mock_worker_cls.assert_called_once()
                mock_worker.initialize.assert_called_once()
                mock_worker.publish_identity.assert_called_once()
                mock_worker.shutdown.assert_called_once()
                mock_comm.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_worker_failed_config(self):
        """Test worker run with failed config retrieval."""
        # Mock command line arguments
        args = MagicMock()
        args.controller = "localhost"
        args.pub_port = 5557
        args.sub_port = 5558
        args.req_port = 5559
        args.rep_port = 5560
        args.worker_id = "test-worker-1"
        args.log_level = "INFO"
        args.log_file = None
        
        # Mock ZMQCommunication
        with patch("aiperf.cli.worker_cli.ZMQCommunication") as mock_zmq:
            # Mock the communication instance
            mock_comm = MagicMock()
            mock_comm.initialize = AsyncMock(return_value=True)
            # Failed request
            mock_comm.request = AsyncMock(return_value={"status": "error", "message": "Config not found"})
            mock_zmq.return_value = mock_comm
            
            # Act
            result = await run_worker(args)
            
            # Assert
            assert result == 1  # Error exit code
            mock_comm.initialize.assert_called_once()
            mock_comm.request.assert_called_once()
            assert mock_comm.request.call_args[0][0] == "system_controller"
            assert mock_comm.request.call_args[0][1]["command"] == "get_worker_config"

    @pytest.mark.asyncio
    async def test_run_worker_failed_init(self):
        """Test worker run with failed worker initialization."""
        # Mock command line arguments
        args = MagicMock()
        args.controller = "localhost"
        args.pub_port = 5557
        args.sub_port = 5558
        args.req_port = 5559
        args.rep_port = 5560
        args.worker_id = "test-worker-1"
        args.log_level = "INFO"
        args.log_file = None
        
        # Mock ZMQCommunication
        with patch("aiperf.cli.worker_cli.ZMQCommunication") as mock_zmq:
            # Mock the communication instance
            mock_comm = MagicMock()
            mock_comm.initialize = AsyncMock(return_value=True)
            mock_comm.request = AsyncMock(return_value={
                "status": "success",
                "endpoint_config": {
                    "name": "test-endpoint",
                    "url": "https://api.example.com/v1/completions",
                    "api_type": "openai",
                    "headers": {"Content-Type": "application/json"}
                }
            })
            mock_zmq.return_value = mock_comm
            
            # Mock Worker
            with patch("aiperf.cli.worker_cli.Worker") as mock_worker_cls:
                # Mock worker instance that fails to initialize
                mock_worker = MagicMock()
                mock_worker.initialize = AsyncMock(return_value=False)
                mock_worker_cls.return_value = mock_worker
                
                # Act
                result = await run_worker(args)
                
                # Assert
                assert result == 1  # Error exit code
                mock_worker.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_worker_failed_registration(self):
        """Test worker run with failed worker registration."""
        # Mock command line arguments
        args = MagicMock()
        args.controller = "localhost"
        args.pub_port = 5557
        args.sub_port = 5558
        args.req_port = 5559
        args.rep_port = 5560
        args.worker_id = "test-worker-1"
        args.log_level = "INFO"
        args.log_file = None
        
        # Mock ZMQCommunication
        with patch("aiperf.cli.worker_cli.ZMQCommunication") as mock_zmq:
            # Mock the communication instance
            mock_comm = MagicMock()
            mock_comm.initialize = AsyncMock(return_value=True)
            mock_comm.request = AsyncMock()
            mock_comm.request.side_effect = [
                # First request for worker config
                {
                    "status": "success",
                    "endpoint_config": {
                        "name": "test-endpoint",
                        "url": "https://api.example.com/v1/completions",
                        "api_type": "openai",
                        "headers": {"Content-Type": "application/json"}
                    }
                },
                # Second request for worker registration fails
                {
                    "status": "error",
                    "message": "Registration failed"
                }
            ]
            mock_zmq.return_value = mock_comm
            
            # Mock Worker
            with patch("aiperf.cli.worker_cli.Worker") as mock_worker_cls:
                # Mock worker instance
                mock_worker = MagicMock()
                mock_worker.initialize = AsyncMock(return_value=True)
                mock_worker.publish_identity = AsyncMock(return_value=True)
                mock_worker_cls.return_value = mock_worker
                
                # Act
                result = await run_worker(args)
                
                # Assert
                assert result == 1  # Error exit code
                assert mock_comm.request.call_count == 2
                mock_worker.initialize.assert_called_once()
                mock_worker.publish_identity.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test worker shutdown."""
        # Mock worker
        mock_worker = MagicMock()
        mock_worker.shutdown = AsyncMock()
        
        # Act
        await shutdown(mock_worker)
        
        # Assert
        mock_worker.shutdown.assert_called_once()

    def test_main(self):
        """Test main entry point."""
        with patch("aiperf.cli.worker_cli.asyncio.run") as mock_run:
            mock_run.return_value = 0
            
            # Act
            result = main()
            
            # Assert
            assert result == 0
            mock_run.assert_called_once_with(main_async())

    @pytest.mark.asyncio
    async def test_main_async_run(self):
        """Test main_async with run command."""
        # Mock command line arguments
        with patch("aiperf.cli.worker_cli.parse_args") as mock_parse_args:
            args = MagicMock()
            args.command = "run"
            args.log_level = "INFO"
            args.log_file = None
            mock_parse_args.return_value = args
            
            # Mock setup_logging
            with patch("aiperf.cli.worker_cli.setup_logging") as mock_setup_logging:
                # Mock run_worker
                with patch("aiperf.cli.worker_cli.run_worker") as mock_run_worker:
                    mock_run_worker.return_value = 0
                    
                    # Act
                    result = await main_async()
                    
                    # Assert
                    assert result == 0
                    mock_parse_args.assert_called_once()
                    mock_setup_logging.assert_called_once_with("INFO")
                    mock_run_worker.assert_called_once_with(args)

    @pytest.mark.asyncio
    async def test_main_async_unknown_command(self):
        """Test main_async with unknown command."""
        # Mock command line arguments
        with patch("aiperf.cli.worker_cli.parse_args") as mock_parse_args:
            args = MagicMock()
            args.command = "invalid"
            args.log_level = "INFO"
            mock_parse_args.return_value = args
            
            # Mock setup_logging
            with patch("aiperf.cli.worker_cli.setup_logging") as mock_setup_logging:
                # Act
                result = await main_async()
                
                # Assert
                assert result == 1  # Error exit code
                mock_parse_args.assert_called_once()
                mock_setup_logging.assert_called_once_with("INFO") 