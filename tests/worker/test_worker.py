# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Comprehensive tests for the worker service.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiperf.common.enums import MessageType, ServiceState, ServiceType
from aiperf.common.exceptions import NotInitializedError
from aiperf.common.messages import (
    CommandMessage,
    ConversationResponseMessage,
    CreditDropMessage,
    CreditReturnMessage,
    ErrorMessage,
    InferenceResultsMessage,
    WorkerHealthMessage,
)
from aiperf.common.models import (
    ErrorDetails,
    RequestRecord,
)
from aiperf.services.workers.worker import Worker
from tests.utils.async_test_utils import async_fixture


@pytest.mark.asyncio
class TestWorkerInitialization:
    """Test worker initialization and configuration."""

    async def test_worker_initialization(
        self,
        worker_instance: Worker,
        mock_communication_clients: dict[str, AsyncMock],
    ) -> None:
        """Test worker initializes correctly with all dependencies."""
        worker = await async_fixture(worker_instance)

        # Verify initial state
        assert worker.service_type == ServiceType.WORKER
        assert worker.service_id == "test-worker"
        assert worker.completed_tasks == 0
        assert worker.failed_tasks == 0
        assert worker.total_tasks == 0
        assert worker.warmup_tasks == 0
        assert worker.warmup_failed_tasks == 0

        # Verify dependencies are set
        assert worker.comms is not None
        assert worker.inference_client is not None
        assert worker.request_converter is not None
        assert worker.model_endpoint is not None

    async def test_worker_initialize_method(
        self,
        worker_instance: Worker,
        mock_communication_clients: dict[str, AsyncMock],
    ) -> None:
        """Test worker initialization method."""
        worker = await async_fixture(worker_instance)

        # Set up the communication clients
        worker.credit_drop_client = mock_communication_clients["credit_drop"]
        worker.credit_return_client = mock_communication_clients["credit_return"]
        worker.inference_results_client = mock_communication_clients[
            "inference_results"
        ]
        worker.conversation_data_client = mock_communication_clients[
            "conversation_data"
        ]
        worker.pub_client = mock_communication_clients["pub"]

        # Initialize worker
        await worker.initialize()

        # Verify initialization
        assert worker.is_initialized
        worker.comms.initialize.assert_called_once()
        worker.credit_drop_client.register_pull_callback.assert_called_once_with(
            MessageType.CREDIT_DROP, worker._process_credit_drop
        )

    async def test_worker_configuration(
        self,
        initialized_worker: Worker,
        command_message: CommandMessage,
    ) -> None:
        """Test worker configuration method."""
        worker = await async_fixture(initialized_worker)

        # Configure should not raise an exception
        await worker._configure(command_message)

        # Worker should remain in ready state
        assert worker.state == ServiceState.READY

    async def test_worker_shutdown(
        self,
        initialized_worker: Worker,
    ) -> None:
        """Test worker shutdown method."""
        worker = await async_fixture(initialized_worker)

        # Shutdown the worker
        await worker._do_shutdown()

        # Verify shutdown
        assert worker.stop_event.is_set()
        worker.comms.shutdown.assert_called_once()
        worker.inference_client.close.assert_called_once()


