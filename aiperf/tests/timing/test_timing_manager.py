import pytest
import asyncio
import time
import random
import uuid
from unittest.mock import patch, MagicMock, AsyncMock, call

from aiperf.timing.timing_manager import TimingManager
from aiperf.config.config_models import TimingConfig
from aiperf.common.models import TimingCredit, DistributionType


class TestTimingManager:
    """Tests for the TimingManager class."""
    
    @pytest.fixture
    def sample_fixed_timing_config(self):
        """Create a sample fixed timing configuration."""
        return TimingConfig(
            schedule_type="fixed",
            parameters={"request_rate": 10.0},
            duration=5.0,
            start_delay=0.1
        )
    
    @pytest.fixture
    def sample_poisson_timing_config(self):
        """Create a sample Poisson timing configuration."""
        return TimingConfig(
            schedule_type="poisson",
            parameters={"request_rate": 10.0},
            duration=5.0,
            start_delay=0.1
        )
    
    @pytest.fixture
    def sample_normal_timing_config(self):
        """Create a sample Normal timing configuration."""
        return TimingConfig(
            schedule_type="normal",
            parameters={
                "request_rate": 10.0,
                "mean": 0.1,
                "stddev": 0.025
            },
            duration=5.0,
            start_delay=0.1
        )
    
    @pytest.fixture
    def sample_uniform_timing_config(self):
        """Create a sample Uniform timing configuration."""
        return TimingConfig(
            schedule_type="uniform",
            parameters={
                "min_rate": 5.0,
                "max_rate": 15.0
            },
            duration=5.0,
            start_delay=0.1
        )
    
    @pytest.fixture
    def mock_communication(self):
        """Create a mock communication interface."""
        mock_comm = AsyncMock()
        mock_comm.publish = AsyncMock(return_value=True)
        mock_comm.subscribe = AsyncMock(return_value=True)
        return mock_comm
    
    @pytest.mark.asyncio
    async def test_initialize_fixed(self, sample_fixed_timing_config, mock_communication):
        """Test initialization with fixed schedule."""
        # Arrange
        manager = TimingManager(
            config=sample_fixed_timing_config,
            communication=mock_communication,
            component_id="test_timing_manager"
        )
        
        # Act
        result = await manager.initialize()
        
        # Assert
        assert result is True
        assert manager._is_initialized is True
        assert manager._is_ready is True
        assert len(manager._schedule) == 50  # 10 req/s * 5s = 50 requests
        assert len(manager._pending_credits) == 50
        mock_communication.subscribe.assert_any_call("timing.request", manager._handle_timing_request)
        mock_communication.subscribe.assert_any_call("timing.credit.consumed", manager._handle_credit_consumed)
    
    @pytest.mark.asyncio
    async def test_initialize_poisson(self, sample_poisson_timing_config, mock_communication):
        """Test initialization with Poisson schedule."""
        # Arrange
        manager = TimingManager(
            config=sample_poisson_timing_config,
            communication=mock_communication,
            component_id="test_timing_manager"
        )
        
        # Act
        result = await manager.initialize()
        
        # Assert
        assert result is True
        assert manager._is_initialized is True
        assert manager._is_ready is True
        assert len(manager._schedule) > 0
        assert len(manager._pending_credits) == len(manager._schedule)
    
    @pytest.mark.asyncio
    async def test_initialize_normal(self, sample_normal_timing_config, mock_communication):
        """Test initialization with Normal schedule."""
        # Arrange
        manager = TimingManager(
            config=sample_normal_timing_config,
            communication=mock_communication,
            component_id="test_timing_manager"
        )
        
        # Act
        result = await manager.initialize()
        
        # Assert
        assert result is True
        assert manager._is_initialized is True
        assert manager._is_ready is True
        assert len(manager._schedule) > 0
        assert len(manager._pending_credits) == len(manager._schedule)
    
    @pytest.mark.asyncio
    async def test_initialize_uniform(self, sample_uniform_timing_config, mock_communication):
        """Test initialization with Uniform schedule."""
        # Arrange
        manager = TimingManager(
            config=sample_uniform_timing_config,
            communication=mock_communication,
            component_id="test_timing_manager"
        )
        
        # Act
        result = await manager.initialize()
        
        # Assert
        assert result is True
        assert manager._is_initialized is True
        assert manager._is_ready is True
        assert len(manager._schedule) > 0
        assert len(manager._pending_credits) == len(manager._schedule)
    
    @pytest.mark.asyncio
    async def test_initialize_invalid_schedule_type(self, mock_communication):
        """Test initialization with invalid schedule type."""
        # Arrange
        config = TimingConfig(
            schedule_type="invalid",
            parameters={},
            duration=5.0
        )
        manager = TimingManager(
            config=config,
            communication=mock_communication
        )
        
        # Act
        result = await manager.initialize()
        
        # Assert
        assert result is False
        assert manager._is_initialized is False
    
    @pytest.mark.asyncio
    async def test_initialize_error(self, sample_fixed_timing_config, mock_communication):
        """Test error during initialization."""
        # Arrange
        manager = TimingManager(
            config=sample_fixed_timing_config,
            communication=mock_communication
        )
        
        with patch.object(manager, "_initialize_fixed_schedule", side_effect=Exception("Test error")):
            # Act
            result = await manager.initialize()
            
            # Assert
            assert result is False
            assert manager._is_initialized is False
    
    @pytest.mark.asyncio
    async def test_ready_check(self, sample_fixed_timing_config):
        """Test ready check."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        manager._is_initialized = True
        manager._is_ready = True
        
        # Act
        result = await manager.ready_check()
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_publish_identity(self, sample_fixed_timing_config, mock_communication):
        """Test publishing identity."""
        # Arrange
        manager = TimingManager(
            config=sample_fixed_timing_config,
            communication=mock_communication,
            component_id="test_timing_manager"
        )
        manager._schedule = [TimingCredit(credit_id="test", target_timestamp=time.time(), credit_type="request")]
        manager._pending_credits = {"test"}
        
        # Act
        result = await manager.publish_identity()
        
        # Assert
        assert result is True
        mock_communication.publish.assert_called_once()
        call_args = mock_communication.publish.call_args[0]
        assert call_args[0] == "system.identity"
        assert call_args[1]["component_id"] == "test_timing_manager"
        assert call_args[1]["component_type"] == "timing_manager"
        assert call_args[1]["schedule_type"] == "fixed"
        assert call_args[1]["total_credits"] == 1
        assert call_args[1]["pending_credits"] == 1
    
    @pytest.mark.asyncio
    async def test_publish_identity_no_communication(self, sample_fixed_timing_config):
        """Test publishing identity with no communication interface."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        
        # Act
        result = await manager.publish_identity()
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_shutdown(self, sample_fixed_timing_config):
        """Test graceful shutdown."""
        # Arrange
        with patch("aiperf.timing.timing_manager.asyncio.create_task") as mock_create_task:
            manager = TimingManager(config=sample_fixed_timing_config)
            manager._running = True  # Set to running to trigger the timer task cancellation
            manager._timer_task = AsyncMock()
            manager._timer_task.done = MagicMock(return_value=False)
            manager._timer_task.cancel = MagicMock()
            
            # Mock stop_timing to avoid duplicate calls
            with patch.object(manager, "stop_timing", AsyncMock(return_value=True)):
                # Act
                result = await manager.shutdown()
                
                # Assert
                assert result is True
                assert manager._is_shutdown is True
                manager._timer_task.cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_no_timer_task(self, sample_fixed_timing_config):
        """Test shutdown with no timer task."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        manager._timer_task = None
        
        # Act
        result = await manager.shutdown()
        
        # Assert
        assert result is True
        assert manager._is_shutdown is True
    
    @pytest.mark.asyncio
    async def test_shutdown_error(self, sample_fixed_timing_config):
        """Test error during shutdown."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        manager._running = True  # Set to running to trigger the timer task cancellation
        manager._timer_task = AsyncMock()
        manager._timer_task.done = MagicMock(return_value=False)
        with patch.object(manager, "stop_timing", side_effect=Exception("Test error")):
            # Act
            result = await manager.shutdown()
            
            # Assert
            assert result is False
    
    @pytest.mark.asyncio
    async def test_handle_command_start(self, sample_fixed_timing_config):
        """Test handling start command."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        
        with patch.object(manager, "start_timing", return_value=True):
            # Act
            response = await manager.handle_command("start")
            
            # Assert
            assert response["status"] == "success"
            assert response["message"] == "Timing started"
    
    @pytest.mark.asyncio
    async def test_handle_command_stop(self, sample_fixed_timing_config):
        """Test handling stop command."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        
        with patch.object(manager, "stop_timing", return_value=True):
            # Act
            response = await manager.handle_command("stop")
            
            # Assert
            assert response["status"] == "success"
            assert response["message"] == "Timing stopped"
    
    @pytest.mark.asyncio
    async def test_handle_command_stats(self, sample_fixed_timing_config):
        """Test handling stats command."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        
        with patch.object(manager, "get_timing_stats", return_value={"total_credits": 10, "pending_credits": 5}):
            # Act
            response = await manager.handle_command("stats")
            
            # Assert
            assert response["status"] == "success"
            assert response["stats"]["total_credits"] == 10
            assert response["stats"]["pending_credits"] == 5
    
    @pytest.mark.asyncio
    async def test_handle_command_unknown(self, sample_fixed_timing_config):
        """Test handling unknown command."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        
        # Act
        response = await manager.handle_command("unknown_command")
        
        # Assert
        assert response["status"] == "error"
        assert "Unknown command" in response["message"]
    
    @pytest.mark.asyncio
    async def test_handle_timing_request(self, sample_fixed_timing_config, mock_communication):
        """Test handling timing request."""
        # Arrange
        manager = TimingManager(
            config=sample_fixed_timing_config,
            communication=mock_communication
        )
        
        with patch.object(manager, "get_next_credit", return_value=TimingCredit(
            credit_id="test_credit",
            target_timestamp=time.time(),
            credit_type="request"
        )):
            # Create a request message
            message = {
                "client_id": "test_client",
                "data": {
                    "request_id": "req_123",
                    "action": "get_next_credit"
                }
            }
            
            # Act
            await manager._handle_timing_request(message)
            
            # Assert
            mock_communication.respond.assert_called_once()
            call_args = mock_communication.respond.call_args[0]
            assert call_args[0] == "test_client"
            assert call_args[1] == "req_123"
            assert call_args[2]["status"] == "success"
            assert call_args[2]["credit"]["credit_id"] == "test_credit"
    
    @pytest.mark.asyncio
    async def test_handle_timing_request_no_credit(self, sample_fixed_timing_config, mock_communication):
        """Test handling timing request with no credit available."""
        # Arrange
        manager = TimingManager(
            config=sample_fixed_timing_config,
            communication=mock_communication
        )
        
        with patch.object(manager, "get_next_credit", return_value=None):
            # Create a request message
            message = {
                "client_id": "test_client",
                "data": {
                    "request_id": "req_123",
                    "action": "get_next_credit"
                }
            }
            
            # Act
            await manager._handle_timing_request(message)
            
            # Assert
            mock_communication.respond.assert_called_once()
            call_args = mock_communication.respond.call_args[0]
            assert call_args[0] == "test_client"
            assert call_args[1] == "req_123"
            assert call_args[2]["status"] == "error"
            assert "No credits available" in call_args[2]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_credit_consumed(self, sample_fixed_timing_config):
        """Test handling credit consumed."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        credit_id = "test_credit"
        manager._pending_credits = {credit_id}
        
        # Create a message
        message = {
            "data": {
                "credit_id": credit_id
            }
        }
        
        # Act
        await manager._handle_credit_consumed(message)
        
        # Assert
        assert credit_id not in manager._pending_credits
        assert credit_id in manager._consumed_credits
    
    @pytest.mark.asyncio
    async def test_start_timing(self, sample_fixed_timing_config):
        """Test starting timing."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        
        with patch("asyncio.create_task") as mock_create_task:
            # Act
            result = await manager.start_timing()
            
            # Assert
            assert result is True
            assert manager._running is True
            assert manager._start_time is not None
            assert manager._stop_time is None
            mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_timing_already_running(self, sample_fixed_timing_config):
        """Test starting timing when already running."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        manager._running = True
        
        # Act
        result = await manager.start_timing()
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_stop_timing(self, sample_fixed_timing_config):
        """Test stopping timing."""
        # Arrange
        with patch("aiperf.timing.timing_manager.asyncio.create_task") as mock_create_task:
            manager = TimingManager(config=sample_fixed_timing_config)
            manager._running = True
            manager._timer_task = AsyncMock()
            manager._timer_task.done = MagicMock(return_value=False)
            manager._timer_task.cancel = MagicMock()
            manager._start_time = time.time() - 10  # Started 10 seconds ago
            
            # Act
            with patch("aiperf.timing.timing_manager.asyncio.CancelledError", Exception):
                result = await manager.stop_timing()
                
                # Assert
                assert result is True
                assert manager._running is False
                assert manager._stop_time is not None
                manager._timer_task.cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_timing_not_running(self, sample_fixed_timing_config):
        """Test stopping timing when not running."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        manager._running = False
        manager._timer_task = None
        
        # Act
        result = await manager.stop_timing()
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_issue_credit(self, sample_fixed_timing_config, mock_communication):
        """Test issuing a credit."""
        # Arrange
        manager = TimingManager(
            config=sample_fixed_timing_config,
            communication=mock_communication
        )
        credit_consumer = AsyncMock()
        await manager.register_credit_consumer(credit_consumer)
        
        credit = TimingCredit(
            credit_id="test_credit",
            target_timestamp=time.time(),
            credit_type="request"
        )
        
        # Act
        await manager._issue_credit(credit)
        
        # Assert
        credit_consumer.assert_called_once()
        assert credit_consumer.call_args[0][0] == credit
        
        # Check that the credit was published
        mock_communication.publish.assert_called_once()
        call_args = mock_communication.publish.call_args[0]
        assert call_args[0] == "timing.credit.issued"
        assert call_args[1]["credit_id"] == credit.credit_id
    
    @pytest.mark.asyncio
    async def test_register_credit_consumer(self, sample_fixed_timing_config):
        """Test registering a credit consumer."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        credit_consumer = AsyncMock()
        
        # Act
        result = await manager.register_credit_consumer(credit_consumer)
        
        # Assert
        assert result is True
        assert credit_consumer in manager._credit_consumers
    
    @pytest.mark.asyncio
    async def test_get_next_credit(self, sample_fixed_timing_config):
        """Test getting the next credit."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        now = time.time()
        past_time = now - 1.0  # 1 second in the past
        credit_id = str(uuid.uuid4())
        credit = TimingCredit(
            credit_id=credit_id,
            target_timestamp=past_time,
            credit_type="request"
        )
        manager._schedule = [credit]
        manager._pending_credits = {credit_id}
        manager._consumed_credits = set()
        
        # Act
        next_credit = await manager.get_next_credit()
        
        # Assert
        assert next_credit is not None
        assert next_credit.credit_id == credit_id
    
    @pytest.mark.asyncio
    async def test_get_next_credit_none_available(self, sample_fixed_timing_config):
        """Test getting the next credit when none are available."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        manager._schedule = []
        manager._pending_credits = set()
        
        # Act
        next_credit = await manager.get_next_credit()
        
        # Assert
        assert next_credit is None
    
    @pytest.mark.asyncio
    async def test_get_next_credit_all_consumed(self, sample_fixed_timing_config):
        """Test getting the next credit when all are consumed."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        credit_id = str(uuid.uuid4())
        credit = TimingCredit(
            credit_id=credit_id,
            target_timestamp=time.time() - 1.0,
            credit_type="request"
        )
        manager._schedule = [credit]
        manager._pending_credits = set()  # Empty pending set
        manager._consumed_credits = {credit_id}  # Credit is consumed
        
        # Act
        next_credit = await manager.get_next_credit()
        
        # Assert
        assert next_credit is None
    
    @pytest.mark.asyncio
    async def test_get_timing_stats(self, sample_fixed_timing_config):
        """Test getting timing stats."""
        # Arrange
        manager = TimingManager(config=sample_fixed_timing_config)
        manager._schedule = [
            TimingCredit(credit_id="1", target_timestamp=time.time(), credit_type="request"),
            TimingCredit(credit_id="2", target_timestamp=time.time(), credit_type="request")
        ]
        manager._pending_credits = {"1", "2"}
        manager._consumed_credits = set()
        manager._start_time = time.time() - 10  # Started 10 seconds ago
        
        # Act
        stats = await manager.get_timing_stats()
        
        # Assert
        assert stats["total_credits"] == 2
        assert stats["pending_credits"] == 2
        assert stats["consumed_credits"] == 0
        assert stats["running"] is False
        assert stats["elapsed_time"] >= 10.0 