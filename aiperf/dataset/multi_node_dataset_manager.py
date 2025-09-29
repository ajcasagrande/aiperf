# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import socket
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.models import Conversation
from aiperf.dataset.distributed_dataset_manager import (
    DistributedDatasetManager,
    DistributedStorageType,
)
from aiperf.dataset.mmap_dataset_manager import MMapDatasetError, MMapDatasetManager
from aiperf.dataset.redis_dataset_cache import (
    DistributedRedisDatasetManager,
    RedisDatasetConfig,
)

_logger = AIPerfLogger(__name__)


class DeploymentMode(str, Enum):
    """Deployment modes for dataset distribution."""

    SINGLE_NODE = "single_node"
    SHARED_STORAGE = "shared_storage"
    REDIS_DISTRIBUTED = "redis_distributed"
    HYBRID = "hybrid"
    AUTO = "auto"


class MultiNodeConfig(BaseModel):
    """Configuration for multi-node dataset management."""

    deployment_mode: DeploymentMode = Field(
        default=DeploymentMode.AUTO,
        description="Deployment mode for dataset distribution",
    )

    # Shared storage configuration
    shared_storage_path: str | None = Field(
        default=None, description="Path to shared storage mount (NFS, CephFS, etc.)"
    )
    storage_type: str = Field(
        default=DistributedStorageType.NFS, description="Type of shared storage backend"
    )

    # Redis configuration
    redis_config: RedisDatasetConfig | None = Field(
        default=None, description="Redis configuration for distributed caching"
    )

    # Hybrid mode configuration
    prefer_local_cache: bool = Field(
        default=True, description="Prefer local caching in hybrid mode"
    )
    fallback_timeout: float = Field(
        default=5.0, description="Timeout for fallback operations"
    )

    # Performance tuning
    enable_compression: bool = Field(
        default=True, description="Enable compression for network efficiency"
    )
    max_retry_attempts: int = Field(
        default=3, description="Maximum retry attempts for failed operations"
    )


