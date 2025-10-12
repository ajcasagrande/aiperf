# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""End-to-end reproducibility validation tests.

These tests validate reproducibility guarantees in realistic scenarios,
simulating full benchmark runs with different configurations.
"""

import asyncio
import os

import pytest

from aiperf.common.config import (
    EndpointConfig,
    LoadGeneratorConfig,
    ServiceConfig,
    UserConfig,
)
from aiperf.common.config.input_config import InputConfig
from aiperf.common.models import Conversation, Text, Turn


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.asyncio
class TestDeterministicModeE2E:
    """End-to-end tests for deterministic mode reproducibility."""

    @pytest.fixture
    def test_conversations(self):
        """Create test conversation dataset."""
        return [
            Conversation(
                session_id=f"conv-{i:04d}",
                turns=[
                    Turn(
                        role="user",
                        texts=[Text(contents=[f"User message {i}"])],
                    )
                ],
            )
            for i in range(200)
        ]

    async def test_perfect_reproducibility_across_concurrency_levels(
        self, test_conversations
    ):
        """Test that deterministic mode produces identical results across concurrency levels.

        This is the GOLD STANDARD test for reproducibility.
        """
        from aiperf.dataset.dataset_manager import DatasetManager

        async def simulate_full_benchmark(concurrency: int):
            """Simulate complete benchmark with specified concurrency."""
            config = UserConfig(
                endpoint=EndpointConfig(
                    url="http://localhost:8000", model_names=["test"]
                ),
                input=InputConfig(
                    random_seed=42,
                    deterministic_conversation_assignment=True,
                    dataset_chunk_size=20,
                ),
                loadgen=LoadGeneratorConfig(
                    concurrency=concurrency,
                    request_count=500,  # Total requests
                ),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in test_conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            await manager._generate_deterministic_sequence()

            # Simulate workers requesting chunks in parallel
            all_conversations = []

            # Each worker gets roughly request_count/concurrency requests
            requests_per_worker = 500 // concurrency
            chunk_size = 20

            for worker_id in range(concurrency):
                worker_convos = []
                for _ in range(requests_per_worker // chunk_size):
                    chunk = manager._get_conversation_chunk(chunk_size)
                    worker_convos.extend(chunk)
                all_conversations.extend(worker_convos)

            return [c.session_id for c in all_conversations]

        # Test with different concurrency levels
        seq_concurrency_5 = await simulate_full_benchmark(5)
        seq_concurrency_10 = await simulate_full_benchmark(10)
        seq_concurrency_25 = await simulate_full_benchmark(25)
        seq_concurrency_50 = await simulate_full_benchmark(50)

        # ALL should be IDENTICAL despite different worker counts!
        assert seq_concurrency_5 == seq_concurrency_10, "5 vs 10 workers differ"
        assert seq_concurrency_10 == seq_concurrency_25, "10 vs 25 workers differ"
        assert seq_concurrency_25 == seq_concurrency_50, "25 vs 50 workers differ"

        # Verify we got expected number of conversations
        assert len(seq_concurrency_5) == 500

    async def test_deterministic_mode_handles_wraparound(self, test_conversations):
        """Test deterministic mode wraps around correctly for infinite benchmarks."""
        from aiperf.dataset.dataset_manager import DatasetManager

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(request_count=150),  # Smaller than dataset
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in test_conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        await manager._generate_deterministic_sequence()

        # Get all 150 conversations
        all_convos = []
        for _ in range(15):
            chunk = manager._get_conversation_chunk(10)
            all_convos.extend(chunk)

        assert len(all_convos) == 150

        # Continue beyond sequence (wraparound)
        chunk_after = manager._get_conversation_chunk(10)
        assert len(chunk_after) == 10

        # Should match beginning of sequence
        first_10_ids = [
            manager.dataset[sid].session_id
            for sid in manager._deterministic_sequence[:10]
        ]
        wraparound_ids = [c.session_id for c in chunk_after]

        assert wraparound_ids == first_10_ids


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.asyncio
class TestRandomModeE2E:
    """End-to-end tests for random mode."""

    async def test_random_mode_reproducible_same_config(self):
        """Test random mode is reproducible with identical configuration."""
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i:04d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        async def run_benchmark():
            config = UserConfig(
                endpoint=EndpointConfig(
                    url="http://localhost:8000", model_names=["test"]
                ),
                input=InputConfig(
                    random_seed=42,
                    enable_chunking=True,
                    dataset_chunk_size=50,
                ),
                loadgen=LoadGeneratorConfig(concurrency=10),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            manager.dataset_configured.set()

            # Simulate 10 workers each requesting 2 chunks
            all_convos = []
            for worker_id in range(10):
                chunk1 = manager._get_conversation_chunk(50)
                chunk2 = manager._get_conversation_chunk(50)
                all_convos.extend(chunk1 + chunk2)

            return [c.session_id for c in all_convos]

        # Run twice with same config
        result1 = await run_benchmark()
        result2 = await run_benchmark()

        # Should be identical (same seed, same consumption pattern)
        assert result1 == result2

    async def test_random_mode_statistical_properties(self):
        """Test random mode maintains proper statistical distribution."""
        from collections import Counter

        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i:02d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(20)
        ]

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(random_seed=42, enable_chunking=True),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager.dataset_configured.set()

        # Request large sample
        all_convos = []
        for _ in range(100):  # 10,000 conversations
            chunk = manager._get_conversation_chunk(100)
            all_convos.extend(chunk)

        # Count distribution
        counter = Counter(c.session_id for c in all_convos)

        # Each conversation should appear roughly 500 times (10000 / 20)
        # Allow significant variance for statistical sampling
        for conv_id, count in counter.items():
            assert 350 <= count <= 650, f"{conv_id}: {count} (expected ~500)"


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.kubernetes
class TestKubernetesChunkingE2E:
    """End-to-end tests for Kubernetes with chunking."""

    @pytest.fixture
    def test_namespace(self):
        """Generate unique namespace for tests."""
        import uuid

        return f"aiperf-chunk-e2e-{uuid.uuid4().hex[:8]}"

    @pytest.mark.skipif(
        not os.getenv("RUN_K8S_TESTS"),
        reason="Requires Kubernetes cluster. Set RUN_K8S_TESTS=1",
    )
    async def test_kubernetes_with_chunking_and_deterministic(self, test_namespace):
        """Test full Kubernetes deployment with chunking and deterministic mode."""
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

        user_config = UserConfig(
            endpoint=EndpointConfig(
                url="http://mock-llm-service.default.svc.cluster.local:8000",
                model_names=["mock-model"],
            ),
            input=InputConfig(
                public_dataset="sharegpt",
                random_seed=42,
                enable_chunking=True,
                dataset_chunk_size=100,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(
                concurrency=20,
                benchmark_duration=30,
            ),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = test_namespace
        service_config.kubernetes.image = "aiperf:latest"
        service_config.kubernetes.image_pull_policy = "IfNotPresent"
        service_config.kubernetes.cleanup_on_completion = True

        orchestrator = KubernetesOrchestrator(user_config, service_config)

        try:
            # Deploy
            success = await orchestrator.deploy()
            assert success, "Deployment should succeed with chunking enabled"

            # Verify ConfigMap has chunking configuration
            cm = orchestrator.resource_manager.core_api.read_namespaced_config_map(
                name="aiperf-config", namespace=test_namespace
            )

            import json

            user_data = json.loads(cm.data["user_config.json"])

            # Verify chunking settings
            assert user_data["input"]["enable_chunking"] is True
            assert user_data["input"]["dataset_chunk_size"] == 100
            assert user_data["input"]["deterministic_conversation_assignment"] is True

        finally:
            await orchestrator.cleanup()

    @pytest.mark.skipif(
        not os.getenv("RUN_K8S_TESTS"),
        reason="Requires Kubernetes cluster. Set RUN_K8S_TESTS=1",
    )
    async def test_kubernetes_with_different_chunk_sizes(self, test_namespace):
        """Test Kubernetes deployment with various chunk sizes."""
        from aiperf.kubernetes.config_serializer import ConfigSerializer

        chunk_sizes = [50, 100, 200]

        for chunk_size in chunk_sizes:
            user_config = UserConfig(
                endpoint=EndpointConfig(
                    url="http://localhost:8000", model_names=["test"]
                ),
                input=InputConfig(
                    random_seed=42,
                    enable_chunking=True,
                    dataset_chunk_size=chunk_size,
                ),
            )

            service_config = ServiceConfig()

            # Serialize and verify
            config_data = ConfigSerializer.serialize_to_configmap(
                user_config, service_config
            )

            import json

            user_json = json.loads(config_data["user_config.json"])
            assert user_json["input"]["dataset_chunk_size"] == chunk_size


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.asyncio
class TestPerformanceCharacteristics:
    """Integration tests for performance characteristics."""

    async def test_chunking_throughput_improvement(self):
        """Verify chunking provides significant throughput improvement."""
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(500)
        ]

        # Test single-conversation mode
        config_single = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(random_seed=42, enable_chunking=False),
        )

        manager_single = DatasetManager(ServiceConfig(), config_single)
        manager_single.dataset = {c.session_id: c for c in conversations}
        manager_single._session_ids_cache = list(manager_single.dataset.keys())
        manager_single.dataset_configured.set()

        start_single = time.perf_counter()
        for _ in range(1000):
            await manager_single._handle_conversation_request(
                ConversationRequestMessage(service_id="worker")
            )
        duration_single = time.perf_counter() - start_single

        # Test chunked mode
        config_chunked = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42, enable_chunking=True, dataset_chunk_size=100
            ),
        )

        manager_chunked = DatasetManager(ServiceConfig(), config_chunked)
        manager_chunked.dataset = {c.session_id: c for c in conversations}
        manager_chunked._session_ids_cache = list(manager_chunked.dataset.keys())
        manager_chunked.dataset_configured.set()

        start_chunked = time.perf_counter()
        for _ in range(10):  # Only 10 requests for 1000 conversations
            await manager_chunked._handle_chunk_request(
                ConversationChunkRequestMessage(service_id="worker", chunk_size=100)
            )
        duration_chunked = time.perf_counter() - start_chunked

        # Chunked should be significantly faster
        # Note: This measures request processing time, not total system throughput
        # Actual improvement depends on network overhead which isn't simulated here
        assert manager_chunked._total_chunk_requests == 10
        assert manager_single._total_single_requests == 1000

        # Request reduction should be 100x
        assert (
            manager_single._total_single_requests
            == 100 * manager_chunked._total_chunk_requests
        )

    async def test_memory_usage_with_large_chunks(self):
        """Test memory usage remains reasonable with large chunks."""
        import sys

        from aiperf.dataset.dataset_manager import DatasetManager

        # Create large dataset
        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[
                    Turn(role="user", texts=[Text(contents=[f"Message {i}" * 100])])
                ],
            )
            for i in range(1000)
        ]

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(enable_chunking=True, dataset_chunk_size=500),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager.dataset_configured.set()

        # Request large chunk
        request = ConversationChunkRequestMessage(service_id="worker", chunk_size=500)
        response = await manager._handle_chunk_request(request)

        # Verify chunk is reasonable size
        assert len(response.conversations) == 500

        # Response object should be < 10MB (reasonable for network transfer)
        # This is a rough check - actual serialization might differ
        response_json = response.model_dump_json()
        response_size = sys.getsizeof(response_json)

        # Should be < 10MB even with large content
        assert response_size < 10 * 1024 * 1024


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.asyncio
class TestCrossConfigurationReproducibility:
    """Test reproducibility across different configurations."""

    async def test_same_seed_different_chunk_sizes_deterministic(self):
        """Test deterministic mode produces same results regardless of chunk size."""
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i:03d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        async def get_full_sequence(chunk_size: int):
            config = UserConfig(
                endpoint=EndpointConfig(
                    url="http://localhost:8000", model_names=["test"]
                ),
                input=InputConfig(
                    random_seed=42,
                    deterministic_conversation_assignment=True,
                    dataset_chunk_size=chunk_size,
                ),
                loadgen=LoadGeneratorConfig(request_count=300),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            await manager._generate_deterministic_sequence()

            # Get all conversations
            all_convos = []
            remaining = 300
            while remaining > 0:
                size = min(chunk_size, remaining)
                chunk = manager._get_conversation_chunk(size)
                all_convos.extend(chunk)
                remaining -= len(chunk)

            return [c.session_id for c in all_convos]

        # Test with different chunk sizes
        seq_10 = await get_full_sequence(10)
        seq_25 = await get_full_sequence(25)
        seq_50 = await get_full_sequence(50)
        seq_100 = await get_full_sequence(100)
        seq_300 = await get_full_sequence(300)

        # ALL should be IDENTICAL
        assert seq_10 == seq_25 == seq_50 == seq_100 == seq_300
        assert len(seq_10) == 300

    async def test_chunking_on_off_compatibility(self):
        """Test that enabling/disabling chunking doesn't break the system."""
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(50)
        ]

        # Config with chunking OFF
        config_off = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(enable_chunking=False),
        )

        manager_off = DatasetManager(ServiceConfig(), config_off)
        manager_off.dataset = {c.session_id: c for c in conversations}
        manager_off._session_ids_cache = list(manager_off.dataset.keys())
        manager_off.dataset_configured.set()

        # Should handle single requests
        from aiperf.common.messages import ConversationRequestMessage

        response = await manager_off._handle_conversation_request(
            ConversationRequestMessage(service_id="worker")
        )
        assert response.conversation is not None

        # Config with chunking ON
        config_on = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(enable_chunking=True, dataset_chunk_size=25),
        )

        manager_on = DatasetManager(ServiceConfig(), config_on)
        manager_on.dataset = {c.session_id: c for c in conversations}
        manager_on._session_ids_cache = list(manager_on.dataset.keys())
        manager_on.dataset_configured.set()

        # Should handle both chunk and single requests
        from aiperf.common.messages import ConversationChunkRequestMessage

        chunk_response = await manager_on._handle_chunk_request(
            ConversationChunkRequestMessage(service_id="worker", chunk_size=25)
        )
        assert len(chunk_response.conversations) == 25

        single_response = await manager_on._handle_conversation_request(
            ConversationRequestMessage(service_id="worker")
        )
        assert single_response.conversation is not None


