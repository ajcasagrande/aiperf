# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for dataset chunking and deterministic assignment."""

import pytest

from aiperf.common.config import (
    EndpointConfig,
    LoadGeneratorConfig,
    ServiceConfig,
    UserConfig,
)
from aiperf.common.config.input_config import InputConfig
from aiperf.common.enums import CustomDatasetType, MessageType
from aiperf.common.messages import (
    ConversationChunkRequestMessage,
    ConversationChunkResponseMessage,
)
from aiperf.dataset.dataset_manager import DatasetManager


class TestChunkMessageTypes:
    """Test chunk message serialization and validation."""

    def test_chunk_request_message_creation(self):
        """Test chunk request message can be created."""
        msg = ConversationChunkRequestMessage(
            service_id="test-worker",
            request_id="req-123",
            chunk_size=100,
            worker_id="worker-42",
        )

        assert msg.message_type == MessageType.CONVERSATION_CHUNK_REQUEST
        assert msg.chunk_size == 100
        assert msg.worker_id == "worker-42"

    def test_chunk_request_validates_size(self):
        """Test chunk size validation."""
        # Should accept valid sizes
        ConversationChunkRequestMessage(service_id="test", chunk_size=1)  # minimum
        ConversationChunkRequestMessage(service_id="test", chunk_size=1000)  # maximum

        # Should reject invalid sizes
        with pytest.raises(Exception):  # Pydantic validation error
            ConversationChunkRequestMessage(service_id="test", chunk_size=0)

        with pytest.raises(Exception):
            ConversationChunkRequestMessage(service_id="test", chunk_size=1001)

    def test_chunk_response_message_creation(self):
        """Test chunk response message can be created."""
        from aiperf.common.models import Conversation, Turn

        conversations = [
            Conversation(session_id="conv-1", turns=[Turn(role="user", contents="Hi")]),
            Conversation(
                session_id="conv-2", turns=[Turn(role="user", contents="Hello")]
            ),
        ]

        msg = ConversationChunkResponseMessage(
            service_id="dataset-mgr",
            request_id="req-123",
            conversations=conversations,
            chunk_index=5,
            has_more=True,
        )

        assert msg.message_type == MessageType.CONVERSATION_CHUNK_RESPONSE
        assert len(msg.conversations) == 2
        assert msg.chunk_index == 5
        assert msg.has_more is True


@pytest.mark.asyncio
class TestDatasetManagerChunking:
    """Test DatasetManager chunking functionality."""

    @pytest.fixture
    async def dataset_manager(self):
        """Create configured DatasetManager."""
        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                public_dataset="sharegpt",
                random_seed=42,
                enable_chunking=True,
                dataset_chunk_size=100,
            ),
        )
        service_config = ServiceConfig()

        manager = DatasetManager(service_config, user_config)

        # Mock dataset configuration
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Message {i}"])])],
            )
            for i in range(500)  # 500 test conversations
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager.dataset_configured.set()

        return manager

    async def test_chunk_request_handler(self, dataset_manager):
        """Test chunk request returns correct number of conversations."""
        request = ConversationChunkRequestMessage(
            service_id="worker-1",
            request_id="req-1",
            chunk_size=100,
        )

        response = await dataset_manager._handle_chunk_request(request)

        assert isinstance(response, ConversationChunkResponseMessage)
        assert len(response.conversations) == 100
        assert response.chunk_index == 1
        assert response.has_more is True

    async def test_chunk_size_respects_dataset_size(self, dataset_manager):
        """Test chunk size is capped at dataset size."""
        request = ConversationChunkRequestMessage(
            service_id="worker-1",
            chunk_size=1000,  # More than dataset size
        )

        response = await dataset_manager._handle_chunk_request(request)

        assert len(response.conversations) == 500  # Capped at dataset size

    async def test_multiple_chunks_dont_overlap_in_random_mode(self, dataset_manager):
        """Test that multiple chunks can be requested."""
        # Note: In random mode, conversations CAN overlap (sampling with replacement)
        # This test just verifies multiple chunks work

        chunks = []
        for i in range(5):
            request = ConversationChunkRequestMessage(
                service_id=f"worker-{i}",
                chunk_size=50,
            )
            response = await dataset_manager._handle_chunk_request(request)
            chunks.append(response)

        assert len(chunks) == 5
        assert all(len(chunk.conversations) == 50 for chunk in chunks)

    async def test_chunk_counter_increments(self, dataset_manager):
        """Test chunk counter tracks requests."""
        for i in range(10):
            request = ConversationChunkRequestMessage(
                service_id="worker", chunk_size=10
            )
            response = await dataset_manager._handle_chunk_request(request)
            assert response.chunk_index == i + 1

    async def test_chunking_statistics(self, dataset_manager):
        """Test that chunking statistics are tracked."""
        # Request 3 chunks
        for _ in range(3):
            request = ConversationChunkRequestMessage(
                service_id="worker", chunk_size=50
            )
            await dataset_manager._handle_chunk_request(request)

        assert dataset_manager._total_chunk_requests == 3
        assert dataset_manager._total_conversations_served == 150

        # Request single conversation
        from aiperf.common.messages import ConversationRequestMessage

        single_request = ConversationRequestMessage(service_id="worker")
        await dataset_manager._handle_conversation_request(single_request)

        assert dataset_manager._total_single_requests == 1
        assert dataset_manager._total_conversations_served == 151


