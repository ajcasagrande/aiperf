# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import tempfile
from pathlib import Path

import pytest

from aiperf.common.models import Conversation, Turn
from aiperf.common.models.dataset_models import Text
from aiperf.dataset.multi_node_dataset_manager import (
    DeploymentMode,
    MultiNodeConfig,
    MultiNodeDatasetManager,
)
from aiperf.dataset.redis_dataset_cache import RedisDatasetConfig


class TestMultiNodeDatasetManager:
    """Test multi-node dataset management capabilities."""

    @pytest.fixture
    def sample_conversations(self):
        """Create sample conversations for testing."""
        return {
            "session1": Conversation(
                session_id="session1",
                turns=[Turn(timestamp=1000, texts=[Text(contents=["Hello"])])],
            ),
            "session2": Conversation(
                session_id="session2",
                turns=[Turn(timestamp=2000, texts=[Text(contents=["World"])])],
            ),
            "session3": Conversation(
                session_id="session3",
                turns=[Turn(timestamp=3000, texts=[Text(contents=["Test"])])],
            ),
        }

    def test_single_node_mode(self, sample_conversations):
        """Test single-node deployment mode."""
        config = MultiNodeConfig(deployment_mode=DeploymentMode.SINGLE_NODE)

        async def test_single_node():
            async with MultiNodeDatasetManager(sample_conversations, config) as manager:
                assert manager.get_deployment_mode() == DeploymentMode.SINGLE_NODE

                # Test conversation access
                conv = await manager.get_conversation("session1")
                assert conv is not None
                assert conv.session_id == "session1"

                # Test random access
                random_conv = await manager.get_conversation()
                assert random_conv is not None
                assert random_conv.session_id in sample_conversations

        asyncio.run(test_single_node())

    def test_shared_storage_mode(self, sample_conversations):
        """Test shared storage deployment mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MultiNodeConfig(
                deployment_mode=DeploymentMode.SHARED_STORAGE,
                shared_storage_path=temp_dir,
            )

            async def test_shared_storage():
                async with MultiNodeDatasetManager(
                    sample_conversations, config
                ) as manager:
                    assert (
                        manager.get_deployment_mode() == DeploymentMode.SHARED_STORAGE
                    )

                    # Verify files are created in shared storage
                    shared_path = Path(temp_dir)
                    dataset_dirs = list(shared_path.glob("aiperf_datasets/dataset_*"))
                    assert len(dataset_dirs) > 0

            asyncio.run(test_shared_storage())

    def test_auto_mode_detection(self, sample_conversations):
        """Test automatic mode detection."""
        config = MultiNodeConfig(deployment_mode=DeploymentMode.AUTO)

        async def test_auto_detection():
            async with MultiNodeDatasetManager(sample_conversations, config) as manager:
                # Should fall back to single-node mode since no distributed storage is available
                assert manager.get_deployment_mode() == DeploymentMode.SINGLE_NODE

                info = manager.get_dataset_info()
                assert "dataset_id" in info
                assert "node_id" in info
                assert info["conversations_count"] == 3

        asyncio.run(test_auto_detection())

    def test_config_validation(self, sample_conversations):
        """Test configuration validation."""
        # Test with Redis config
        redis_config = RedisDatasetConfig(
            host="localhost", port=6379, use_compression=True
        )

        config = MultiNodeConfig(
            deployment_mode=DeploymentMode.REDIS_DISTRIBUTED,
            redis_config=redis_config,
            enable_compression=True,
        )

        manager = MultiNodeDatasetManager(sample_conversations, config)
        assert manager.config.redis_config is not None
        assert manager.config.enable_compression is True

    @pytest.mark.skipif(
        True,  # Skip by default since it requires Redis server
        reason="Requires Redis server for testing",
    )
    def test_redis_distributed_mode(self, sample_conversations):
        """Test Redis distributed deployment mode (requires Redis server)."""
        redis_config = RedisDatasetConfig(
            host="localhost",
            port=6379,
            db=15,  # Use test database
            ttl_seconds=60,
        )

        config = MultiNodeConfig(
            deployment_mode=DeploymentMode.REDIS_DISTRIBUTED,
            redis_config=redis_config,
        )

        async def test_redis_mode():
            async with MultiNodeDatasetManager(sample_conversations, config) as manager:
                assert manager.get_deployment_mode() == DeploymentMode.REDIS_DISTRIBUTED

                # Test conversation access
                conv = await manager.get_conversation("session1")
                assert conv is not None
                assert conv.session_id == "session1"

        asyncio.run(test_redis_mode())

    def test_error_handling(self, sample_conversations):
        """Test error handling and fallback behavior."""
        # Test with invalid shared storage path
        config = MultiNodeConfig(
            deployment_mode=DeploymentMode.SHARED_STORAGE,
            shared_storage_path="/nonexistent/path",
        )

        async def test_fallback():
            async with MultiNodeDatasetManager(sample_conversations, config) as manager:
                # Should fall back to single-node mode
                assert manager.get_deployment_mode() == DeploymentMode.SINGLE_NODE

        asyncio.run(test_fallback())

    def test_dataset_info(self, sample_conversations):
        """Test dataset information retrieval."""
        config = MultiNodeConfig(
            deployment_mode=DeploymentMode.SINGLE_NODE,
            enable_compression=True,
        )

        async def test_info():
            async with MultiNodeDatasetManager(sample_conversations, config) as manager:
                info = manager.get_dataset_info()

                assert info["conversations_count"] == 3
                assert info["compression_enabled"] is True
                assert info["deployment_mode"] == DeploymentMode.SINGLE_NODE
                assert "dataset_id" in info
                assert "node_id" in info

        asyncio.run(test_info())

    def test_hybrid_mode_fallback(self, sample_conversations):
        """Test hybrid mode with fallback strategies."""
        config = MultiNodeConfig(
            deployment_mode=DeploymentMode.HYBRID,
            fallback_timeout=1.0,  # Short timeout for testing
        )

        async def test_hybrid():
            async with MultiNodeDatasetManager(sample_conversations, config) as manager:
                # Should fall back to single-node mode
                assert manager.get_deployment_mode() == DeploymentMode.SINGLE_NODE

                # Verify functionality
                conv = await manager.get_conversation("session2")
                assert conv is not None
                assert conv.session_id == "session2"

        asyncio.run(test_hybrid())


class TestRedisDatasetCache:
    """Test Redis-based dataset caching (integration tests)."""

    @pytest.fixture
    def redis_config(self):
        """Redis configuration for testing."""
        return RedisDatasetConfig(
            host="localhost",
            port=6379,
            db=15,  # Use test database
            ttl_seconds=30,
            use_compression=True,
        )

    @pytest.fixture
    def sample_conversations(self):
        """Sample conversations for testing."""
        return {
            "test1": Conversation(
                session_id="test1",
                turns=[Turn(timestamp=1000, texts=[Text(contents=["Redis test"])])],
            ),
        }

    @pytest.mark.skipif(
        True,  # Skip by default since it requires Redis server
        reason="Requires Redis server for testing",
    )
    def test_redis_cache_operations(self, redis_config, sample_conversations):
        """Test Redis cache operations (requires Redis server)."""
        from aiperf.dataset.redis_dataset_cache import RedisDatasetCache

        async def test_redis():
            async with RedisDatasetCache(redis_config) as cache:
                dataset_id = "test_dataset"

                # Store dataset
                await cache.store_dataset(sample_conversations, dataset_id)

                # Retrieve conversation
                conv = await cache.get_conversation(dataset_id, "test1")
                assert conv is not None
                assert conv.session_id == "test1"

                # Get dataset info
                info = await cache.get_dataset_info(dataset_id)
                assert info is not None
                assert info["conversation_count"] == 1

                # Clean up
                await cache.delete_dataset(dataset_id)

        asyncio.run(test_redis())
