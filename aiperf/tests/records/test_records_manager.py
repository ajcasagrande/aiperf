import pytest
import asyncio
import uuid
import json
import os
from unittest.mock import patch, MagicMock, AsyncMock, call

from aiperf.records.records_manager import RecordsManager
from aiperf.config.config_models import MetricsConfig
from aiperf.common.models import Record, Conversation, Metric


class TestRecordsManager:
    """Tests for the RecordsManager class."""
    
    @pytest.fixture
    def sample_metrics_config(self):
        """Create a sample metrics configuration."""
        return MetricsConfig(
            enabled_metrics=["latency", "tps", "tokens_per_second"],
            output_format="json",
            output_path="/tmp/test_records.json",
            live_metrics=True,
            server_metrics=True
        )
    
    @pytest.fixture
    def mock_communication(self):
        """Create a mock communication interface."""
        mock_comm = AsyncMock()
        mock_comm.publish = AsyncMock(return_value=True)
        mock_comm.subscribe = AsyncMock(return_value=True)
        return mock_comm
    
    @pytest.fixture
    def sample_record(self):
        """Create a sample record."""
        conversation = Conversation(
            conversation_id="conv_123",
            metadata={"test": "metadata"}
        )
        
        metrics = [
            Metric(
                name="latency",
                value=0.5,
                unit="s",
                timestamp=1234567890,
                metadata={"request_id": "req_123"}
            ),
            Metric(
                name="tokens_per_second",
                value=150.5,
                unit="tokens/s",
                timestamp=1234567890,
                metadata={"model": "test-model"}
            )
        ]
        
        return Record(
            record_id="record_123",
            conversation=conversation,
            metrics=metrics,
            raw_data={"prompt": "test prompt", "completion": "test completion"}
        )
    
    @pytest.mark.asyncio
    async def test_initialize(self, sample_metrics_config, mock_communication):
        """Test initialization of records manager."""
        # Arrange
        manager = RecordsManager(
            metrics_config=sample_metrics_config,
            communication=mock_communication,
            component_id="test_records_manager"
        )
        
        with patch.object(manager, "_initialize_storage", return_value=True):
            # Act
            result = await manager.initialize()
            
            # Assert
            assert result is True
            assert manager._is_initialized is True
            assert manager._is_ready is True
            mock_communication.subscribe.assert_called_once_with("records.request", manager._handle_records_request)
    
    @pytest.mark.asyncio
    async def test_initialize_storage_with_output_path(self, sample_metrics_config):
        """Test initializing storage with output path."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        with patch("os.makedirs") as mock_makedirs:
            # Act
            result = await manager._initialize_storage()
            
            # Assert
            assert result is True
            mock_makedirs.assert_called_once_with(os.path.dirname(sample_metrics_config.output_path), exist_ok=True)
    
    @pytest.mark.asyncio
    async def test_initialize_storage_error(self, sample_metrics_config):
        """Test error during storage initialization."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        with patch("os.makedirs", side_effect=Exception("Test error")):
            # Act
            result = await manager._initialize_storage()
            
            # Assert
            assert result is False
    
    @pytest.mark.asyncio
    async def test_ready_check(self, sample_metrics_config):
        """Test ready check."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        manager._is_initialized = True
        manager._is_ready = True
        
        # Act
        result = await manager.ready_check()
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_publish_identity(self, sample_metrics_config, mock_communication):
        """Test publishing identity."""
        # Arrange
        manager = RecordsManager(
            metrics_config=sample_metrics_config,
            communication=mock_communication,
            component_id="test_records_manager"
        )
        
        # Act
        result = await manager.publish_identity()
        
        # Assert
        assert result is True
        mock_communication.publish.assert_called_once()
        call_args = mock_communication.publish.call_args[0]
        assert call_args[0] == "system.identity"
        assert call_args[1]["component_id"] == "test_records_manager"
        assert call_args[1]["component_type"] == "records_manager"
        assert "records_count" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_publish_identity_no_communication(self, sample_metrics_config):
        """Test publishing identity with no communication interface."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        # Act
        result = await manager.publish_identity()
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_shutdown(self, sample_metrics_config):
        """Test graceful shutdown."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        with patch.object(manager, "_flush_records_to_disk", return_value=True):
            # Act
            result = await manager.shutdown()
            
            # Assert
            assert result is True
            assert manager._is_shutdown is True
    
    @pytest.mark.asyncio
    async def test_shutdown_error(self, sample_metrics_config):
        """Test error during shutdown."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        # Create a simple dictionary to use instead of MagicMock
        test_record = {"id": "test", "data": "sample"}
        manager._records = {"test": test_record}
        
        # Define a function that raises an exception when called
        async def flush_error(*args, **kwargs):
            raise Exception("Test error")
        
        # Use the function directly
        manager._flush_records_to_disk = flush_error
        
        # Act
        result = await manager.shutdown()
        
        # Assert
        assert result is False
        assert manager._is_shutdown is True  # Should still be marked as shutdown
    
    @pytest.mark.asyncio
    async def test_flush_records_to_disk(self, sample_metrics_config, sample_record):
        """Test flushing records to disk."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        manager._records = {"record_123": sample_record}
        
        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Act
            result = await manager._flush_records_to_disk()
            
            # Assert
            assert result is True
            mock_open.assert_called_once_with(sample_metrics_config.output_path, 'w')
            assert mock_file.write.called  # Just check that write was called, not how many times
    
    @pytest.mark.asyncio
    async def test_flush_records_to_disk_no_output_path(self, sample_metrics_config):
        """Test flushing records to disk with no output path."""
        # Arrange
        metrics_config = MetricsConfig(
            enabled_metrics=["latency", "tps"],
            output_format="json",
            output_path=None
        )
        manager = RecordsManager(metrics_config=metrics_config)
        
        # Act
        result = await manager._flush_records_to_disk()
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_handle_command_store_record(self, sample_metrics_config, sample_record):
        """Test handling store_record command."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        with patch.object(manager, "store_record", return_value=True):
            # Act
            response = await manager.handle_command("store_record", {"record": sample_record.__dict__})
            
            # Assert
            assert response["status"] == "success"
            assert response["message"] == "Record stored"
    
    @pytest.mark.asyncio
    async def test_handle_command_get_records(self, sample_metrics_config, sample_record):
        """Test handling get_records command."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        with patch.object(manager, "get_records", return_value=[sample_record.__dict__]):
            # Act
            response = await manager.handle_command("get_records", {"filters": {"record_id": "record_123"}})
            
            # Assert
            assert response["status"] == "success"
            assert len(response["records"]) == 1
            assert response["records"][0] == sample_record.__dict__
    
    @pytest.mark.asyncio
    async def test_handle_command_unknown(self, sample_metrics_config):
        """Test handling unknown command."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        # Act
        response = await manager.handle_command("unknown_command")
        
        # Assert
        assert response["status"] == "error"
        assert "Unknown command" in response["message"]
    
    @pytest.mark.asyncio
    async def test_handle_records_request(self, sample_metrics_config, mock_communication):
        """Test handling records request."""
        # Arrange
        manager = RecordsManager(
            metrics_config=sample_metrics_config,
            communication=mock_communication
        )
        
        with patch.object(manager, "get_records", return_value=[{"record_id": "record_123"}]):
            # Create a request message
            message = {
                "client_id": "test_client",
                "data": {
                    "request_id": "req_123",
                    "action": "get_records",
                    "filters": {"record_id": "record_123"}
                }
            }
            
            # Act
            await manager._handle_records_request(message)
            
            # Assert
            mock_communication.respond.assert_called_once()
            call_args = mock_communication.respond.call_args[0]
            assert call_args[0] == "test_client"
            assert call_args[1] == "req_123"
            assert call_args[2]["status"] == "success"
            assert len(call_args[2]["records"]) == 1
    
    @pytest.mark.asyncio
    async def test_store_record(self, sample_metrics_config, sample_record):
        """Test storing a record."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        # Act
        result = await manager.store_record(sample_record)
        
        # Assert
        assert result is True
        assert sample_record.record_id in manager._records
        
    @pytest.mark.asyncio
    async def test_store_record_with_listeners(self, sample_metrics_config, sample_record):
        """Test storing a record with listeners."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        listener = MagicMock()
        await manager.add_listener(listener)
        
        # Act
        result = await manager.store_record(sample_record)
        
        # Assert
        assert result is True
        assert sample_record.record_id in manager._records
        listener.assert_called_once_with(sample_record)
    
    @pytest.mark.asyncio
    async def test_get_records_with_filters(self, sample_metrics_config, sample_record):
        """Test getting records with filters."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        manager._records = {"record_123": sample_record}
        
        # Act
        records = await manager.get_records({"record_id": "record_123"})
        
        # Assert
        assert len(records) == 1
        assert records[0]["record_id"] == "record_123"
    
    @pytest.mark.asyncio
    async def test_get_records_with_conversation_filter(self, sample_metrics_config, sample_record):
        """Test getting records with conversation filter."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        manager._records = {"record_123": sample_record}
        manager._records_by_conversation = {"conv_123": ["record_123"]}
        
        # Act
        records = await manager.get_records({"conversation_id": "conv_123"})
        
        # Assert
        assert len(records) == 1
        assert records[0]["record_id"] == "record_123"
    
    @pytest.mark.asyncio
    async def test_get_records_no_matches(self, sample_metrics_config, sample_record):
        """Test getting records with no matches."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        manager._records = {"record_123": sample_record}
        
        # Act
        records = await manager.get_records({"record_id": "nonexistent"})
        
        # Assert
        assert len(records) == 0
    
    @pytest.mark.asyncio
    async def test_get_record(self, sample_metrics_config, sample_record):
        """Test getting a single record."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        manager._records = {"record_123": sample_record}
        
        # Act
        record = await manager.get_record("record_123")
        
        # Assert
        assert record is not None
        assert record.record_id == "record_123"
    
    @pytest.mark.asyncio
    async def test_get_record_nonexistent(self, sample_metrics_config):
        """Test getting a nonexistent record."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        
        # Act
        record = await manager.get_record("nonexistent")
        
        # Assert
        assert record is None
    
    @pytest.mark.asyncio
    async def test_add_listener(self, sample_metrics_config):
        """Test adding a record listener."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        listener = MagicMock()
        
        # Act
        result = await manager.add_listener(listener)
        
        # Assert
        assert result is True
        assert listener in manager._record_listeners
    
    @pytest.mark.asyncio
    async def test_get_stats(self, sample_metrics_config, sample_record):
        """Test getting stats."""
        # Arrange
        manager = RecordsManager(metrics_config=sample_metrics_config)
        manager._records = {"record_123": sample_record}
        manager._records_by_conversation = {"conv_123": ["record_123"]}
        
        # Act
        stats = await manager.get_stats()
        
        # Assert
        assert stats["records_count"] == 1
        assert stats["total_conversations"] == 1
        assert stats["total_records"] == 1
        assert stats["total_metrics"] == 2 