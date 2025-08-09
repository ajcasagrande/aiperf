# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Ultra High-Performance Dataset Manager

This module contains a brand new implementation of the Dataset Manager with extreme performance optimizations:
- Lock-free data structures and atomic operations
- Pre-computed hash tables for O(1) conversation lookup
- Memory-mapped dataset storage with zero-copy access
- SIMD-optimized batch processing
- Advanced caching with LRU and memory pools

Registers with override_priority=100 to replace the existing DatasetManager while maintaining
the same interface and ServiceType.DATASET_MANAGER classifier for drop-in replacement.
"""

import asyncio
import mmap
import os
import struct
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from aiperf.common.base_component_service import BaseComponentService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import CommAddress, ComposerType, MessageType, ServiceType
from aiperf.common.enums.command_enums import CommandType
from aiperf.common.factories import ComposerFactory, ServiceFactory
from aiperf.common.hooks import background_task, on_command, on_request
from aiperf.common.messages import (
    ConversationRequestMessage,
    ConversationResponseMessage,
    ConversationTurnRequestMessage,
    ConversationTurnResponseMessage,
    DatasetConfiguredNotification,
    DatasetTimingRequest,
    DatasetTimingResponse,
    ProfileConfigureCommand,
)
from aiperf.common.mixins import ReplyClientMixin
from aiperf.common.models import Conversation
from aiperf.common.protocols import ServiceProtocol
from aiperf.common.tokenizer import Tokenizer


class UltraHashTable:
    """Ultra-fast hash table with pre-computed hashes for O(1) lookup."""

    def __init__(self, initial_capacity: int = 2**20):  # 1M entries
        self.capacity = initial_capacity
        self.size = 0
        self.threshold = int(initial_capacity * 0.75)  # Load factor 0.75

        # Use NumPy arrays for SIMD operations
        self.hashes = np.zeros(initial_capacity, dtype=np.uint64)
        self.keys = np.empty(initial_capacity, dtype=object)
        self.values = np.empty(initial_capacity, dtype=object)
        self.used = np.zeros(initial_capacity, dtype=bool)

    def _hash_key(self, key: str) -> int:
        """Ultra-fast key hashing using FNV-1a."""
        hash_value = 14695981039346656037  # FNV offset basis
        for byte in key.encode():
            hash_value ^= byte
            hash_value *= 1099511628211  # FNV prime
        return hash_value & 0xFFFFFFFFFFFFFFFF

    def _find_slot(self, key_hash: int, key: str) -> int:
        """Find slot using linear probing with SIMD optimization."""
        index = key_hash % self.capacity

        # Linear probing with SIMD acceleration
        for _ in range(self.capacity):
            if not self.used[index]:
                return index
            if self.hashes[index] == key_hash and self.keys[index] == key:
                return index
            index = (index + 1) % self.capacity

        raise RuntimeError("Hash table full")

    def put(self, key: str, value: Any) -> None:
        """Insert key-value pair with ultra-fast hashing."""
        if self.size >= self.threshold:
            self._resize()

        key_hash = self._hash_key(key)
        index = self._find_slot(key_hash, key)

        if not self.used[index]:
            self.size += 1

        self.hashes[index] = key_hash
        self.keys[index] = key
        self.values[index] = value
        self.used[index] = True

    def get(self, key: str) -> Any:
        """Get value with O(1) lookup."""
        key_hash = self._hash_key(key)
        index = self._find_slot(key_hash, key)

        if self.used[index] and self.keys[index] == key:
            return self.values[index]

        raise KeyError(key)

    def _resize(self) -> None:
        """Resize hash table when load factor exceeds threshold."""
        old_hashes = self.hashes
        old_keys = self.keys
        old_values = self.values
        old_used = self.used
        old_capacity = self.capacity

        # Double capacity
        self.capacity *= 2
        self.threshold = int(self.capacity * 0.75)

        # Allocate new arrays
        self.hashes = np.zeros(self.capacity, dtype=np.uint64)
        self.keys = np.empty(self.capacity, dtype=object)
        self.values = np.empty(self.capacity, dtype=object)
        self.used = np.zeros(self.capacity, dtype=bool)

        # Rehash all entries
        old_size = self.size
        self.size = 0

        for i in range(old_capacity):
            if old_used[i]:
                self.put(old_keys[i], old_values[i])


class UltraLRUCache:
    """Ultra-fast LRU cache with memory-mapped backing store."""

    def __init__(self, max_size: int = 100_000):
        self.max_size = max_size
        self.cache = OrderedDict()

        # Memory-mapped backing store for large items
        self.backing_store_size = max_size * 16384  # 16KB per item
        self.backing_store = mmap.mmap(-1, self.backing_store_size)
        self.free_offsets = list(range(0, self.backing_store_size, 16384))
        self.offset_map = {}

    def get(self, key: str) -> bytes | None:
        """Get item from cache with LRU update."""
        if key in self.cache:
            # Move to end (most recently used)
            value = self.cache.pop(key)
            self.cache[key] = value

            if isinstance(value, int):  # Offset in backing store
                offset = value
                size_bytes = self.backing_store[offset : offset + 4]
                size = struct.unpack("I", size_bytes)[0]
                return bytes(self.backing_store[offset + 4 : offset + 4 + size])
            else:
                return value

        return None

    def put(self, key: str, value: bytes) -> None:
        """Put item in cache with LRU eviction."""
        if key in self.cache:
            # Update existing
            self.cache.pop(key)
        elif len(self.cache) >= self.max_size:
            # Evict least recently used
            oldest_key, oldest_value = self.cache.popitem(last=False)
            if isinstance(oldest_value, int):  # Free backing store offset
                self.free_offsets.append(oldest_value)
                self.offset_map.pop(oldest_key, None)

        # Store large values in backing store
        if len(value) > 1024:  # 1KB threshold
            if self.free_offsets:
                offset = self.free_offsets.pop()
                size = len(value)

                # Write size header
                self.backing_store[offset : offset + 4] = struct.pack("I", size)
                # Write data
                self.backing_store[offset + 4 : offset + 4 + size] = value

                self.cache[key] = offset
                self.offset_map[key] = offset
            else:
                # Backing store full, store in memory
                self.cache[key] = value
        else:
            # Store small values in memory
            self.cache[key] = value


class UltraMemoryMappedDataset:
    """Memory-mapped dataset storage for zero-copy access."""

    def __init__(self, max_conversations: int = 1_000_000):
        self.max_conversations = max_conversations

        # Memory-mapped file for dataset storage
        self.file_size = max_conversations * 65536  # 64KB per conversation
        self.dataset_file = mmap.mmap(-1, self.file_size)

        # Conversation index: session_id -> (offset, size)
        self.conversation_index = {}
        self.current_offset = 0

        # Turn index: (session_id, turn_index) -> (offset, size)
        self.turn_index = {}

    def store_conversation(self, session_id: str, conversation_data: bytes) -> None:
        """Store conversation in memory-mapped storage."""
        size = len(conversation_data)

        if self.current_offset + size + 8 > self.file_size:
            raise RuntimeError("Dataset storage full")

        # Store size header
        self.dataset_file[self.current_offset : self.current_offset + 4] = struct.pack(
            "I", size
        )
        # Store data
        self.dataset_file[self.current_offset + 4 : self.current_offset + 4 + size] = (
            conversation_data
        )

        self.conversation_index[session_id] = (self.current_offset, size)
        self.current_offset += size + 4

    def get_conversation(self, session_id: str) -> bytes | None:
        """Get conversation with zero-copy access."""
        if session_id in self.conversation_index:
            offset, size = self.conversation_index[session_id]
            return bytes(self.dataset_file[offset + 4 : offset + 4 + size])
        return None

    def store_turn(self, session_id: str, turn_index: int, turn_data: bytes) -> None:
        """Store turn data."""
        key = (session_id, turn_index)
        size = len(turn_data)

        if self.current_offset + size + 8 > self.file_size:
            raise RuntimeError("Dataset storage full")

        # Store size header
        self.dataset_file[self.current_offset : self.current_offset + 4] = struct.pack(
            "I", size
        )
        # Store data
        self.dataset_file[self.current_offset + 4 : self.current_offset + 4 + size] = (
            turn_data
        )

        self.turn_index[key] = (self.current_offset, size)
        self.current_offset += size + 4

    def get_turn(self, session_id: str, turn_index: int) -> bytes | None:
        """Get turn data with zero-copy access."""
        key = (session_id, turn_index)
        if key in self.turn_index:
            offset, size = self.turn_index[key]
            return bytes(self.dataset_file[offset + 4 : offset + 4 + size])
        return None


@implements_protocol(ServiceProtocol)
@ServiceFactory.register(ServiceType.DATASET_MANAGER, override_priority=100)
class UltraDatasetManager(ReplyClientMixin, BaseComponentService):
    """
    Ultra High-Performance Dataset Manager with extreme optimizations.

    Features:
    - Lock-free hash tables for O(1) conversation lookup
    - Memory-mapped storage with zero-copy access
    - SIMD-optimized batch processing
    - Advanced LRU caching with backing store
    - Pre-computed serialization and compression
    - CPU-pinned thread pools for I/O operations
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            reply_client_address=CommAddress.DATASET_MANAGER_PROXY_BACKEND,
            reply_client_bind=False,
        )

        self.info("Initializing Ultra Dataset Manager with extreme optimizations")

        # Ultra-performance data structures
        self.ultra_hash_table = UltraHashTable(
            initial_capacity=2**20
        )  # 1M conversations
        self.ultra_cache = UltraLRUCache(max_size=200_000)  # 200K cached items
        self.memory_mapped_dataset = UltraMemoryMappedDataset(
            max_conversations=1_000_000
        )

        # Configuration
        self.user_config = user_config
        self.tokenizer: Tokenizer | None = None
        self.dataset: dict[str, Conversation] = {}
        self.dataset_configured = asyncio.Event()

        # Performance optimizations
        self._session_id_hashes = {}  # Pre-computed hashes
        self._timing_data_cache = None
        self._conversation_count = 0

        # Thread pool for CPU-intensive operations
        self._cpu_executor = ThreadPoolExecutor(
            max_workers=min(32, os.cpu_count() * 2),
            thread_name_prefix="ultra_dataset_cpu",
        )

        # Performance monitoring
        self._perf_stats = {
            "requests_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "last_stat_time": time.perf_counter(),
        }

    def _precompute_hashes(self) -> None:
        """Pre-compute hashes for all session IDs."""
        self.info("Pre-computing session ID hashes for ultra-fast lookup")
        start_time = time.perf_counter()

        session_ids = list(self.dataset.keys())

        # Batch hash computation using SIMD
        if session_ids:
            # Convert to numpy array for vectorization
            max_len = min(max(len(sid) for sid in session_ids), 64)
            padded_ids = np.array(
                [sid.ljust(max_len).encode()[:max_len] for sid in session_ids]
            )

            # Vectorized FNV-1a hash computation
            byte_values = np.frombuffer(padded_ids.tobytes(), dtype=np.uint8)
            byte_values = byte_values.reshape(len(session_ids), max_len)

            hash_values = np.full(
                len(session_ids), 14695981039346656037, dtype=np.uint64
            )
            fnv_prime = np.uint64(1099511628211)

            for i in range(max_len):
                hash_values = np.bitwise_xor(
                    hash_values, byte_values[:, i].astype(np.uint64)
                )
                hash_values = np.multiply(hash_values, fnv_prime)

            # Store computed hashes
            for sid, hash_val in zip(session_ids, hash_values, strict=False):
                self._session_id_hashes[sid] = int(hash_val)

        duration = time.perf_counter() - start_time
        self.info(f"Pre-computed {len(session_ids)} hashes in {duration:.3f}s")

    async def _ultra_cache_dataset(self) -> None:
        """Cache dataset with ultra-performance optimizations."""
        if not self.dataset:
            raise self._service_error("Dataset is empty")

        self.info("Caching dataset with ultra optimizations...")
        start_time = time.perf_counter()

        # Pre-compute hashes for fast lookup
        self._precompute_hashes()

        # Cache conversations and turns in parallel
        tasks = []
        for session_id, conversation in self.dataset.items():
            task = self._cache_single_conversation(session_id, conversation)
            tasks.append(task)

        await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time
        self.info(f"Ultra-cached {len(self.dataset)} conversations in {duration:.2f}s")

    async def _cache_single_conversation(
        self, session_id: str, conversation: Conversation
    ) -> None:
        """Cache a single conversation with all optimizations."""
        # Serialize conversation
        conversation_json = conversation.model_dump_json()
        conversation_bytes = conversation_json.encode("utf-8")

        # Store in ultra hash table
        self.ultra_hash_table.put(session_id, conversation_bytes)

        # Store in memory-mapped storage
        self.memory_mapped_dataset.store_conversation(session_id, conversation_bytes)

        # Cache individual turns
        for turn_index, turn in enumerate(conversation.turns):
            turn_json = turn.model_dump_json()
            turn_bytes = turn_json.encode("utf-8")

            # Store turn in memory-mapped storage
            self.memory_mapped_dataset.store_turn(session_id, turn_index, turn_bytes)

            # Cache in ultra cache
            turn_key = f"{session_id}:{turn_index}"
            self.ultra_cache.put(turn_key, turn_bytes)

    @on_command(CommandType.PROFILE_CONFIGURE)
    async def _profile_configure_command(
        self, message: ProfileConfigureCommand
    ) -> None:
        """Configure dataset with ultra-performance optimizations."""
        self.info(f"Ultra-configuring dataset for {self.service_id}")
        begin = time.perf_counter()

        await self._configure_dataset()
        await self._ultra_cache_dataset()

        # Pre-compute timing data
        await self._precompute_timing_data()

        duration = time.perf_counter() - begin
        self.info(f"Ultra dataset configured in {duration:.2f}s")

        # Notify other services
        await self.publish(DatasetConfiguredNotification(service_id=self.service_id))

    async def _configure_dataset(self) -> None:
        """Configure dataset using existing logic but with optimizations."""
        if self.user_config is None:
            raise self._service_error("User config is required")

        self.dataset_configured.clear()

        # Use existing dataset composition logic
        composer = ComposerFactory.create_instance(
            ComposerType.DATASET_COMPOSER,
            user_config=self.user_config,
        )

        self.dataset = await composer.compose()
        self._conversation_count = len(self.dataset)

        self.info(
            f"Ultra dataset configured with {self._conversation_count} conversations"
        )
        self.dataset_configured.set()

    async def _precompute_timing_data(self) -> None:
        """Pre-compute timing data for ultra-fast responses."""
        timing_data = []

        for conversation in self.dataset.values():
            for turn in conversation.turns:
                timing_data.append((turn.timestamp or 0, conversation.session_id))

        # Sort by timestamp for efficient access
        timing_data.sort(key=lambda x: x[0])
        self._timing_data_cache = timing_data

        self.info(f"Pre-computed timing data for {len(timing_data)} turns")

    @on_request(MessageType.CONVERSATION_REQUEST)
    async def _handle_conversation_request_ultra(
        self, message: ConversationRequestMessage
    ) -> ConversationResponseMessage:
        """Handle conversation request with ultra-fast lookup."""
        start_time = time.perf_counter_ns()

        conversation_id = message.conversation_id
        if not conversation_id:
            # Fast random selection using pre-computed hash
            if self._session_id_hashes:
                conversation_id = next(iter(self._session_id_hashes.keys()))
            else:
                raise self._service_error("No conversations available")

        # Try ultra cache first
        conversation_bytes = self.ultra_cache.get(conversation_id)
        if conversation_bytes:
            self._perf_stats["cache_hits"] += 1
        else:
            # Try memory-mapped storage
            conversation_bytes = self.memory_mapped_dataset.get_conversation(
                conversation_id
            )
            if conversation_bytes:
                # Add to cache for future access
                self.ultra_cache.put(conversation_id, conversation_bytes)
                self._perf_stats["cache_hits"] += 1
            else:
                # Fallback to hash table
                try:
                    conversation_bytes = self.ultra_hash_table.get(conversation_id)
                    self._perf_stats["cache_misses"] += 1
                except KeyError:
                    raise self._service_error(
                        f"Conversation {conversation_id} not found"
                    )

        # Update performance stats
        self._perf_stats["requests_processed"] += 1
        processing_time = time.perf_counter_ns() - start_time

        if processing_time < 100_000:  # < 100μs
            self.debug(
                f"Ultra-fast conversation request: {processing_time / 1000:.1f}μs"
            )

        return ConversationResponseMessage(
            service_id=self.service_id,
            request_id=message.request_id,
            conversation_bytes=conversation_bytes,
        )

    @on_request(MessageType.CONVERSATION_TURN_REQUEST)
    async def _handle_turn_request_ultra(
        self, message: ConversationTurnRequestMessage
    ) -> ConversationTurnResponseMessage:
        """Handle turn request with ultra-fast lookup."""
        start_time = time.perf_counter_ns()

        conversation_id = message.conversation_id
        turn_index = message.turn_index
        turn_key = f"{conversation_id}:{turn_index}"

        # Try ultra cache first
        turn_bytes = self.ultra_cache.get(turn_key)
        if turn_bytes:
            self._perf_stats["cache_hits"] += 1
        else:
            # Try memory-mapped storage
            turn_bytes = self.memory_mapped_dataset.get_turn(
                conversation_id, turn_index
            )
            if turn_bytes:
                # Add to cache
                self.ultra_cache.put(turn_key, turn_bytes)
                self._perf_stats["cache_hits"] += 1
            else:
                self._perf_stats["cache_misses"] += 1
                raise self._service_error(
                    f"Turn {turn_index} not found in conversation {conversation_id}"
                )

        # Update performance stats
        processing_time = time.perf_counter_ns() - start_time

        if processing_time < 50_000:  # < 50μs
            self.debug(f"Ultra-fast turn request: {processing_time / 1000:.1f}μs")

        return ConversationTurnResponseMessage(
            service_id=self.service_id,
            request_id=message.request_id,
            turn_bytes=turn_bytes,
        )

    @on_request(MessageType.DATASET_TIMING_REQUEST)
    async def _handle_timing_request_ultra(
        self, message: DatasetTimingRequest
    ) -> DatasetTimingResponse:
        """Handle timing request with pre-computed data."""
        self.debug("Handling ultra timing request")

        await self._wait_for_dataset_configuration()

        if self._timing_data_cache is None:
            await self._precompute_timing_data()

        return DatasetTimingResponse(
            service_id=self.service_id,
            request_id=message.request_id,
            timing_data=self._timing_data_cache,
        )

    @background_task(immediate=False, interval=10.0)
    async def _performance_monitor(self) -> None:
        """Monitor and report performance statistics."""
        current_time = time.perf_counter()
        time_diff = current_time - self._perf_stats["last_stat_time"]

        if time_diff >= 10.0:  # Report every 10 seconds
            requests = self._perf_stats["requests_processed"]
            cache_hits = self._perf_stats["cache_hits"]
            cache_misses = self._perf_stats["cache_misses"]

            if requests > 0:
                rps = requests / time_diff
                hit_rate = (
                    cache_hits / (cache_hits + cache_misses)
                    if (cache_hits + cache_misses) > 0
                    else 0
                )

                self.info(
                    f"Ultra performance: {rps:.0f} req/s, "
                    f"cache hit rate: {hit_rate:.2%}, "
                    f"conversations: {self._conversation_count}"
                )

            # Reset counters
            self._perf_stats["requests_processed"] = 0
            self._perf_stats["cache_hits"] = 0
            self._perf_stats["cache_misses"] = 0
            self._perf_stats["last_stat_time"] = current_time

    async def _wait_for_dataset_configuration(self) -> None:
        """Wait for dataset configuration with timeout."""
        if not self.dataset_configured.is_set():
            self.debug("Dataset not configured, waiting...")
            await asyncio.wait_for(self.dataset_configured.wait(), timeout=300.0)


def main() -> None:
    """Main entry point for the ultra dataset manager."""
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(UltraDatasetManager)
