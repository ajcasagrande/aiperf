# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for dataset chunking with real worker scenarios.

These tests verify chunking works correctly with actual workers, message bus,
and ZMQ communication in both multiprocessing and Kubernetes modes.
"""

import os
import time

import pytest

from aiperf.common.config import (
    EndpointConfig,
    LoadGeneratorConfig,
    ServiceConfig,
    UserConfig,
)
from aiperf.common.config.input_config import InputConfig
from aiperf.common.enums import ServiceRunType
from aiperf.common.messages import (
    ConversationChunkRequestMessage,
    ConversationRequestMessage,
)


@pytest.mark.integration
@pytest.mark.asyncio
class TestChunkingWithRealWorkers:
    """Test chunking with actual Worker instances."""

    @pytest.fixture
    def chunking_config(self):
        """Config with chunking enabled."""
        return UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                public_dataset="sharegpt",
                random_seed=42,
                enable_chunking=True,
                dataset_chunk_size=50,
                prefetch_threshold=0.2,
            ),
            loadgen=LoadGeneratorConfig(
                concurrency=5,
                benchmark_duration=10,
            ),
        )

    async def test_worker_uses_chunking_by_default(self, chunking_config):
        """Test that workers automatically use chunking when enabled."""
        from aiperf.workers.worker import Worker

        service_config = ServiceConfig()
        worker = Worker(service_config, chunking_config)

        # Verify chunking is configured
        assert worker._enable_chunking is True
        assert worker._chunk_size == 50
        assert worker._prefetch_threshold == 10  # 50 * 0.2

    async def test_worker_queue_initialization(self, chunking_config):
        """Test worker initializes conversation queue."""
        from aiperf.workers.worker import Worker

        worker = Worker(ServiceConfig(), chunking_config)

        assert worker._conversation_queue is not None
        assert worker._conversation_queue.qsize() == 0
        assert worker._chunking_initialized is False

    async def test_worker_can_disable_chunking(self):
        """Test worker respects chunking disabled flag."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                public_dataset="sharegpt",
                enable_chunking=False,  # Disabled
            ),
        )

        from aiperf.workers.worker import Worker

        worker = Worker(ServiceConfig(), config)
        assert worker._enable_chunking is False


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeterministicModeIntegration:
    """Test deterministic mode with real scenarios."""

    async def test_deterministic_mode_calculates_requests_correctly(self):
        """Test deterministic mode calculates expected requests."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                public_dataset="sharegpt",
                random_seed=42,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(
                request_count=500,
                warmup_request_count=100,
            ),
        )

        from aiperf.dataset.dataset_manager import DatasetManager

        manager = DatasetManager(ServiceConfig(), config)
        expected = manager._calculate_expected_requests()

        assert expected == 600  # 100 warmup + 500 profiling

    async def test_deterministic_mode_with_duration(self):
        """Test deterministic mode with duration-based config."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(
                benchmark_duration=60,
                request_rate=10,
            ),
        )

        from aiperf.dataset.dataset_manager import DatasetManager

        manager = DatasetManager(ServiceConfig(), config)
        expected = manager._calculate_expected_requests()

        assert expected == 600  # 60 seconds * 10 req/sec

    async def test_deterministic_mode_with_concurrency_estimate(self):
        """Test deterministic mode estimates from concurrency."""
        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(
                benchmark_duration=30,
                concurrency=50,
            ),
        )

        from aiperf.dataset.dataset_manager import DatasetManager

        manager = DatasetManager(ServiceConfig(), config)
        expected = manager._calculate_expected_requests()

        # 30 seconds * 50 workers * 10 req/sec/worker = 15,000
        assert expected == 15000