@pytest.mark.asyncio
class TestCreditDropProcessing:
    """Test credit drop message processing."""

    async def test_process_credit_drop_success(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
        sample_conversation_response: ConversationResponseMessage,
        sample_request_record: RequestRecord,
        mock_time_functions: dict[str, MagicMock],
    ) -> None:
        """Test successful credit drop processing."""
        worker = await async_fixture(initialized_worker)

        # Mock the conversation data client response
        worker.conversation_data_client.request.return_value = (
            sample_conversation_response
        )

        # Mock the inference client response
        worker.inference_client.send_request.return_value = sample_request_record

        # Process credit drop
        await worker._process_credit_drop(sample_credit_drop_message)

        # Verify metrics were updated
        assert worker.total_tasks == 1
        assert worker.completed_tasks == 1
        assert worker.failed_tasks == 0
        assert worker.warmup_tasks == 0

        # Verify inference results were pushed
        worker.inference_results_client.push.assert_called_once()

        # Verify credits were returned
        worker.credit_return_client.push.assert_called_once()

        # Verify the credit return message
        credit_return_call = worker.credit_return_client.push.call_args[1]["message"]
        assert isinstance(credit_return_call, CreditReturnMessage)
        assert (
            credit_return_call.conversation_id
            == sample_credit_drop_message.conversation_id
        )
        assert credit_return_call.credit_phase is False

    async def test_process_warmup_credit_drop(
        self,
        initialized_worker: Worker,
        sample_warmup_credit_drop_message: CreditDropMessage,
        sample_conversation_response: ConversationResponseMessage,
        sample_request_record: RequestRecord,
    ) -> None:
        """Test warmup credit drop processing."""
        worker = await async_fixture(initialized_worker)

        # Mock the conversation data client response
        worker.conversation_data_client.request.return_value = (
            sample_conversation_response
        )

        # Mock the inference client response
        worker.inference_client.send_request.return_value = sample_request_record

        # Process warmup credit drop
        await worker._process_credit_drop(sample_warmup_credit_drop_message)

        # Verify metrics were updated correctly for warmup
        assert worker.total_tasks == 1
        assert worker.completed_tasks == 0  # Warmup tasks don't count as completed
        assert worker.failed_tasks == 0
        assert worker.warmup_tasks == 1
        assert worker.warmup_failed_tasks == 0

        # Verify the credit return message indicates warmup
        credit_return_call = worker.credit_return_client.push.call_args[1]["message"]
        assert credit_return_call.warmup is True

    async def test_process_credit_drop_with_error(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
    ) -> None:
        """Test credit drop processing with error."""
        worker = await async_fixture(initialized_worker)

        # Mock the conversation data client to raise an exception
        worker.conversation_data_client.request.side_effect = Exception("Test error")

        # Process credit drop
        await worker._process_credit_drop(sample_credit_drop_message)

        # Verify metrics were updated for failure
        assert worker.total_tasks == 1
        assert worker.completed_tasks == 0
        assert worker.failed_tasks == 1

        # Verify inference results were still pushed (with error)
        worker.inference_results_client.push.assert_called_once()

        # Verify credits were returned
        worker.credit_return_client.push.assert_called_once()

        # Verify the inference results message contains error
        inference_results_call = worker.inference_results_client.push.call_args[1][
            "message"
        ]
        assert isinstance(inference_results_call, InferenceResultsMessage)
        assert inference_results_call.record.error is not None
        assert not inference_results_call.record.valid

    async def test_process_credit_drop_inference_results_push_failure(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
        sample_conversation_response: ConversationResponseMessage,
        sample_request_record: RequestRecord,
    ) -> None:
        """Test credit drop processing when inference results push fails."""
        worker = await async_fixture(initialized_worker)

        # Mock the conversation data client response
        worker.conversation_data_client.request.return_value = (
            sample_conversation_response
        )

        # Mock the inference client response
        worker.inference_client.send_request.return_value = sample_request_record

        # Mock the inference results client to fail on push
        worker.inference_results_client.push.side_effect = Exception("Push failed")

        # Process credit drop - should not raise exception
        await worker._process_credit_drop(sample_credit_drop_message)

        # Verify credits were still returned even after push failure
        worker.credit_return_client.push.assert_called_once()

    async def test_process_credit_drop_error_response(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
    ) -> None:
        """Test credit drop processing with error response from conversation data."""
        worker = await async_fixture(initialized_worker)

        # Mock the conversation data client to return an error message
        error_message = ErrorMessage(
            service_id="test-service",
            error=ErrorDetails(
                error_type="DataError",
                message="Conversation not found",
                traceback="Test traceback",
            ),
        )
        worker.conversation_data_client.request.return_value = error_message

        # Process credit drop
        await worker._process_credit_drop(sample_credit_drop_message)

        # Verify metrics were updated for failure
        assert worker.total_tasks == 1
        assert worker.completed_tasks == 0
        assert worker.failed_tasks == 1

        # Verify the inference results message contains error
        inference_results_call = worker.inference_results_client.push.call_args[1][
            "message"
        ]
        assert isinstance(inference_results_call, InferenceResultsMessage)
        assert inference_results_call.record.error is not None
        assert not inference_results_call.record.valid


