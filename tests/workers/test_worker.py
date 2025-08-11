# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiperf.common.enums import CreditPhase, ServiceType
from aiperf.common.messages import CreditReturnMessage
from aiperf.common.models import WorkerPhaseTaskStats
from aiperf.workers.worker import Worker
from tests.workers.conftest import WorkerTestBase


class TestWorker(WorkerTestBase):
    """Test the Worker service core functionality."""

    @pytest.fixture
    def worker_service(
        self,
        worker_service_config,
        worker_user_config,
        mock_communication_factory,
        mock_inference_dependencies,
    ):
        """Create a worker instance with mocked dependencies."""
        deps = mock_inference_dependencies

        with (
            patch(
                "aiperf.workers.worker.ModelEndpointInfo.from_user_config"
            ) as mock_endpoint,
            patch(
                "aiperf.workers.worker.InferenceClientFactory"
            ) as mock_client_factory,
            patch(
                "aiperf.workers.worker.RequestConverterFactory"
            ) as mock_converter_factory,
        ):
            mock_endpoint.return_value = deps["model_endpoint"]
            mock_client_factory.create_instance.return_value = deps["inference_client"]
            mock_converter_factory.create_instance.return_value = deps[
                "request_converter"
            ]

            mock_client_class = MagicMock()
            mock_client_class.__name__ = "MockInferenceClient"
            mock_client_factory.get_class_from_type.return_value = mock_client_class

            worker = Worker(
                service_config=worker_service_config,
                user_config=worker_user_config,
                service_id="test-worker",
            )

            # Mock communication clients that would normally be created by the worker
            worker.credit_return_push_client = AsyncMock()
            worker.inference_results_push_client = AsyncMock()
            worker.conversation_request_client = AsyncMock()

            return worker

    def test_worker_service_type_registration(self):
        """Test that Worker is properly registered with ServiceFactory."""
        from aiperf.common.factories import ServiceFactory

        service_class = ServiceFactory.get_class_from_type(ServiceType.WORKER)
        assert service_class == Worker

    def test_worker_initialization(self, worker_service):
        """Test worker initializes with correct attributes."""
        worker = worker_service

        # Use base test assertions
        self.assert_service_initialized(worker)
        self.assert_communication_setup(worker)
        self.assert_pull_client_setup(worker)
        self.assert_process_health_setup(worker)

        # Test Worker-specific attributes
        assert worker.service_id == "test-worker"
        assert worker.health_check_interval == 1.0
        assert isinstance(worker.task_stats, dict)

    @pytest.mark.asyncio
    async def test_credit_drop_callback_success(
        self,
        worker_service,
        sample_credit_drop_message,
    ):
        """Test successful credit drop processing."""
        worker = worker_service

        expected_return = CreditReturnMessage(
            service_id="test-worker",
            phase=CreditPhase.WARMUP,
            delayed_ns=None,
        )

        with patch.object(
            worker, "_process_credit_drop_internal", return_value=expected_return
        ) as mock_process:
            await worker._credit_drop_callback(sample_credit_drop_message)

            mock_process.assert_called_once_with(sample_credit_drop_message)
            worker.credit_return_push_client.push.assert_called_once_with(
                expected_return
            )

    @pytest.mark.asyncio
    async def test_credit_drop_callback_exception(
        self,
        worker_service,
        sample_credit_drop_message,
    ):
        """Test credit drop callback handles exceptions and still returns credit."""
        worker = worker_service

        with patch.object(
            worker, "_process_credit_drop_internal", side_effect=Exception("Test error")
        ):
            await worker._credit_drop_callback(sample_credit_drop_message)

            # Should still return a default credit return message
            worker.credit_return_push_client.push.assert_called_once()
            call_args = worker.credit_return_push_client.push.call_args[0][0]
            assert isinstance(call_args, CreditReturnMessage)
            assert call_args.service_id == "test-worker"
            assert call_args.phase == CreditPhase.WARMUP

    def test_task_stats_tracking(self, worker_service):
        """Test that task stats are properly tracked."""
        worker = worker_service

        phase = CreditPhase.WARMUP
        assert phase not in worker.task_stats

        worker.task_stats[phase] = WorkerPhaseTaskStats()
        worker.task_stats[phase].total += 1
        worker.task_stats[phase].completed += 1

        assert worker.task_stats[phase].total == 1
        assert worker.task_stats[phase].completed == 1
        assert worker.task_stats[phase].failed == 0