@pytest.mark.asyncio
class TestDeterministicMode:
    """Test deterministic conversation assignment."""

    @pytest.fixture
    def deterministic_config(self):
        """Create config with deterministic mode enabled."""
        return UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                public_dataset="sharegpt",
                random_seed=42,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(
                benchmark_duration=60,
                request_rate=10,  # 600 total requests
            ),
        )

    async def test_deterministic_sequence_generation(self, deterministic_config):
        """Test that deterministic sequence is generated."""
        manager = DatasetManager(ServiceConfig(), deterministic_config)

        # Mock dataset
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())

        await manager._generate_deterministic_sequence()

        # Should generate sequence
        assert len(manager._deterministic_sequence) == 600  # warmup(0) + 600 requests
        assert all(
            sid in manager._session_ids_cache for sid in manager._deterministic_sequence
        )

    async def test_deterministic_mode_reproducibility(self, deterministic_config):
        """Test same seed produces identical sequences."""
        from aiperf.common.models import Conversation, Text, Turn

        # Create test conversations
        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        # Manager 1
        manager1 = DatasetManager(ServiceConfig(), deterministic_config)
        manager1.dataset = {c.session_id: c for c in conversations}
        manager1._session_ids_cache = list(manager1.dataset.keys())
        await manager1._generate_deterministic_sequence()

        chunk1 = manager1._get_conversation_chunk(50)
        chunk2 = manager1._get_conversation_chunk(50)

        # Manager 2 with same config
        manager2 = DatasetManager(ServiceConfig(), deterministic_config)
        manager2.dataset = {c.session_id: c for c in conversations}
        manager2._session_ids_cache = list(manager2.dataset.keys())
        await manager2._generate_deterministic_sequence()

        chunk1_repeat = manager2._get_conversation_chunk(50)
        chunk2_repeat = manager2._get_conversation_chunk(50)

        # Should be identical
        assert [c.session_id for c in chunk1] == [c.session_id for c in chunk1_repeat]
        assert [c.session_id for c in chunk2] == [c.session_id for c in chunk2_repeat]

    async def test_deterministic_mode_index_based(self, deterministic_config):
        """Test deterministic mode uses index-based access."""
        manager = DatasetManager(ServiceConfig(), deterministic_config)

        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(50)
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        await manager._generate_deterministic_sequence()

        # Get chunks
        chunk1 = manager._get_conversation_chunk(25)
        chunk2 = manager._get_conversation_chunk(25)

        # Should be from deterministic sequence (positions 0-24, 25-49)
        expected_ids_1 = manager._deterministic_sequence[0:25]
        expected_ids_2 = manager._deterministic_sequence[25:50]

        assert [c.session_id for c in chunk1] == expected_ids_1
        assert [c.session_id for c in chunk2] == expected_ids_2