@pytest.mark.asyncio
class TestInferenceApiCalls:
    """Test inference API calls and related functionality."""

    async def test_execute_single_credit_success(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
        sample_conversation_response: ConversationResponseMessage,
        sample_request_record: RequestRecord,
    ) -> None:
        """Test successful execution of single credit."""
        worker = await async_fixture(initialized_worker)

        # Mock the conversation data client response
        worker.conversation_data_client.request.return_value = (
            sample_conversation_response
        )

        # Mock the inference client response
        worker.inference_client.send_request.return_value = sample_request_record

        # Execute single credit
        result = await worker._execute_single_credit(sample_credit_drop_message)

        # Verify the result
        assert result == sample_request_record
        assert worker.total_tasks == 1

        # Verify conversation data was requested
        worker.conversation_data_client.request.assert_called_once()

        # Verify inference client was called
        worker.inference_client.send_request.assert_called_once()

    async def test_execute_single_credit_no_inference_client(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
    ) -> None:
        """Test execution of single credit when inference client is not initialized."""
        worker = await async_fixture(initialized_worker)

        # Set inference client to None
        worker.inference_client = None

        # Execute single credit - should raise NotInitializedError
        with pytest.raises(NotInitializedError):
            await worker._execute_single_credit(sample_credit_drop_message)

    async def test_call_inference_api_success(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
        sample_turn,
        sample_request_record: RequestRecord,
    ) -> None:
        """Test successful inference API call."""
        worker = await async_fixture(initialized_worker)

        # Mock the request converter response
        worker.request_converter.format_payload.return_value = {
            "messages": [{"role": "user", "content": "test"}]
        }

        # Mock the inference client response
        worker.inference_client.send_request.return_value = sample_request_record

        # Call inference API
        result = await worker._call_inference_api(
            sample_credit_drop_message, sample_turn
        )

        # Verify the result
        assert result == sample_request_record

        # Verify request converter was called
        worker.request_converter.format_payload.assert_called_once()

        # Verify inference client was called
        worker.inference_client.send_request.assert_called_once()

    async def test_call_inference_api_with_delayed_execution(
        self,
        initialized_worker: Worker,
        sample_turn,
        sample_request_record: RequestRecord,
        mock_asyncio_sleep: AsyncMock,
    ) -> None:
        """Test inference API call with delayed execution."""
        worker = await async_fixture(initialized_worker)

        # Create a credit drop message with future timestamp
        future_time = time.time_ns() + 1000000000  # 1 second in the future
        credit_drop_message = CreditDropMessage(
            service_id="test-service",
            conversation_id="test-conversation",
            credit_drop_ns=future_time,
            warmup=False,
        )

        # Mock the request converter response
        worker.request_converter.format_payload.return_value = {
            "messages": [{"role": "user", "content": "test"}]
        }

        # Mock the inference client response
        worker.inference_client.send_request.return_value = sample_request_record

        # Call inference API
        result = await worker._call_inference_api(credit_drop_message, sample_turn)

        # Verify sleep was called for delayed execution
        mock_asyncio_sleep.assert_called_once()

        # Verify the result
        assert result == sample_request_record

    async def test_call_inference_api_with_past_timestamp(
        self,
        initialized_worker: Worker,
        sample_turn,
        sample_request_record: RequestRecord,
    ) -> None:
        """Test inference API call with past timestamp (delayed)."""
        worker = await async_fixture(initialized_worker)

        # Create a credit drop message with past timestamp
        past_time = time.time_ns() - 1000000000  # 1 second in the past
        credit_drop_message = CreditDropMessage(
            service_id="test-service",
            conversation_id="test-conversation",
            credit_drop_ns=past_time,
            warmup=False,
        )

        # Mock the request converter response
        worker.request_converter.format_payload.return_value = {
            "messages": [{"role": "user", "content": "test"}]
        }

        # Mock the inference client response
        worker.inference_client.send_request.return_value = sample_request_record

        # Call inference API
        result = await worker._call_inference_api(credit_drop_message, sample_turn)

        # Verify the result contains delayed_ns
        assert result.delayed_ns is not None
        assert result.delayed_ns < 0  # Should be negative for past timestamp

    async def test_call_inference_api_with_exception(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
        sample_turn,
    ) -> None:
        """Test inference API call with exception."""
        worker = await async_fixture(initialized_worker)

        # Mock the inference client to raise an exception
        worker.inference_client.send_request.side_effect = Exception("API error")

        # Call inference API
        result = await worker._call_inference_api(
            sample_credit_drop_message, sample_turn
        )

        # Verify the result is an error record
        assert isinstance(result, RequestRecord)
        assert result.error is not None
        assert not result.valid