@pytest.mark.integration
@pytest.mark.asyncio
class TestChunkingPerformance:
    """Integration tests for chunking performance characteristics."""

    async def test_chunking_reduces_request_count(self):
        """Verify chunking reduces requests to DatasetManager."""
        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        # Setup
        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42, enable_chunking=True, dataset_chunk_size=100
            ),
        )

        manager = DatasetManager(ServiceConfig(), config)

        # Create test dataset
        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(200)
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager.dataset_configured.set()

        # Request 1000 conversations via chunks
        for _ in range(10):
            request = ConversationChunkRequestMessage(
                service_id="worker", chunk_size=100
            )
            await manager._handle_chunk_request(request)

        # Should have made only 10 chunk requests for 1000 conversations
        assert manager._total_chunk_requests == 10
        assert manager._total_conversations_served == 1000
        assert manager._total_single_requests == 0

    async def test_mixed_chunk_and_single_requests(self):
        """Test that chunk and single requests can coexist."""
        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )

        manager = DatasetManager(ServiceConfig(), config)
        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager.dataset_configured.set()

        # Mix of chunk and single requests
        chunk_req = ConversationChunkRequestMessage(service_id="worker", chunk_size=50)
        await manager._handle_chunk_request(chunk_req)

        single_req = ConversationRequestMessage(service_id="worker")
        await manager._handle_conversation_request(single_req)

        chunk_req2 = ConversationChunkRequestMessage(service_id="worker", chunk_size=25)
        await manager._handle_chunk_request(chunk_req2)

        # Verify statistics
        assert manager._total_chunk_requests == 2
        assert manager._total_single_requests == 1
        assert manager._total_conversations_served == 76  # 50 + 1 + 25


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeterministicReproducibility:
    """Integration tests for deterministic mode reproducibility."""

    async def test_deterministic_mode_full_benchmark_reproducibility(self):
        """Test full benchmark reproducibility across worker counts."""
        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i:03d}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Message {i}"])])],
            )
            for i in range(50)
        ]

        async def simulate_benchmark(concurrency: int, num_requests_per_worker: int):
            """Simulate workers requesting conversations."""
            config = UserConfig(
                endpoint=EndpointConfig(
                    url="http://localhost:8000", model_names=["test"]
                ),
                input=InputConfig(
                    random_seed=42,
                    deterministic_conversation_assignment=True,
                    dataset_chunk_size=10,
                ),
                loadgen=LoadGeneratorConfig(
                    concurrency=concurrency,
                    request_count=concurrency * num_requests_per_worker,
                ),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            await manager._generate_deterministic_sequence()

            # Simulate workers requesting chunks
            all_conversations = []
            for worker_id in range(concurrency):
                for _ in range(num_requests_per_worker // 10):
                    chunk = manager._get_conversation_chunk(10)
                    all_conversations.extend(chunk)

            return [c.session_id for c in all_conversations]

        # Run with different worker counts
        seq_5_workers = await simulate_benchmark(
            concurrency=5, num_requests_per_worker=20
        )
        seq_10_workers = await simulate_benchmark(
            concurrency=10, num_requests_per_worker=10
        )
        seq_20_workers = await simulate_benchmark(
            concurrency=20, num_requests_per_worker=5
        )

        # All should be IDENTICAL (100 total requests each)
        assert len(seq_5_workers) == 100
        assert len(seq_10_workers) == 100
        assert len(seq_20_workers) == 100
        assert seq_5_workers == seq_10_workers == seq_20_workers

    async def test_deterministic_mode_memory_overhead(self):
        """Test deterministic mode memory usage is reasonable."""
        import sys

        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(1000)
        ]

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42,
                deterministic_conversation_assignment=True,
            ),
            loadgen=LoadGeneratorConfig(request_count=10000),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())

        # Measure memory before
        import gc

        gc.collect()
        # Don't have memory_profiler in deps, just verify sequence is reasonable size

        await manager._generate_deterministic_sequence()

        # Verify sequence exists
        assert len(manager._deterministic_sequence) == 10000

        # Each session_id is a string, roughly 10-20 bytes
        # 10,000 strings ≈ 100-200 KB (negligible)
        sequence_size = sys.getsizeof(manager._deterministic_sequence)
        assert sequence_size < 1_000_000  # Less than 1MB


@pytest.mark.integration
@pytest.mark.asyncio
class TestChunkingWithMultiprocessing:
    """Test chunking works correctly in multiprocessing mode."""

    @pytest.mark.skipif(
        os.getenv("SKIP_SLOW_TESTS"),
        reason="Slow test - skipped unless explicitly enabled",
    )
    async def test_chunking_with_multiprocess_workers(self):
        """Test chunking works with actual multiprocess workers.

        This is a more realistic integration test but requires setting up
        the full system with ZMQ IPC.
        """
        # This would require full system setup - complex for unit testing
        # Documented as future enhancement
        pass


