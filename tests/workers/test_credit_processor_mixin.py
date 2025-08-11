# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import patch

import pytest

from aiperf.common.enums import CreditPhase
from aiperf.common.exceptions import NotInitializedError
from aiperf.common.messages import (
    CreditDropMessage,
    CreditReturnMessage,
    InferenceResultsMessage,
)
from aiperf.common.models import RequestRecord, WorkerPhaseTaskStats
from aiperf.workers.credit_processor_mixin import CreditProcessorMixin
from tests.workers.conftest import WorkerTestBase


class TestCreditProcessorMixin(WorkerTestBase):
    """Test the CreditProcessorMixin functionality."""

    @pytest.fixture
    def mock_credit_processor(self, mock_inference_dependencies):
        """Create a mock credit processor with all required dependencies."""

        class MockCreditProcessor(CreditProcessorMixin):
            """Complete mock implementation for testing CreditProcessorMixin."""

            def __init__(self):
                self.service_id = "test-service"
                self.task_stats = {}

                # Set up all required attributes from dependencies
                deps = mock_inference_dependencies
                self.inference_client = deps["inference_client"]
                self.conversation_request_client = deps["conversation_request_client"]
                self.inference_results_push_client = deps[
                    "inference_results_push_client"
                ]
                self.request_converter = deps["request_converter"]
                self.model_endpoint = deps["model_endpoint"]
                self.model_endpoint.primary_model_name = "test-model"

            # Implement required logger protocol methods
            def trace(self, message):
                pass

            def debug(self, message):
                pass

            def info(self, message):
                pass

            def warning(self, message):
                pass

            def error(self, message):
                pass

            def exception(self, message):
                pass

            def critical(self, message):
                pass

            @property
            def is_trace_enabled(self) -> bool:
                return True

            @property
            def is_debug_enabled(self) -> bool:
                return True

            @property
            def is_info_enabled(self) -> bool:
                return True

            @property
            def is_warning_enabled(self) -> bool:
                return True

            @property
            def is_error_enabled(self) -> bool:
                return True

            @property
            def is_critical_enabled(self) -> bool:
                return True

        return MockCreditProcessor()

    @pytest.mark.asyncio
    async def test_process_credit_drop_success(
        self,
        mock_credit_processor,
        sample_credit_drop_message: CreditDropMessage,
    ):
        """Test successful credit drop processing."""
        from aiperf.common.models.record_models import TextResponse

        sample_record = RequestRecord()
        sample_record.start_perf_ns = 1000000000  # Make it valid
        sample_record.responses = [
            TextResponse(
                perf_ns=1000050000,  # Valid timestamp
                text="Test response",
            )
        ]

        with patch.object(
            mock_credit_processor,
            "_execute_single_credit_internal",
            return_value=sample_record,
        ):
            result = await mock_credit_processor._process_credit_drop_internal(
                sample_credit_drop_message
            )

            # Should return a CreditReturnMessage
            assert isinstance(result, CreditReturnMessage)
            assert result.service_id == "test-service"
            assert result.phase == CreditPhase.PROFILING

            # Should push InferenceResultsMessage
            mock_credit_processor.inference_results_push_client.push.assert_called_once()
            pushed_msg = (
                mock_credit_processor.inference_results_push_client.push.call_args[0][0]
            )
            assert isinstance(pushed_msg, InferenceResultsMessage)

            # Should update task stats
            assert CreditPhase.PROFILING in mock_credit_processor.task_stats
            assert mock_credit_processor.task_stats[CreditPhase.PROFILING].total == 1
            assert (
                mock_credit_processor.task_stats[CreditPhase.PROFILING].completed == 1
            )

    @pytest.mark.asyncio
    async def test_process_credit_drop_exception(
        self,
        mock_credit_processor,
        sample_credit_drop_message: CreditDropMessage,
    ):
        """Test credit drop processing handles exceptions correctly."""
        with patch.object(
            mock_credit_processor,
            "_execute_single_credit_internal",
            side_effect=Exception("Test error"),
        ):
            result = await mock_credit_processor._process_credit_drop_internal(
                sample_credit_drop_message
            )

            # Should still return a CreditReturnMessage
            assert isinstance(result, CreditReturnMessage)
            assert result.service_id == "test-service"

            # Should update task stats for failed request
            assert mock_credit_processor.task_stats[CreditPhase.PROFILING].total == 1
            assert mock_credit_processor.task_stats[CreditPhase.PROFILING].failed == 1
            assert (
                mock_credit_processor.task_stats[CreditPhase.PROFILING].completed == 0
            )

    @pytest.mark.asyncio
    async def test_execute_single_credit_no_inference_client(
        self,
        mock_credit_processor,
        sample_credit_drop_message: CreditDropMessage,
    ):
        """Test that missing inference client raises NotInitializedError."""
        # Create a new mock with None inference client
        mock_credit_processor.inference_client = None

        with pytest.raises(
            NotInitializedError, match="Inference server client not initialized"
        ):
            await mock_credit_processor._execute_single_credit_internal(
                sample_credit_drop_message
            )


class TestCreditProcessorMixinSync:
    """Non-async tests for CreditProcessorMixin."""

    def test_task_stats_initialization(self, mock_inference_dependencies):
        """Test that task stats are properly initialized."""

        class SimpleMockProcessor:
            def __init__(self):
                self.task_stats = {}

        processor = SimpleMockProcessor()
        phase = CreditPhase.PROFILING
        assert phase not in processor.task_stats

        processor.task_stats[phase] = WorkerPhaseTaskStats()
        processor.task_stats[phase].total += 1

        assert isinstance(processor.task_stats[phase], WorkerPhaseTaskStats)
        assert processor.task_stats[phase].total == 1