class MultiNodeDatasetManager:
    """
    Intelligent multi-node dataset manager that automatically selects
    the best distribution strategy based on environment and configuration.

    Supports:
    - Single-node memory-mapped files (optimal performance)
    - Shared storage (NFS, CephFS) for simple multi-node setups
    - Redis distributed caching for high-performance multi-node
    - Hybrid mode with intelligent fallbacks
    """

    def __init__(
        self,
        dataset: dict[str, Conversation],
        config: MultiNodeConfig,
        random_seed: int | None = None,
        use_sequential_iteration: bool = False,
    ) -> None:
        """Initialize multi-node dataset manager."""
        if not dataset:
            raise MMapDatasetError("Dataset cannot be empty")

        self.dataset = dataset
        self.config = config
        self.random_seed = random_seed
        self.use_sequential_iteration = use_sequential_iteration

        self._active_manager: Any = None
        self._deployment_mode: DeploymentMode | None = None
        self._dataset_id = self._generate_dataset_id()
        self._node_id = self._get_node_id()

    def _generate_dataset_id(self) -> str:
        """Generate unique dataset ID."""
        import hashlib
        import time

        # Create hash from dataset content and timestamp
        content_hash = hashlib.md5(
            str(sorted(self.dataset.keys())).encode("utf-8")
        ).hexdigest()[:8]

        return f"dataset_{content_hash}_{int(time.time())}"

    def _get_node_id(self) -> str:
        """Get unique node identifier."""
        import os

        return f"{socket.gethostname()}_{os.getpid()}"

    async def initialize(self) -> tuple[str, str] | None:
        """Initialize the dataset manager with automatic mode detection."""
        if self.config.deployment_mode == DeploymentMode.AUTO:
            self._deployment_mode = await self._detect_deployment_mode()
        else:
            self._deployment_mode = self.config.deployment_mode

        _logger.info(
            f"Initializing dataset manager in {self._deployment_mode} mode",
            extra={
                "dataset_id": self._dataset_id,
                "node_id": self._node_id,
                "conversations_count": len(self.dataset),
                "compression_enabled": self.config.enable_compression,
            },
        )

        try:
            if self._deployment_mode == DeploymentMode.SINGLE_NODE:
                return await self._initialize_single_node()
            elif self._deployment_mode == DeploymentMode.SHARED_STORAGE:
                return await self._initialize_shared_storage()
            elif self._deployment_mode == DeploymentMode.REDIS_DISTRIBUTED:
                return await self._initialize_redis_distributed()
            elif self._deployment_mode == DeploymentMode.HYBRID:
                return await self._initialize_hybrid()
            else:
                raise MMapDatasetError(
                    f"Unsupported deployment mode: {self._deployment_mode}"
                )

        except Exception as e:
            _logger.error(f"Failed to initialize dataset manager: {e}")
            # Fallback to single-node mode
            _logger.info("Falling back to single-node mode")
            self._deployment_mode = DeploymentMode.SINGLE_NODE
            return await self._initialize_single_node()

    async def _detect_deployment_mode(self) -> DeploymentMode:
        """Auto-detect the best deployment mode based on environment."""
        # Check for Redis availability
        if self.config.redis_config and await self._test_redis_connection():
            return DeploymentMode.REDIS_DISTRIBUTED

        # Check for shared storage
        if self.config.shared_storage_path and await self._test_shared_storage():
            return DeploymentMode.SHARED_STORAGE

        # Check if we're in a multi-node environment
        if await self._detect_multi_node_environment():
            _logger.warning(
                "Multi-node environment detected but no distributed storage available"
            )
            return (
                DeploymentMode.HYBRID
                if self.config.redis_config
                else DeploymentMode.SINGLE_NODE
            )

        return DeploymentMode.SINGLE_NODE

    async def _test_redis_connection(self) -> bool:
        """Test Redis connectivity."""
        if not self.config.redis_config:
            return False

        try:
            from aiperf.dataset.redis_dataset_cache import REDIS_AVAILABLE

            if not REDIS_AVAILABLE:
                return False

            import redis.asyncio as redis

            r = redis.Redis(
                host=self.config.redis_config.host,
                port=self.config.redis_config.port,
                password=self.config.redis_config.password,
                socket_timeout=2.0,
            )
            await r.ping()
            await r.aclose()
            return True
        except Exception:
            return False

    async def _test_shared_storage(self) -> bool:
        """Test shared storage accessibility."""
        if not self.config.shared_storage_path:
            return False

        try:
            from pathlib import Path

            shared_path = Path(self.config.shared_storage_path)
            return shared_path.exists() and shared_path.is_dir()
        except Exception:
            return False

    async def _detect_multi_node_environment(self) -> bool:
        """Detect if we're running in a multi-node environment."""
        # This is a simple heuristic - in practice, you might check:
        # - Kubernetes environment variables
        # - Docker Swarm labels
        # - Configuration files
        # - Network topology
        import os

        return bool(
            os.environ.get("KUBERNETES_SERVICE_HOST")
            or os.environ.get("DOCKER_SWARM_MODE")
            or os.environ.get("AIPERF_MULTI_NODE")
        )

    async def _initialize_single_node(self) -> tuple[str, str]:
        """Initialize single-node memory-mapped dataset."""
        self._active_manager = MMapDatasetManager(
            dataset=self.dataset,
            random_seed=self.random_seed,
            use_sequential_iteration=self.use_sequential_iteration,
            enable_compression=self.config.enable_compression,
        )

        return await self._active_manager.create_memory_mapped_files_async()

    async def _initialize_shared_storage(self) -> tuple[str, str]:
        """Initialize shared storage dataset."""
        self._active_manager = DistributedDatasetManager(
            dataset=self.dataset,
            storage_type=self.config.storage_type,
            shared_storage_path=self.config.shared_storage_path,
            random_seed=self.random_seed,
            use_sequential_iteration=self.use_sequential_iteration,
            enable_compression=self.config.enable_compression,
        )

        return await self._active_manager.create_distributed_dataset()

    async def _initialize_redis_distributed(self) -> tuple[str, str] | None:
        """Initialize Redis distributed dataset."""
        if not self.config.redis_config:
            raise MMapDatasetError(
                "Redis configuration required for Redis distributed mode"
            )

        self._active_manager = DistributedRedisDatasetManager(
            dataset=self.dataset,
            redis_config=self.config.redis_config,
            dataset_id=self._dataset_id,
            enable_local_cache=self.config.prefer_local_cache,
        )

        await self._active_manager.initialize()
        return None  # Redis mode doesn't use file paths

    async def _initialize_hybrid(self) -> tuple[str, str] | None:
        """Initialize hybrid mode with multiple fallback strategies."""
        # Try Redis first, then shared storage, finally local
        strategies = []

        if self.config.redis_config:
            strategies.append(self._initialize_redis_distributed)

        if self.config.shared_storage_path:
            strategies.append(self._initialize_shared_storage)

        strategies.append(self._initialize_single_node)

        for strategy in strategies:
            try:
                result = await asyncio.wait_for(
                    strategy(), timeout=self.config.fallback_timeout
                )
                _logger.info(f"Successfully initialized using {strategy.__name__}")

                # Update deployment mode based on successful strategy
                if strategy.__name__ == "_initialize_redis_distributed":
                    self._deployment_mode = DeploymentMode.REDIS_DISTRIBUTED
                elif strategy.__name__ == "_initialize_shared_storage":
                    self._deployment_mode = DeploymentMode.SHARED_STORAGE
                elif strategy.__name__ == "_initialize_single_node":
                    self._deployment_mode = DeploymentMode.SINGLE_NODE

                return result
            except Exception as e:
                _logger.warning(f"Strategy {strategy.__name__} failed: {e}")
                continue

        raise MMapDatasetError("All initialization strategies failed")

    async def get_conversation(
        self, session_id: str | None = None
    ) -> Conversation | None:
        """Get conversation using the active manager."""
        if not self._active_manager:
            raise MMapDatasetError("Dataset manager not initialized")

        if hasattr(self._active_manager, "get_conversation"):
            return await self._active_manager.get_conversation(session_id)
        else:
            # Fallback for managers that don't support direct conversation access
            if session_id and session_id in self.dataset:
                return self.dataset[session_id]
            elif not session_id:
                import random

                session_id = random.choice(list(self.dataset.keys()))
                return self.dataset[session_id]

        return None

    def get_deployment_mode(self) -> DeploymentMode | None:
        """Get the active deployment mode."""
        return self._deployment_mode

    def get_dataset_info(self) -> dict[str, Any]:
        """Get dataset information."""
        return {
            "dataset_id": self._dataset_id,
            "node_id": self._node_id,
            "deployment_mode": self._deployment_mode,
            "conversations_count": len(self.dataset),
            "compression_enabled": self.config.enable_compression,
            "sequential_iteration": self.use_sequential_iteration,
        }

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._active_manager:
            if hasattr(self._active_manager, "cleanup"):
                await self._active_manager.cleanup()
            elif hasattr(self._active_manager, "cleanup_memory_mapped_files_async"):
                await self._active_manager.cleanup_memory_mapped_files_async()
            elif hasattr(self._active_manager, "cleanup_distributed_dataset"):
                await self._active_manager.cleanup_distributed_dataset()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
