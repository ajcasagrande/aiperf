# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import pickle
from typing import Any

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False
from pydantic import BaseModel, Field

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.models import Conversation
from aiperf.dataset.mmap_dataset_manager import MMapDatasetError

_logger = AIPerfLogger(__name__)


class RedisDatasetConfig(BaseModel):
    """Configuration for Redis-based dataset caching."""

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database number")
    password: str | None = Field(default=None, description="Redis password")
    key_prefix: str = Field(
        default="aiperf:dataset", description="Key prefix for dataset entries"
    )
    ttl_seconds: int = Field(
        default=3600, description="Time-to-live for cached entries"
    )
    max_connections: int = Field(
        default=20, description="Maximum Redis connection pool size"
    )
    use_compression: bool = Field(
        default=True, description="Whether to compress stored data"
    )


class RedisDatasetCache:
    """
    Redis-based distributed dataset cache for multi-node deployments.

    This cache stores conversation data in Redis, allowing workers across multiple
    nodes to access the same dataset efficiently. Includes compression, TTL management,
    and connection pooling for optimal performance.
    """

    def __init__(self, config: RedisDatasetConfig) -> None:
        """Initialize Redis dataset cache."""
        self.config = config
        self._redis: redis.Redis | None = None
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if not REDIS_AVAILABLE:
            raise MMapDatasetError(
                "Redis is not available. Install with: pip install redis"
            )

        try:
            self._redis = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                max_connections=self.config.max_connections,
                decode_responses=False,  # We handle binary data
            )

            # Test connection
            await self._redis.ping()
            self._connected = True

            _logger.info(
                "Connected to Redis dataset cache",
                extra={
                    "host": self.config.host,
                    "port": self.config.port,
                    "db": self.config.db,
                    "compression": self.config.use_compression,
                },
            )

        except Exception as e:
            _logger.error(f"Failed to connect to Redis: {e}")
            raise MMapDatasetError(f"Redis connection failed: {e}") from e

    async def store_dataset(
        self, dataset: dict[str, Conversation], dataset_id: str
    ) -> None:
        """Store entire dataset in Redis with optional compression."""
        if not self._connected or not self._redis:
            raise MMapDatasetError("Redis not connected")

        try:
            pipe = self._redis.pipeline()

            # Store metadata
            metadata = {
                "dataset_id": dataset_id,
                "conversation_count": len(dataset),
                "session_ids": list(dataset.keys()),
                "compression": self.config.use_compression,
                "format": "pickle" if self.config.use_compression else "json",
            }

            metadata_key = f"{self.config.key_prefix}:{dataset_id}:meta"
            pipe.set(metadata_key, json.dumps(metadata), ex=self.config.ttl_seconds)

            # Store individual conversations
            for session_id, conversation in dataset.items():
                conv_key = f"{self.config.key_prefix}:{dataset_id}:conv:{session_id}"

                if self.config.use_compression:
                    # Use pickle for binary compression
                    conv_data = pickle.dumps(conversation.model_dump())
                else:
                    # Use JSON for human-readable format
                    conv_data = conversation.model_dump_json().encode("utf-8")

                pipe.set(conv_key, conv_data, ex=self.config.ttl_seconds)

            # Execute pipeline
            await pipe.execute()

            _logger.info(
                "Stored dataset in Redis cache",
                extra={
                    "dataset_id": dataset_id,
                    "conversations": len(dataset),
                    "compression": self.config.use_compression,
                    "ttl_seconds": self.config.ttl_seconds,
                },
            )

        except Exception as e:
            _logger.error(f"Failed to store dataset in Redis: {e}")
            raise MMapDatasetError(f"Failed to store dataset: {e}") from e

    async def get_conversation(
        self, dataset_id: str, session_id: str
    ) -> Conversation | None:
        """Retrieve a specific conversation from Redis cache."""
        if not self._connected or not self._redis:
            raise MMapDatasetError("Redis not connected")

        try:
            conv_key = f"{self.config.key_prefix}:{dataset_id}:conv:{session_id}"
            conv_data = await self._redis.get(conv_key)

            if not conv_data:
                return None

            # Get metadata to determine format
            metadata_key = f"{self.config.key_prefix}:{dataset_id}:meta"
            metadata_raw = await self._redis.get(metadata_key)

            if metadata_raw:
                metadata = json.loads(metadata_raw.decode("utf-8"))
                use_compression = metadata.get("compression", False)
            else:
                use_compression = self.config.use_compression

            # Deserialize based on format
            if use_compression:
                conv_dict = pickle.loads(conv_data)
            else:
                conv_dict = json.loads(conv_data.decode("utf-8"))

            return Conversation.model_validate(conv_dict)

        except Exception as e:
            _logger.warning(f"Failed to retrieve conversation {session_id}: {e}")
            return None

    async def get_random_conversation(self, dataset_id: str) -> Conversation | None:
        """Get a random conversation from the dataset."""
        if not self._connected or not self._redis:
            raise MMapDatasetError("Redis not connected")

        try:
            # Get metadata first
            metadata_key = f"{self.config.key_prefix}:{dataset_id}:meta"
            metadata_raw = await self._redis.get(metadata_key)

            if not metadata_raw:
                return None

            metadata = json.loads(metadata_raw.decode("utf-8"))
            session_ids = metadata.get("session_ids", [])

            if not session_ids:
                return None

            # Pick random session
            import random

            session_id = random.choice(session_ids)
            return await self.get_conversation(dataset_id, session_id)

        except Exception as e:
            _logger.warning(f"Failed to get random conversation: {e}")
            return None

    async def get_dataset_info(self, dataset_id: str) -> dict[str, Any] | None:
        """Get dataset metadata."""
        if not self._connected or not self._redis:
            raise MMapDatasetError("Redis not connected")

        try:
            metadata_key = f"{self.config.key_prefix}:{dataset_id}:meta"
            metadata_raw = await self._redis.get(metadata_key)

            if metadata_raw:
                return json.loads(metadata_raw.decode("utf-8"))
            return None

        except Exception as e:
            _logger.warning(f"Failed to get dataset info: {e}")
            return None

    async def delete_dataset(self, dataset_id: str) -> None:
        """Delete entire dataset from Redis cache."""
        if not self._connected or not self._redis:
            raise MMapDatasetError("Redis not connected")

        try:
            # Get all keys for this dataset
            pattern = f"{self.config.key_prefix}:{dataset_id}:*"
            keys = []

            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await self._redis.delete(*keys)
                _logger.info(f"Deleted dataset {dataset_id} ({len(keys)} keys)")

        except Exception as e:
            _logger.error(f"Failed to delete dataset {dataset_id}: {e}")
            raise MMapDatasetError(f"Failed to delete dataset: {e}") from e

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._connected = False
            _logger.debug("Closed Redis connection")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class DistributedRedisDatasetManager:
    """
    Distributed dataset manager using Redis as the backend.

    Combines local memory-mapped files for performance with Redis distribution
    for multi-node access. Provides intelligent caching and fallback strategies.
    """

    def __init__(
        self,
        dataset: dict[str, Conversation],
        redis_config: RedisDatasetConfig,
        dataset_id: str,
        enable_local_cache: bool = True,
    ) -> None:
        """Initialize distributed Redis dataset manager."""
        self.dataset = dataset
        self.dataset_id = dataset_id
        self.enable_local_cache = enable_local_cache

        self.redis_cache = RedisDatasetCache(redis_config)
        self._local_cache: dict[str, Conversation] = {}

    async def initialize(self) -> None:
        """Initialize the distributed dataset manager."""
        await self.redis_cache.connect()
        await self.redis_cache.store_dataset(self.dataset, self.dataset_id)

        if self.enable_local_cache:
            self._local_cache = self.dataset.copy()

    async def get_conversation(
        self, session_id: str | None = None
    ) -> Conversation | None:
        """Get conversation with multi-level caching."""
        if session_id is None:
            return await self.redis_cache.get_random_conversation(self.dataset_id)

        # Try local cache first
        if self.enable_local_cache and session_id in self._local_cache:
            return self._local_cache[session_id]

        # Fall back to Redis
        conversation = await self.redis_cache.get_conversation(
            self.dataset_id, session_id
        )

        # Cache locally for future access
        if conversation and self.enable_local_cache:
            self._local_cache[session_id] = conversation

        return conversation

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.redis_cache.close()
        self._local_cache.clear()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
