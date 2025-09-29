# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import tempfile
from pathlib import Path

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.decorators import implements_protocol
from aiperf.common.models import Conversation
from aiperf.common.protocols import ServiceProtocol
from aiperf.dataset.mmap_dataset_manager import MMapDatasetError, MMapDatasetManager

_logger = AIPerfLogger(__name__)


class DistributedStorageType:
    """Supported distributed storage backends."""

    NFS = "nfs"
    CEPH = "ceph"
    S3FS = "s3fs"
    LOCAL_REPLICA = "local_replica"


@implements_protocol(ServiceProtocol)
class DistributedDatasetManager:
    """
    Manages dataset distribution across multiple nodes using shared storage.

    This manager creates memory-mapped files on shared storage (NFS, CephFS, etc.)
    that can be accessed by workers on different nodes. Falls back to local
    replication if shared storage is not available.
    """

    def __init__(
        self,
        dataset: dict[str, Conversation],
        storage_type: str = DistributedStorageType.NFS,
        shared_storage_path: str | None = None,
        random_seed: int | None = None,
        use_sequential_iteration: bool = False,
        enable_compression: bool = True,  # Enable by default for network efficiency
        replica_nodes: list[str] | None = None,
    ) -> None:
        """Initialize the distributed dataset manager.

        Args:
            dataset: Dictionary mapping session IDs to Conversation objects
            storage_type: Type of distributed storage backend
            shared_storage_path: Path to shared storage mount point
            random_seed: Optional random seed for reproducible random access
            use_sequential_iteration: Whether to use sequential iteration
            enable_compression: Whether to enable compression (recommended for network storage)
            replica_nodes: List of nodes for local replication strategy
        """
        if not dataset:
            raise MMapDatasetError("Dataset cannot be empty")

        self.dataset = dataset
        self.storage_type = storage_type
        self.shared_storage_path = (
            Path(shared_storage_path) if shared_storage_path else None
        )
        self.replica_nodes = replica_nodes or []

        # Use the existing MMapDatasetManager for the core functionality
        self._mmap_manager = MMapDatasetManager(
            dataset=dataset,
            random_seed=random_seed,
            use_sequential_iteration=use_sequential_iteration,
            enable_compression=enable_compression,
        )

        self._distributed_paths: tuple[str, str] | None = None
        self._node_id = self._get_node_id()

    def _get_node_id(self) -> str:
        """Get unique identifier for this node."""
        import socket

        return f"{socket.gethostname()}_{os.getpid()}"

    async def create_distributed_dataset(self) -> tuple[str, str]:
        """Create dataset files accessible across multiple nodes.

        Returns:
            Tuple of (data_file_path, index_file_path) accessible by all nodes
        """
        if self.storage_type == DistributedStorageType.LOCAL_REPLICA:
            return await self._create_replicated_dataset()
        else:
            return await self._create_shared_storage_dataset()

    async def _create_shared_storage_dataset(self) -> tuple[str, str]:
        """Create dataset on shared storage (NFS, CephFS, etc.)."""
        if not self.shared_storage_path:
            raise MMapDatasetError(
                "Shared storage path required for shared storage strategy"
            )

        if not self.shared_storage_path.exists():
            raise MMapDatasetError(
                f"Shared storage path does not exist: {self.shared_storage_path}"
            )

        try:
            # Create dataset directory on shared storage
            dataset_dir = (
                self.shared_storage_path
                / "aiperf_datasets"
                / f"dataset_{self._node_id}"
            )
            dataset_dir.mkdir(parents=True, exist_ok=True)

            # Create temporary files first, then move to shared storage
            with tempfile.TemporaryDirectory():
                # Create files using existing mmap manager
                (
                    temp_data_path,
                    temp_index_path,
                ) = await self._mmap_manager.create_memory_mapped_files_async()

                # Copy to shared storage with atomic operations
                shared_data_path = dataset_dir / f"data_{self._node_id}.dat"
                shared_index_path = dataset_dir / f"index_{self._node_id}.dat"

                # Use atomic move operations
                await self._atomic_move(temp_data_path, shared_data_path)
                await self._atomic_move(temp_index_path, shared_index_path)

            self._distributed_paths = (str(shared_data_path), str(shared_index_path))

            _logger.info(
                "Created shared storage dataset",
                extra={
                    "storage_type": self.storage_type,
                    "shared_path": str(self.shared_storage_path),
                    "data_path": str(shared_data_path),
                    "index_path": str(shared_index_path),
                    "conversations_count": len(self.dataset),
                    "compression_enabled": self._mmap_manager.enable_compression,
                },
            )

            return self._distributed_paths

        except Exception as e:
            _logger.error(f"Failed to create shared storage dataset: {e}")
            raise MMapDatasetError(
                f"Failed to create shared storage dataset: {e}"
            ) from e

    async def _create_replicated_dataset(self) -> tuple[str, str]:
        """Create dataset with replication to multiple nodes."""
        # Create local copy first
        (
            local_data_path,
            local_index_path,
        ) = await self._mmap_manager.create_memory_mapped_files_async()

        # TODO: Implement actual replication logic
        # This would involve:
        # 1. Identifying target nodes
        # 2. Transferring files via secure copy or rsync
        # 3. Verifying integrity on remote nodes
        # 4. Updating node registry

        _logger.info(
            "Created replicated dataset (local copy)",
            extra={
                "local_data_path": local_data_path,
                "local_index_path": local_index_path,
                "target_nodes": self.replica_nodes,
            },
        )

        self._distributed_paths = (local_data_path, local_index_path)
        return self._distributed_paths

    async def _atomic_move(self, src: str, dst: Path) -> None:
        """Atomically move file to destination."""
        import shutil

        loop = asyncio.get_running_loop()

        # Move to temporary name first, then rename (atomic on most filesystems)
        temp_dst = dst.with_suffix(dst.suffix + ".tmp")
        await loop.run_in_executor(None, shutil.move, src, str(temp_dst))
        await loop.run_in_executor(None, temp_dst.rename, dst)

    def get_distributed_paths(self) -> tuple[str, str] | None:
        """Get the paths to distributed dataset files."""
        return self._distributed_paths

    async def cleanup_distributed_dataset(self) -> None:
        """Clean up distributed dataset files."""
        if self._distributed_paths:
            data_path, index_path = self._distributed_paths

            for file_path in [Path(data_path), Path(index_path)]:
                if file_path.exists():
                    try:
                        file_path.unlink()
                        _logger.debug(f"Cleaned up distributed file: {file_path}")
                    except OSError as e:
                        _logger.warning(
                            f"Failed to cleanup distributed file {file_path}: {e}"
                        )

        # Cleanup local mmap files
        await self._mmap_manager.cleanup_memory_mapped_files_async()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.cleanup_distributed_dataset()