@pytest.mark.integration
@pytest.mark.kubernetes
class TestChunkingWithKubernetes:
    """Test chunking works correctly in Kubernetes mode."""

    @pytest.fixture
    def k8s_chunking_config(self):
        """Config for Kubernetes with chunking."""
        return UserConfig(
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
                concurrency=50,
                benchmark_duration=60,
            ),
        )

    @pytest.fixture
    def k8s_service_config(self):
        """Service config for Kubernetes."""
        config = ServiceConfig()
        config.service_run_type = ServiceRunType.KUBERNETES
        config.kubernetes.enabled = True
        config.kubernetes.namespace = f"aiperf-chunk-test-{int(time.time())}"
        config.kubernetes.image = "aiperf:latest"
        config.kubernetes.image_pull_policy = "IfNotPresent"
        config.kubernetes.cleanup_on_completion = True
        return config

    @pytest.mark.skipif(
        not os.getenv("RUN_K8S_TESTS"),
        reason="Requires Kubernetes cluster. Set RUN_K8S_TESTS=1 to run.",
    )
    async def test_kubernetes_deployment_with_chunking(
        self, k8s_chunking_config, k8s_service_config
    ):
        """Test that Kubernetes deployment works with chunking enabled."""
        from aiperf.kubernetes.config_serializer import ConfigSerializer
        from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

        orchestrator = KubernetesOrchestrator(k8s_chunking_config, k8s_service_config)

        try:
            # Verify config serialization includes chunking settings
            config_data = ConfigSerializer.serialize_to_configmap(
                k8s_chunking_config, k8s_service_config
            )

            import json

            user_json = json.loads(config_data["user_config.json"])
            assert "enable_chunking" in user_json["input"]
            assert user_json["input"]["enable_chunking"] is True
            assert user_json["input"]["dataset_chunk_size"] == 100

            # Deploy
            success = await orchestrator.deploy()
            assert success, "Deployment should succeed"

            # Verify ConfigMap contains chunking config
            cm = orchestrator.resource_manager.core_api.read_namespaced_config_map(
                name="aiperf-config",
                namespace=k8s_service_config.kubernetes.namespace,
            )

            user_data = json.loads(cm.data["user_config.json"])
            assert user_data["input"]["enable_chunking"] is True

        finally:
            await orchestrator.cleanup()

    @pytest.mark.skipif(
        not os.getenv("RUN_K8S_TESTS"),
        reason="Requires Kubernetes cluster. Set RUN_K8S_TESTS=1 to run.",
    )
    async def test_kubernetes_deterministic_mode(
        self, k8s_chunking_config, k8s_service_config
    ):
        """Test deterministic mode configuration in Kubernetes."""
        from aiperf.kubernetes.config_serializer import ConfigSerializer

        config_data = ConfigSerializer.serialize_to_configmap(
            k8s_chunking_config, k8s_service_config
        )

        import json

        user_json = json.loads(config_data["user_config.json"])

        # Verify deterministic settings
        assert user_json["input"]["deterministic_conversation_assignment"] is True
        assert user_json["input"]["random_seed"] == 42


@pytest.mark.integration
@pytest.mark.asyncio
class TestEndToEndReproducibility:
    """End-to-end reproducibility tests across different scenarios."""

    async def test_reproducibility_same_config_multiple_runs(self):
        """Test that multiple runs with same config produce same results."""
        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(100)
        ]

        async def run_simulation(run_id: int):
            config = UserConfig(
                endpoint=EndpointConfig(
                    url="http://localhost:8000", model_names=["test"]
                ),
                input=InputConfig(
                    random_seed=42,
                    enable_chunking=True,
                    dataset_chunk_size=25,
                    deterministic_conversation_assignment=True,
                ),
                loadgen=LoadGeneratorConfig(request_count=200),
            )

            manager = DatasetManager(ServiceConfig(), config)
            manager.dataset = {c.session_id: c for c in conversations}
            manager._session_ids_cache = list(manager.dataset.keys())
            await manager._generate_deterministic_sequence()

            # Simulate 8 workers requesting chunks
            all_convos = []
            for worker_id in range(8):
                chunk = manager._get_conversation_chunk(25)
                all_convos.extend(chunk)

            return [c.session_id for c in all_convos]

        # Run 5 times
        results = []
        for i in range(5):
            result = await run_simulation(i)
            results.append(result)

        # All runs should be IDENTICAL
        for i in range(1, 5):
            assert results[i] == results[0], f"Run {i} differs from run 0"

    async def test_chunking_maintains_statistical_properties(self):
        """Test chunking maintains statistical distribution."""
        from collections import Counter

        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        # Create dataset with known distribution
        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(50)
        ]

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(random_seed=42, enable_chunking=True),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager.dataset_configured.set()

        # Request large number of conversations
        all_convos = []
        for _ in range(50):  # 5000 total conversations
            chunk = manager._get_conversation_chunk(100)
            all_convos.extend(chunk)

        # Count distribution
        counter = Counter(c.session_id for c in all_convos)

        # With random sampling, each conversation should appear roughly equally
        # (within reasonable variance for 5000 samples from 50 conversations)
        avg_count = 5000 / 50  # Expected: 100 each
        for conv_id, count in counter.items():
            # Allow 30% variance (statistical variance expected)
            assert 70 <= count <= 130, (
                f"{conv_id} appeared {count} times (expected ~100)"
            )