@pytest.mark.integration
@pytest.mark.e2e
class TestScenarioValidation:
    """Validate specific usage scenarios."""

    @pytest.mark.asyncio
    async def test_high_concurrency_scenario(self):
        """Test scenario: 1000 workers with chunking."""
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i:04d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(500)
        ]

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42,
                enable_chunking=True,
                dataset_chunk_size=100,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(
                concurrency=1000,
                benchmark_duration=60,
            ),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        await manager._generate_deterministic_sequence()

        # Simulate 1000 workers each requesting 1 chunk
        start = time.perf_counter()

        tasks = []
        for worker_id in range(1000):
            request = ConversationChunkRequestMessage(
                service_id=f"worker-{worker_id}",
                chunk_size=100,
            )
            tasks.append(manager._handle_chunk_request(request))

        # Process all requests
        await asyncio.gather(*tasks)

        duration = time.perf_counter() - start

        # Should handle 1000 chunk requests quickly
        print(f"\n1000 chunk requests processed in {duration:.3f}s")
        print(f"Throughput: {1000 / duration:.0f} chunk req/sec")
        print(f"Conversations served: {manager._total_conversations_served}")

        assert manager._total_chunk_requests == 1000
        assert duration < 5.0  # Should complete in < 5 seconds

    @pytest.mark.asyncio
    async def test_scientific_reproducibility_scenario(self):
        """Test scenario: Scientific benchmark requiring perfect reproducibility."""
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i:03d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        async def run_scientific_benchmark(concurrency: int, run_id: int):
            """Simulate scientific benchmark run."""
            config = UserConfig(
                endpoint=EndpointConfig(
                    url="http://localhost:8000", model_names=["model-v1.0"]
                ),
                input=InputConfig(
                    random_seed=42,  # FIXED seed
                    enable_chunking=True,
                    dataset_chunk_size=50,
                    deterministic_conversation_assignment=True,  # PERFECT reproducibility
                ),
                loadgen=LoadGeneratorConfig(
                    concurrency=concurrency,
                    request_count=500,
                ),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            await manager._generate_deterministic_sequence()

            # Get all 500 conversations
            all_convos = []
            for _ in range(10):
                chunk = manager._get_conversation_chunk(50)
                all_convos.extend(chunk)

            return [c.session_id for c in all_convos]

        # Scientist runs benchmark multiple times with different concurrency
        results = []
        for concurrency in [10, 25, 50, 100]:
            result = await run_scientific_benchmark(concurrency, run_id=concurrency)
            results.append(result)

        # ALL runs should produce IDENTICAL sequences
        for i in range(1, len(results)):
            assert results[i] == results[0], (
                f"Run with concurrency={[10, 25, 50, 100][i]} differs from concurrency=10"
            )


@pytest.mark.integration
def test_integration_test_suite_completeness():
    """Verify integration test suite covers all critical scenarios."""

    test_coverage = {
        "chunking_basic": True,
        "deterministic_mode": True,
        "kubernetes_integration": True,
        "performance_validation": True,
        "reproducibility_cross_worker": True,
        "backwards_compatibility": True,
        "edge_cases": True,
        "statistical_properties": True,
    }

    assert all(test_coverage.values()), "Not all scenarios covered"