@pytest.mark.asyncio
class TestHealthCheck:
    """Test health check functionality."""

    async def test_create_health_message(
        self,
        initialized_worker: Worker,
    ) -> None:
        """Test creation of health message."""
        worker = await async_fixture(initialized_worker)

        # Set some metrics
        worker.total_tasks = 10
        worker.completed_tasks = 8
        worker.failed_tasks = 2
        worker.warmup_tasks = 5
        worker.warmup_failed_tasks = 1

        # Create health message
        health_message = worker.create_health_message()

        # Verify health message
        assert isinstance(health_message, WorkerHealthMessage)
        assert health_message.service_id == worker.service_id
        assert health_message.total_tasks == 10
        assert health_message.completed_tasks == 8
        assert health_message.failed_tasks == 2
        assert health_message.warmup_tasks == 5
        assert health_message.warmup_failed_tasks == 1
        assert health_message.process is not None

    async def test_health_check_task(
        self,
        initialized_worker: Worker,
    ) -> None:
        """Test health check task execution."""
        worker = await async_fixture(initialized_worker)

        # Mock the health check interval to be very short
        worker.health_check_interval = 0.001

        # Start the health check task
        task = asyncio.create_task(worker._health_check_task())

        # Let it run for a short time
        await asyncio.sleep(0.01)

        # Stop the task
        worker.stop_event.set()

        # Wait for task to complete
        await asyncio.wait_for(task, timeout=1.0)

        # Verify health messages were published
        assert worker.pub_client.publish.call_count > 0

    async def test_health_check_task_with_exception(
        self,
        initialized_worker: Worker,
    ) -> None:
        """Test health check task with exception."""
        worker = await async_fixture(initialized_worker)

        # Mock the pub client to raise an exception
        worker.pub_client.publish.side_effect = Exception("Publish error")

        # Mock the health check interval to be very short
        worker.health_check_interval = 0.001

        # Start the health check task
        task = asyncio.create_task(worker._health_check_task())

        # Let it run for a short time
        await asyncio.sleep(0.01)

        # Stop the task
        worker.stop_event.set()

        # Wait for task to complete - should not raise exception
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
class TestWorkerMetrics:
    """Test worker metrics tracking."""

    async def test_metrics_initialization(
        self,
        worker_instance: Worker,
    ) -> None:
        """Test worker metrics are initialized correctly."""
        worker = await async_fixture(worker_instance)

        # Verify initial metrics
        assert worker.completed_tasks == 0
        assert worker.failed_tasks == 0
        assert worker.total_tasks == 0
        assert worker.warmup_tasks == 0
        assert worker.warmup_failed_tasks == 0

    async def test_metrics_update_on_successful_task(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
        sample_conversation_response: ConversationResponseMessage,
        sample_request_record: RequestRecord,
    ) -> None:
        """Test metrics update on successful task completion."""
        worker = await async_fixture(initialized_worker)

        # Mock successful responses
        worker.conversation_data_client.request.return_value = (
            sample_conversation_response
        )
        worker.inference_client.send_request.return_value = sample_request_record

        # Process credit drop
        await worker._process_credit_drop(sample_credit_drop_message)

        # Verify metrics
        assert worker.total_tasks == 1
        assert worker.completed_tasks == 1
        assert worker.failed_tasks == 0
        assert worker.warmup_tasks == 0
        assert worker.warmup_failed_tasks == 0

    async def test_metrics_update_on_failed_task(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
        sample_conversation_response: ConversationResponseMessage,
        sample_failed_request_record: RequestRecord,
    ) -> None:
        """Test metrics update on failed task completion."""
        worker = await async_fixture(initialized_worker)

        # Mock responses with failed record
        worker.conversation_data_client.request.return_value = (
            sample_conversation_response
        )
        worker.inference_client.send_request.return_value = sample_failed_request_record

        # Process credit drop
        await worker._process_credit_drop(sample_credit_drop_message)

        # Verify metrics
        assert worker.total_tasks == 1
        assert worker.completed_tasks == 0
        assert worker.failed_tasks == 1
        assert worker.warmup_tasks == 0
        assert worker.warmup_failed_tasks == 0

    async def test_metrics_update_on_warmup_tasks(
        self,
        initialized_worker: Worker,
        sample_warmup_credit_drop_message: CreditDropMessage,
        sample_conversation_response: ConversationResponseMessage,
        sample_request_record: RequestRecord,
        sample_failed_request_record: RequestRecord,
    ) -> None:
        """Test metrics update on warmup task completion."""
        worker = await async_fixture(initialized_worker)

        # Mock responses
        worker.conversation_data_client.request.return_value = (
            sample_conversation_response
        )

        # Process successful warmup task
        worker.inference_client.send_request.return_value = sample_request_record
        await worker._process_credit_drop(sample_warmup_credit_drop_message)

        # Verify metrics for successful warmup
        assert worker.total_tasks == 1
        assert worker.completed_tasks == 0  # Warmup tasks don't count as completed
        assert worker.failed_tasks == 0
        assert worker.warmup_tasks == 1
        assert worker.warmup_failed_tasks == 0

        # Process failed warmup task
        worker.inference_client.send_request.return_value = sample_failed_request_record
        await worker._process_credit_drop(sample_warmup_credit_drop_message)

        # Verify metrics for failed warmup
        assert worker.total_tasks == 2
        assert worker.completed_tasks == 0
        assert worker.failed_tasks == 0
        assert worker.warmup_tasks == 2
        assert worker.warmup_failed_tasks == 1


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling in various scenarios."""

    async def test_error_handling_in_process_credit_drop(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
    ) -> None:
        """Test error handling in process credit drop."""
        worker = await async_fixture(initialized_worker)

        # Mock to raise an exception
        worker.conversation_data_client.request.side_effect = Exception("Test error")

        # Process credit drop - should not raise exception
        await worker._process_credit_drop(sample_credit_drop_message)

        # Verify error was handled and metrics updated
        assert worker.failed_tasks == 1

        # Verify inference results were pushed with error
        worker.inference_results_client.push.assert_called_once()

        # Verify credits were returned
        worker.credit_return_client.push.assert_called_once()

    async def test_error_handling_in_inference_api_call(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
        sample_turn,
    ) -> None:
        """Test error handling in inference API call."""
        worker = await async_fixture(initialized_worker)

        # Mock to raise an exception
        worker.inference_client.send_request.side_effect = Exception("Inference error")

        # Call inference API
        result = await worker._call_inference_api(
            sample_credit_drop_message, sample_turn
        )

        # Verify error was handled
        assert isinstance(result, RequestRecord)
        assert result.error is not None
        assert not result.valid

    async def test_error_handling_in_health_check(
        self,
        initialized_worker: Worker,
    ) -> None:
        """Test error handling in health check task."""
        worker = await async_fixture(initialized_worker)

        # Mock to raise an exception
        worker.pub_client.publish.side_effect = Exception("Health check error")

        # Mock health check interval to be very short
        worker.health_check_interval = 0.001

        # Start health check task
        task = asyncio.create_task(worker._health_check_task())

        # Let it run briefly
        await asyncio.sleep(0.01)

        # Stop the task
        worker.stop_event.set()

        # Wait for task to complete - should not raise exception
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
class TestWorkerProtocol:
    """Test worker protocol compliance."""

    async def test_worker_implements_protocol_methods(
        self,
        initialized_worker: Worker,
    ) -> None:
        """Test worker implements required protocol methods."""
        worker = await async_fixture(initialized_worker)

        # Check that worker has all required methods
        assert hasattr(worker, "_process_credit_drop")
        assert callable(worker._process_credit_drop)

        # Check communication clients are set up
        assert worker.credit_drop_client is not None
        assert worker.credit_return_client is not None
        assert worker.inference_results_client is not None
        assert worker.conversation_data_client is not None
        assert worker.pub_client is not None

    async def test_worker_service_type(
        self,
        worker_instance: Worker,
    ) -> None:
        """Test worker service type is correct."""
        worker = await async_fixture(worker_instance)

        assert worker.service_type == ServiceType.WORKER

    async def test_worker_health_message_generation(
        self,
        initialized_worker: Worker,
    ) -> None:
        """Test worker generates valid health messages."""
        worker = await async_fixture(initialized_worker)

        # Create health message
        health_message = worker.create_health_message()

        # Verify health message structure
        assert isinstance(health_message, WorkerHealthMessage)
        assert health_message.service_id == worker.service_id
        assert hasattr(health_message, "process")
        assert hasattr(health_message, "total_tasks")
        assert hasattr(health_message, "completed_tasks")
        assert hasattr(health_message, "failed_tasks")
        assert hasattr(health_message, "warmup_tasks")
        assert hasattr(health_message, "warmup_failed_tasks")


@pytest.mark.asyncio
class TestWorkerEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_worker_with_none_credit_drop_time(
        self,
        initialized_worker: Worker,
        sample_turn,
        sample_request_record: RequestRecord,
    ) -> None:
        """Test worker behavior with None credit drop time."""
        worker = await async_fixture(initialized_worker)

        # Create credit drop message with None timestamp
        credit_drop_message = CreditDropMessage(
            service_id="test-service",
            conversation_id="test-conversation",
            credit_drop_ns=None,
            warmup=False,
        )

        # Mock the request converter and inference client
        worker.request_converter.format_payload.return_value = {
            "messages": [{"role": "user", "content": "test"}]
        }
        worker.inference_client.send_request.return_value = sample_request_record

        # Call inference API - should not raise exception
        result = await worker._call_inference_api(credit_drop_message, sample_turn)

        # Verify result
        assert result == sample_request_record

    async def test_worker_with_empty_conversation_turns(
        self,
        initialized_worker: Worker,
        sample_credit_drop_message: CreditDropMessage,
    ) -> None:
        """Test worker behavior with empty conversation turns."""
        worker = await async_fixture(initialized_worker)

        # Mock conversation response with empty turns
        from aiperf.common.models import Conversation

        empty_conversation_response = ConversationResponseMessage(
            service_id="test-service",
            conversation=Conversation(turns=[]),
        )
        worker.conversation_data_client.request.return_value = (
            empty_conversation_response
        )

        # Process credit drop - should handle gracefully
        with pytest.raises(IndexError):
            await worker._process_credit_drop(sample_credit_drop_message)

    async def test_worker_metrics_overflow_handling(
        self,
        initialized_worker: Worker,
    ) -> None:
        """Test worker handles large metric values."""
        worker = await async_fixture(initialized_worker)

        # Set large metric values
        worker.total_tasks = 999999999
        worker.completed_tasks = 999999999
        worker.failed_tasks = 999999999
        worker.warmup_tasks = 999999999
        worker.warmup_failed_tasks = 999999999

        # Create health message - should not raise exception
        health_message = worker.create_health_message()

        # Verify health message is valid
        assert isinstance(health_message, WorkerHealthMessage)
        assert health_message.total_tasks == 999999999

    async def test_worker_concurrent_credit_drops(
        self,
        initialized_worker: Worker,
        sample_conversation_response: ConversationResponseMessage,
        sample_request_record: RequestRecord,
    ) -> None:
        """Test worker handles concurrent credit drops."""
        worker = await async_fixture(initialized_worker)

        # Mock responses
        worker.conversation_data_client.request.return_value = (
            sample_conversation_response
        )
        worker.inference_client.send_request.return_value = sample_request_record

        # Create multiple credit drop messages
        credit_drops = [
            CreditDropMessage(
                service_id="test-service",
                conversation_id=f"test-conversation-{i}",
                credit_drop_ns=time.time_ns(),
                warmup=False,
            )
            for i in range(5)
        ]

        # Process credit drops concurrently
        tasks = [worker._process_credit_drop(msg) for msg in credit_drops]
        await asyncio.gather(*tasks)

        # Verify all tasks were processed
        assert worker.total_tasks == 5
        assert worker.completed_tasks == 5
        assert worker.failed_tasks == 0

        # Verify all credit returns were made
        assert worker.credit_return_client.push.call_count == 5