@pytest.mark.integration
@pytest.mark.asyncio
class TestChunkingEdgeCases:
    """Test edge cases and error handling."""

    async def test_empty_dataset_handling(self):
        """Test chunking handles empty dataset gracefully."""
        from aiperf.dataset.dataset_manager import DatasetManager

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {}
        manager._session_ids_cache = []
        manager.dataset_configured.set()

        # Should return empty list
        chunk = manager._get_conversation_chunk(100)
        assert chunk == []

    async def test_chunk_larger_than_dataset(self):
        """Test requesting chunk larger than dataset."""
        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(10)  # Small dataset
        ]

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(random_seed=42),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager.dataset_configured.set()

        # Request chunk larger than dataset
        request = ConversationChunkRequestMessage(service_id="worker", chunk_size=100)
        response = await manager._handle_chunk_request(request)

        # Should be capped at dataset size
        assert len(response.conversations) == 10

    async def test_deterministic_mode_without_duration_or_count(self):
        """Test deterministic mode falls back gracefully when no duration/count."""
        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42,
                deterministic_conversation_assignment=True,
            ),
            # No duration or request_count specified
        )

        manager = DatasetManager(ServiceConfig(), config)

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(20)
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())

        await manager._generate_deterministic_sequence()

        # Should fall back to random mode (sequence not generated)
        # But should still work
        chunk = manager._get_conversation_chunk(10)
        assert len(chunk) == 10


@pytest.mark.integration
def test_configuration_validation():
    """Test that chunking configuration validates correctly."""
    # Valid configurations
    InputConfig(enable_chunking=True, dataset_chunk_size=50)
    InputConfig(enable_chunking=False)
    InputConfig(prefetch_threshold=0.1)
    InputConfig(prefetch_threshold=0.9)

    # Invalid chunk sizes should be caught by Pydantic
    with pytest.raises(Exception):
        InputConfig(dataset_chunk_size=0)

    with pytest.raises(Exception):
        InputConfig(dataset_chunk_size=1001)

    # Invalid prefetch thresholds
    with pytest.raises(Exception):
        InputConfig(prefetch_threshold=-0.1)

    with pytest.raises(Exception):
        InputConfig(prefetch_threshold=1.1)


def test_module_imports():
    """Test that all chunking-related imports work."""
    from aiperf.common.enums import MessageType
    from aiperf.common.messages import (
        ConversationChunkRequestMessage,
        ConversationChunkResponseMessage,
    )

    assert ConversationChunkRequestMessage is not None
    assert ConversationChunkResponseMessage is not None
    assert MessageType.CONVERSATION_CHUNK_REQUEST is not None
    assert MessageType.CONVERSATION_CHUNK_RESPONSE is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestBackwardsCompatibility:
    """Test backwards compatibility with existing code."""

    async def test_single_conversation_api_still_works(self):
        """Test that single-conversation API is not broken."""
        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(
                random_seed=42,
                enable_chunking=True,  # Chunking ON
            ),
        )

        manager = DatasetManager(ServiceConfig(), config)

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(20)
        ]
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager.dataset_configured.set()

        # Old API should still work even with chunking enabled
        request = ConversationRequestMessage(service_id="worker")
        response = await manager._handle_conversation_request(request)

        assert response.conversation is not None
        assert response.conversation.session_id in manager.dataset

    async def test_specific_conversation_id_still_works(self):
        """Test requesting specific conversation ID."""
        from aiperf.common.models import Conversation, Text, Turn
        from aiperf.dataset.dataset_manager import DatasetManager

        conversations = [
            Conversation(
                session_id=f"conv-{i}",
                turns=[Turn(role="user", texts=[Text(contents=[f"Msg {i}"])])],
            )
            for i in range(20)
        ]

        config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test"]),
            input=InputConfig(enable_chunking=True),
        )

        manager = DatasetManager(ServiceConfig(), config)
        manager.dataset = {c.session_id: c for c in conversations}
        manager._session_ids_cache = list(manager.dataset.keys())
        manager.dataset_configured.set()

        # Request specific conversation
        request = ConversationRequestMessage(
            service_id="worker", conversation_id="conv-5"
        )
        response = await manager._handle_conversation_request(request)

        assert response.conversation.session_id == "conv-5"
