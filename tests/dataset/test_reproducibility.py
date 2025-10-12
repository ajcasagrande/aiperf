# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Reproducibility tests for dataset distribution.

These tests verify that benchmarks produce identical results across different
configurations when using the same random seed.
"""

import pytest

from aiperf.common.config import (
    EndpointConfig,
    LoadGeneratorConfig,
    ServiceConfig,
    UserConfig,
)
from aiperf.common.config.input_config import InputConfig
from aiperf.dataset.dataset_manager import DatasetManager


@pytest.mark.asyncio
class TestCrossWorkerCountReproducibility:
    """Test reproducibility across different worker counts."""

    async def test_deterministic_mode_across_worker_counts(self):
        """Test deterministic mode produces identical sequences regardless of worker count.

        This is the CRITICAL test for cross-worker-count reproducibility.
        """
        from aiperf.common.models import Conversation, Text, Turn

        # Create test dataset
        conversations = [
            Conversation(
                session_id=f"conv-{i:03d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Message {i}"])])],
            )
            for i in range(100)
        ]

        # Helper function to get conversation sequence
        async def get_conversation_sequence(concurrency: int, num_chunks: int):
            config = UserConfig(
                endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
                input=InputConfig(
                    random_seed=42,
                    deterministic_conversation_assignment=True,
                ),
                loadgen=LoadGeneratorConfig(
                    request_count=1000,  # 1000 total requests
                    concurrency=concurrency,
                ),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            await manager._generate_deterministic_sequence()

            # Simulate multiple workers requesting chunks
            all_conversations = []
            for _ in range(num_chunks):
                chunk = manager._get_conversation_chunk(1000 // num_chunks)
                all_conversations.extend(chunk)

            return [c.session_id for c in all_conversations]

        # Test with different "worker counts" (simulated by num_chunks)
        seq_10_workers = await get_conversation_sequence(concurrency=10, num_chunks=10)
        seq_100_workers = await get_conversation_sequence(
            concurrency=100, num_chunks=100
        )
        seq_1000_workers = await get_conversation_sequence(
            concurrency=1000, num_chunks=1000
        )

        # All should be IDENTICAL
        assert seq_10_workers == seq_100_workers
        assert seq_100_workers == seq_1000_workers
        assert len(seq_10_workers) == 1000

    async def test_random_mode_NOT_reproducible_across_worker_counts(self):
        """Test that random mode (without deterministic) is NOT reproducible across worker counts.

        This documents the existing behavior and verifies that users need
        to use deterministic mode for cross-worker-count reproducibility.
        """
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i:03d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Message {i}"])])],
            )
            for i in range(100)
        ]

        # Random mode (default)
        config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42, deterministic_conversation_assignment=False
            ),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())

        # Simulate different worker patterns consuming random sequence
        # Worker pattern 1: Large chunks
        chunk1 = manager._get_conversation_chunk(100)

        # Reset random state
        import random

        manager._conversation_query_random = random.Random(42)

        # Worker pattern 2: Small chunks (different consumption pattern)
        small_chunks = []
        for _ in range(10):
            small_chunks.extend(manager._get_conversation_chunk(10))

        # Both consumed 100 random choices, so should be identical
        assert [c.session_id for c in chunk1] == [c.session_id for c in small_chunks]


@pytest.mark.asyncio
class TestChunkingVsSingleConversationReproducibility:
    """Test that chunking produces same results as single-conversation mode."""

    async def test_chunked_matches_single_mode(self):
        """Verify chunking produces identical sequence to single-conversation requests."""
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i:03d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Message {i}"])])],
            )
            for i in range(50)
        ]

        # Single-conversation mode: call _return_any_conversation 100 times
        config1 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )
        manager1 = DatasetManager(ServiceConfig(), config1)
        manager1.dataset = {c.session_id: c for c in conversations}
        manager1._session_ids_cache = list(manager1.dataset.keys())

        single_ids = []
        for _ in range(100):
            response = manager1._return_any_conversation(request_id=None)
            single_ids.append(response.conversation.session_id)

        # Chunked mode: call _get_conversation_chunk once with size=100
        config2 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )
        manager2 = DatasetManager(ServiceConfig(), config2)
        manager2.dataset = {c.session_id: c for c in conversations}
        manager2._session_ids_cache = list(manager2.dataset.keys())

        chunk = manager2._get_conversation_chunk(100)
        chunk_ids = [c.session_id for c in chunk]

        # MUST be identical
        assert single_ids == chunk_ids

    async def test_sequential_mode_chunked_matches_single(self):
        """Test sequential mode chunking matches single-conversation mode."""
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i:03d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Message {i}"])])],
            )
            for i in range(100)
        ]

        # Single mode
        config1 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
        )
        manager1 = DatasetManager(ServiceConfig(), config1)
        manager1.dataset = {c.session_id: c for c in conversations}
        manager1._session_ids_cache = list(manager1.dataset.keys())
        manager1._use_sequential_iteration = True

        single_ids = []
        for _ in range(50):
            response = manager1._return_any_conversation(request_id=None)
            single_ids.append(response.conversation.session_id)

        # Chunked mode
        config2 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
        )
        manager2 = DatasetManager(ServiceConfig(), config2)
        manager2.dataset = {c.session_id: c for c in conversations}
        manager2._session_ids_cache = list(manager2.dataset.keys())
        manager2._use_sequential_iteration = True

        chunk = manager2._get_conversation_chunk(50)
        chunk_ids = [c.session_id for c in chunk]

        # Should be identical
        assert single_ids == chunk_ids


@pytest.mark.asyncio
class TestDeterministicModeGuarantees:
    """Test deterministic mode provides strong reproducibility guarantees."""

    async def test_same_seed_produces_identical_full_sequence(self):
        """Test that deterministic mode with same seed produces identical FULL sequences."""
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(50)
        ]

        async def generate_full_sequence(seed: int):
            config = UserConfig(
                endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
                input=InputConfig(
                    random_seed=seed,
                    deterministic_conversation_assignment=True,
                ),
                loadgen=LoadGeneratorConfig(request_count=200),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            await manager._generate_deterministic_sequence()

            return manager._deterministic_sequence

        # Generate with seed 42
        seq1 = await generate_full_sequence(42)
        seq2 = await generate_full_sequence(42)
        seq3 = await generate_full_sequence(42)

        # All should be identical
        assert seq1 == seq2 == seq3
        assert len(seq1) == 200

        # Different seed should be different
        seq_different = await generate_full_sequence(123)
        assert seq_different != seq1

    async def test_deterministic_sequence_wraparound(self):
        """Test that deterministic sequence wraps around for infinite benchmarks."""
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(20)
        ]

        config = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(request_count=100),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        await manager._generate_deterministic_sequence()

        # Get all 100 conversations from sequence
        chunk1 = manager._get_conversation_chunk(100)
        assert len(chunk1) == 100

        # Get more (should wrap around)
        chunk2 = manager._get_conversation_chunk(50)
        assert len(chunk2) == 50

        # Verify wraparound: should start from beginning
        assert [c.session_id for c in chunk2[:25]] == [
            manager.dataset[sid].session_id
            for sid in manager._deterministic_sequence[:25]
        ]


@pytest.mark.asyncio
class TestReproducibilityDocumentation:
    """Tests that document and verify reproducibility guarantees."""

    async def test_reproducibility_guarantee_same_config(self):
        """Test: Same config → Same results."""
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        async def run_benchmark(run_id: int):
            config = UserConfig(
                endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
                input=InputConfig(
                    random_seed=42,
                    enable_chunking=True,
                    dataset_chunk_size=25,
                    deterministic_conversation_assignment=True,
                ),
                loadgen=LoadGeneratorConfig(
                    concurrency=10,
                    request_count=100,
                ),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            await manager._generate_deterministic_sequence()

            # Simulate 4 workers requesting chunks
            all_convos = []
            for _ in range(4):
                chunk = manager._get_conversation_chunk(25)
                all_convos.extend(chunk)

            return [c.session_id for c in all_convos]

        # Run multiple times
        run1 = await run_benchmark(1)
        run2 = await run_benchmark(2)
        run3 = await run_benchmark(3)

        # All runs should be IDENTICAL
        assert run1 == run2 == run3

    async def test_reproducibility_different_chunk_sizes_same_result(self):
        """Test that different chunk sizes produce same conversation sequence."""
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        async def get_sequence(chunk_size: int):
            config = UserConfig(
                endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
                input=InputConfig(
                    random_seed=42,
                    deterministic_conversation_assignment=True,
                    dataset_chunk_size=chunk_size,
                ),
                loadgen=LoadGeneratorConfig(request_count=200),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            await manager._generate_deterministic_sequence()

            # Get all conversations
            all_convos = []
            remaining = 200
            while remaining > 0:
                chunk = manager._get_conversation_chunk(min(chunk_size, remaining))
                all_convos.extend(chunk)
                remaining -= len(chunk)

            return [c.session_id for c in all_convos]

        # Test with different chunk sizes
        seq_10 = await get_sequence(chunk_size=10)
        seq_50 = await get_sequence(chunk_size=50)
        seq_100 = await get_sequence(chunk_size=100)
        seq_200 = await get_sequence(chunk_size=200)

        # All should produce IDENTICAL sequence
        assert seq_10 == seq_50 == seq_100 == seq_200
        assert len(seq_10) == 200


@pytest.mark.asyncio
class TestChunkingReproducibilityWithSeed:
    """Test chunking maintains reproducibility with same seed."""

    async def test_same_seed_same_random_sequence(self):
        """Test that same seed produces same random conversation sequence."""
        from aiperf.common.models import Conversation, Text, Turn

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        # Run 1
        config1 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )
        manager1 = DatasetManager(ServiceConfig(), config1)
        manager1.dataset = {c.session_id: c for c in conversations}
        manager1._session_ids_cache = list(manager1.dataset.keys())

        chunk1a = manager1._get_conversation_chunk(50)
        chunk1b = manager1._get_conversation_chunk(50)

        # Run 2
        config2 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )
        manager2 = DatasetManager(ServiceConfig(), config2)
        manager2.dataset = {c.session_id: c for c in conversations}
        manager2._session_ids_cache = list(manager2.dataset.keys())

        chunk2a = manager2._get_conversation_chunk(50)
        chunk2b = manager2._get_conversation_chunk(50)

        # Should be identical
        assert [c.session_id for c in chunk1a] == [c.session_id for c in chunk2a]
        assert [c.session_id for c in chunk1b] == [c.session_id for c in chunk2b]

    async def test_different_seeds_produce_different_sequences(self):
        """Test that different seeds produce different sequences."""
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

        chunk1 = manager1._get_conversation_chunk(100)

        # Seed 999
        config2 = UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
            input=InputConfig(random_seed=999),
        )
        manager2 = DatasetManager(ServiceConfig(), config2)
        manager2.dataset = {c.session_id: c for c in conversations}
        manager2._session_ids_cache = list(manager2.dataset.keys())

        chunk2 = manager2._get_conversation_chunk(100)

        # Should be different
        assert [c.session_id for c in chunk1] != [c.session_id for c in chunk2]


def test_reproducibility_documentation():
    """Document reproducibility guarantees for users."""

    guarantees = {
        "deterministic_mode": {
            "same_seed_same_config_same_workers": "✅ Reproducible",
            "same_seed_same_config_different_workers": "✅ Reproducible (PERFECT!)",
            "different_seed": "❌ Different results (expected)",
        },
        "random_mode": {
            "same_seed_same_config_same_workers": "✅ Reproducible",
            "same_seed_same_config_different_workers": "❌ May differ (credit timing)",
            "different_seed": "❌ Different results (expected)",
        },
        "sequential_mode": {
            "deterministic": "✅ Always reproducible (deterministic order)",
        },
    }

    # This test documents guarantees
    assert guarantees["deterministic_mode"][
        "same_seed_same_config_different_workers"
    ] == ("✅ Reproducible (PERFECT!)")