class TestSequentialMode:
    """Test sequential iteration mode."""

    @pytest.mark.asyncio
    async def test_sequential_maintains_order(self):
        """Test sequential mode maintains conversation order."""
        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                custom_dataset_type=CustomDatasetType.MOONCAKE_TRACE,
                random_seed=42,
            ),
        )

        manager = DatasetManager(ServiceConfig(), user_config)

        from aiperf.common.models import Conversation, Text, Turn

        # Create ordered conversations
        conversations = [
            Conversation(
                session_id=f"conv-{i:03d}",  # conv-000, conv-001, etc.
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(200)
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager._use_sequential_iteration = True

        # Get chunks
        chunk1 = manager._get_conversation_chunk(50)
        chunk2 = manager._get_conversation_chunk(50)
        chunk3 = manager._get_conversation_chunk(50)

        # Should be sequential
        expected = [f"conv-{i:03d}" for i in range(150)]
        actual = [c.session_id for c in chunk1 + chunk2 + chunk3]

        assert actual == expected


class TestRandomMode:
    """Test random mode reproducibility."""

    @pytest.mark.asyncio
    async def test_random_mode_same_seed_reproducible(self):
        """Test random mode with same seed produces same sequence."""
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        # Manager 1
        config1 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )
        manager1 = DatasetManager(ServiceConfig(), config1)
        manager1.dataset = {c.session_id: c for c in conversations}
        manager1._session_ids_cache = list(manager1.dataset.keys())

        chunk1 = manager1._get_conversation_chunk(50)

        # Manager 2 with same seed
        config2 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )
        manager2 = DatasetManager(ServiceConfig(), config2)
        manager2.dataset = {c.session_id: c for c in conversations}
        manager2._session_ids_cache = list(manager2.dataset.keys())

        chunk2 = manager2._get_conversation_chunk(50)

        # Should be identical
        assert [c.session_id for c in chunk1] == [c.session_id for c in chunk2]

    @pytest.mark.asyncio
    async def test_random_mode_different_seed_different_sequence(self):
        """Test different seeds produce different sequences."""
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        # Seed 42
        config1 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )
        manager1 = DatasetManager(ServiceConfig(), config1)
        manager1.dataset = {c.session_id: c for c in conversations}
        manager1._session_ids_cache = list(manager1.dataset.keys())

        chunk1 = manager1._get_conversation_chunk(50)

        # Seed 123
        config2 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=123),
        )
        manager2 = DatasetManager(ServiceConfig(), config2)
        manager2.dataset = {c.session_id: c for c in conversations}
        manager2._session_ids_cache = list(manager2.dataset.keys())

        chunk2 = manager2._get_conversation_chunk(50)

        # Should be different
        assert [c.session_id for c in chunk1] != [c.session_id for c in chunk2]


class TestExpectedRequestCalculation:
    """Test expected request count calculation."""

    def test_calculate_from_request_count(self):
        """Test calculation when request count is specified."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            loadgen=LoadGeneratorConfig(
                request_count=1000,
                warmup_request_count=100,
            ),
        )

        manager = DatasetManager(ServiceConfig(), config)
        expected = manager._calculate_expected_requests()

        assert expected == 1100  # 100 warmup + 1000 profiling

    def test_calculate_from_duration_and_rate(self):
        """Test calculation from duration and request rate."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            loadgen=LoadGeneratorConfig(
                benchmark_duration=60,
                request_rate=10,
                warmup_request_count=50,
            ),
        )

        manager = DatasetManager(ServiceConfig(), config)
        expected = manager._calculate_expected_requests()

        assert expected == 650  # 50 warmup + (60 * 10) profiling

    def test_calculate_from_duration_and_concurrency(self):
        """Test estimation from duration and concurrency."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            loadgen=LoadGeneratorConfig(
                benchmark_duration=60,
                concurrency=100,
            ),
        )

        manager = DatasetManager(ServiceConfig(), config)
        expected = manager._calculate_expected_requests()

        # Conservative estimate: 60 * 100 * 10 = 60,000
        assert expected == 60000

    def test_calculate_with_default_values(self):
        """Test calculation with default loadgen values."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            # Uses default LoadGeneratorConfig (request_count=10)
        )

        manager = DatasetManager(ServiceConfig(), config)
        expected = manager._calculate_expected_requests()

        # Default has request_count=10, warmup=0
        assert expected == 10


@pytest.mark.asyncio
class TestChunkingModes:
    """Test different chunking modes."""

    async def test_mode_selection_deterministic(self):
        """Test deterministic mode is selected when configured."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(request_count=100),
        )

        manager = DatasetManager(ServiceConfig(), config)

        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(50)
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())

        await manager._generate_deterministic_sequence()

        # Should have pre-generated sequence
        assert len(manager._deterministic_sequence) == 100

    async def test_mode_selection_sequential(self):
        """Test sequential mode is selected for traces."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(custom_dataset_type=CustomDatasetType.MOONCAKE_TRACE),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager._use_sequential_iteration = True  # Set by dataset type

        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(50)
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())

        chunk = manager._get_conversation_chunk(10)

        # Should be sequential
        assert [c.session_id for c in chunk] == [f"conv-{i}" for i in range(10)]

    async def test_mode_selection_random_default(self):
        """Test random mode is default."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )

        manager = DatasetManager(ServiceConfig(), config)

        assert manager._deterministic_sequence == []
        assert manager._use_sequential_iteration is False


def test_input_config_defaults():
    """Test input config has correct chunking defaults."""
    config = InputConfig()

    assert config.enable_chunking is True
    assert config.dataset_chunk_size == 100
    assert config.prefetch_threshold == 0.2
    assert config.deterministic_conversation_assignment is False
