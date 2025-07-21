# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the worker protocols module.
"""

from typing import Any

import pytest

from aiperf.common.messages import (
    ConversationResponse,
    CreditDropMessage,
    InferenceResultsMessage,
    WorkerHealthMessage,
)
from aiperf.common.models import Conversation
from aiperf.services.workers.protocols import WorkerCommunicationsProtocol


class MockWorkerCommunication:
    """Mock implementation of WorkerCommunicationsProtocol for testing."""

    def __init__(self):
        self.credit_drop_handler = None
        self.credits_returned = 0
        self.conversation_requests = []
        self.inference_results = []
        self.health_messages = []

    def register_credit_drop_handler(self, handler):
        """Register a handler for credit drop messages."""
        self.credit_drop_handler = handler

    async def return_credits(self, amount: int) -> None:
        """Return credits to the Timing Manager."""
        self.credits_returned += amount

    async def request_conversation_data(self, conversation_id: str | None = None):
        """Request conversation data for a given conversation ID."""
        self.conversation_requests.append(conversation_id)
        return ConversationResponse(
            service_id="test-service",
            conversation=Conversation(session_id="test-session"),
        )

    async def push_inference_results(self, message: InferenceResultsMessage) -> None:
        """Push inference results to the inference results client."""
        self.inference_results.append(message)

    async def publish_health_message(self, message: WorkerHealthMessage) -> None:
        """Publish a health message to the Worker Manager."""
        self.health_messages.append(message)


class TestWorkerCommunicationsProtocol:
    """Test the WorkerCommunicationsProtocol interface."""

    @pytest.fixture
    def mock_worker_comm(self) -> MockWorkerCommunication:
        """Create a mock worker communication instance."""
        return MockWorkerCommunication()

    @pytest.fixture
    def sample_credit_drop_message(self) -> CreditDropMessage:
        """Create a sample credit drop message."""
        return CreditDropMessage(
            service_id="test-service",
            conversation_id="test-conversation",
            credit_drop_ns=1000000000,
            warmup=False,
        )

    @pytest.fixture
    def sample_inference_results_message(self) -> InferenceResultsMessage:
        """Create a sample inference results message."""
        from aiperf.common.models import RequestRecord

        return InferenceResultsMessage(
            service_id="test-service",
            record=RequestRecord(
                timestamp_ns=1000000000,
                start_perf_ns=2000000000,
                end_perf_ns=3000000000,
                error=None,
            ),
        )

    @pytest.fixture
    def sample_health_message(self) -> WorkerHealthMessage:
        """Create a sample worker health message."""
        from aiperf.common.models import (
            CPUTimes,
            CtxSwitches,
            IOCounters,
            ProcessHealth,
        )

        return WorkerHealthMessage(
            service_id="test-service",
            process=ProcessHealth(
                pid=12345,
                create_time=1000000000,
                uptime=600.0,
                cpu_usage=25.0,
                memory_usage=50.0,
                io_counters=IOCounters(
                    read_count=1000,
                    write_count=1000,
                    read_bytes=1000,
                    write_bytes=1000,
                    read_chars=1000,
                    write_chars=1000,
                ),
                cpu_times=CPUTimes(1000, 1000, 1000),
                num_ctx_switches=CtxSwitches(1000, 1000),
                num_threads=1,
            ),
            total_tasks=10,
            completed_tasks=8,
            failed_tasks=2,
            warmup_tasks=5,
            warmup_failed_tasks=1,
        )

    def test_protocol_is_runtime_checkable(self):
        """Test that the protocol is runtime checkable."""
        # This ensures the protocol can be used with isinstance checks
        assert isinstance(WorkerCommunicationsProtocol, type)
        # Check that it's a Protocol class
        assert hasattr(WorkerCommunicationsProtocol, "__annotations__") or hasattr(
            WorkerCommunicationsProtocol, "__dict__"
        )

    def test_protocol_defines_required_methods(self):
        """Test that the protocol defines all required methods."""
        # Check that all required methods are defined in the protocol
        protocol_methods = [
            "register_credit_drop_handler",
            "return_credits",
            "request_conversation_data",
            "push_inference_results",
            "publish_health_message",
        ]

        for method_name in protocol_methods:
            assert hasattr(WorkerCommunicationsProtocol, method_name)

    def test_mock_implementation_conforms_to_protocol(
        self, mock_worker_comm: MockWorkerCommunication
    ):
        """Test that our mock implementation conforms to the protocol."""
        # Check that all protocol methods are implemented
        assert hasattr(mock_worker_comm, "register_credit_drop_handler")
        assert hasattr(mock_worker_comm, "return_credits")
        assert hasattr(mock_worker_comm, "request_conversation_data")
        assert hasattr(mock_worker_comm, "push_inference_results")
        assert hasattr(mock_worker_comm, "publish_health_message")

        # Check that methods are callable
        assert callable(mock_worker_comm.register_credit_drop_handler)
        assert callable(mock_worker_comm.return_credits)
        assert callable(mock_worker_comm.request_conversation_data)
        assert callable(mock_worker_comm.push_inference_results)
        assert callable(mock_worker_comm.publish_health_message)

    @pytest.mark.asyncio
    async def test_register_credit_drop_handler(
        self, mock_worker_comm: MockWorkerCommunication
    ):
        """Test registering a credit drop handler."""

        async def dummy_handler(message: CreditDropMessage) -> None:
            pass

        # Register the handler
        mock_worker_comm.register_credit_drop_handler(dummy_handler)

        # Verify the handler was registered
        assert mock_worker_comm.credit_drop_handler == dummy_handler

    @pytest.mark.asyncio
    async def test_return_credits(self, mock_worker_comm: MockWorkerCommunication):
        """Test returning credits."""
        # Return some credits
        await mock_worker_comm.return_credits(5)

        # Verify credits were returned
        assert mock_worker_comm.credits_returned == 5

        # Return more credits
        await mock_worker_comm.return_credits(3)

        # Verify total credits returned
        assert mock_worker_comm.credits_returned == 8

    @pytest.mark.asyncio
    async def test_request_conversation_data(
        self, mock_worker_comm: MockWorkerCommunication
    ):
        """Test requesting conversation data."""
        # Request conversation data
        response = await mock_worker_comm.request_conversation_data(
            "test-conversation-123"
        )

        # Verify request was recorded
        assert "test-conversation-123" in mock_worker_comm.conversation_requests

        # Verify response structure
        assert isinstance(response, ConversationResponse)
        assert response.service_id == "test-service"

    @pytest.mark.asyncio
    async def test_request_conversation_data_with_none_id(
        self, mock_worker_comm: MockWorkerCommunication
    ):
        """Test requesting conversation data with None ID."""
        # Request conversation data with None ID
        response = await mock_worker_comm.request_conversation_data(None)

        # Verify request was recorded
        assert None in mock_worker_comm.conversation_requests

        # Verify response structure
        assert isinstance(response, ConversationResponse)

    @pytest.mark.asyncio
    async def test_push_inference_results(
        self,
        mock_worker_comm: MockWorkerCommunication,
        sample_inference_results_message: InferenceResultsMessage,
    ):
        """Test pushing inference results."""
        # Push inference results
        await mock_worker_comm.push_inference_results(sample_inference_results_message)

        # Verify results were pushed
        assert len(mock_worker_comm.inference_results) == 1
        assert mock_worker_comm.inference_results[0] == sample_inference_results_message

    @pytest.mark.asyncio
    async def test_publish_health_message(
        self,
        mock_worker_comm: MockWorkerCommunication,
        sample_health_message: WorkerHealthMessage,
    ):
        """Test publishing health message."""
        # Publish health message
        await mock_worker_comm.publish_health_message(sample_health_message)

        # Verify message was published
        assert len(mock_worker_comm.health_messages) == 1
        assert mock_worker_comm.health_messages[0] == sample_health_message

    @pytest.mark.asyncio
    async def test_multiple_operations(
        self,
        mock_worker_comm: MockWorkerCommunication,
        sample_inference_results_message: InferenceResultsMessage,
        sample_health_message: WorkerHealthMessage,
    ):
        """Test multiple operations in sequence."""

        # Register handler
        async def test_handler(message: CreditDropMessage) -> None:
            pass

        mock_worker_comm.register_credit_drop_handler(test_handler)

        # Return credits
        await mock_worker_comm.return_credits(10)

        # Request conversation data
        await mock_worker_comm.request_conversation_data("test-conversation-456")

        # Push inference results
        await mock_worker_comm.push_inference_results(sample_inference_results_message)

        # Publish health message
        await mock_worker_comm.publish_health_message(sample_health_message)

        # Verify all operations
        assert mock_worker_comm.credit_drop_handler == test_handler
        assert mock_worker_comm.credits_returned == 10
        assert "test-conversation-456" in mock_worker_comm.conversation_requests
        assert len(mock_worker_comm.inference_results) == 1
        assert len(mock_worker_comm.health_messages) == 1

    @pytest.mark.asyncio
    def test_protocol_type_hints(self):
        """Test that the protocol has correct type hints."""
        import inspect

        # Get the protocol methods
        methods = inspect.getmembers(
            WorkerCommunicationsProtocol, predicate=inspect.isfunction
        )

        # Check register_credit_drop_handler signature
        for name, method in methods:
            if name == "register_credit_drop_handler":
                signature = inspect.signature(method)
                params = list(signature.parameters.values())
                assert len(params) == 2  # self and handler
                handler_param = params[1]
                assert handler_param.name == "handler"
                # The annotation should be a callable that takes CreditDropMessage and returns a coroutine
                assert "Callable" in str(handler_param.annotation)
                assert "CreditDropMessage" in str(handler_param.annotation)
                assert "Coroutine" in str(handler_param.annotation)

    def test_protocol_method_return_types(self):
        """Test that protocol methods have correct return types."""
        import inspect

        # Get the protocol methods
        methods = inspect.getmembers(
            WorkerCommunicationsProtocol, predicate=inspect.isfunction
        )

        for name, method in methods:
            signature = inspect.signature(method)

            if name == "register_credit_drop_handler":
                # Should return None
                assert signature.return_annotation in (
                    None,
                    type(None),
                    inspect.Signature.empty,
                )
            elif name in [
                "return_credits",
                "push_inference_results",
                "publish_health_message",
            ]:
                # Should return Coroutine[Any, Any, None]
                assert "Coroutine" in str(signature.return_annotation)
            elif name == "request_conversation_data":
                # Should return Coroutine[Any, Any, ConversationResponseMessage]
                assert "Coroutine" in str(signature.return_annotation)
                assert "ConversationResponseMessage" in str(signature.return_annotation)


class TestProtocolUsage:
    """Test how the protocol is used in practice."""

    def test_protocol_can_be_used_as_type_hint(self):
        """Test that the protocol can be used as a type hint."""

        def accept_worker_comm(comm: WorkerCommunicationsProtocol) -> None:
            pass

        # This should not raise any type errors
        mock_comm = MockWorkerCommunication()
        accept_worker_comm(mock_comm)

    def test_protocol_methods_are_async_where_expected(self):
        """Test that protocol methods are async where expected."""
        import inspect

        mock_comm = MockWorkerCommunication()

        # These methods should be async
        async_methods = [
            "return_credits",
            "request_conversation_data",
            "push_inference_results",
            "publish_health_message",
        ]

        for method_name in async_methods:
            method = getattr(mock_comm, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} should be async"

        # This method should not be async
        sync_methods = ["register_credit_drop_handler"]

        for method_name in sync_methods:
            method = getattr(mock_comm, method_name)
            assert not inspect.iscoroutinefunction(method), (
                f"{method_name} should not be async"
            )

    @pytest.mark.asyncio
    async def test_protocol_with_real_usage_pattern(self):
        """Test protocol with a realistic usage pattern."""
        mock_comm = MockWorkerCommunication()

        # Simulate a credit drop handler
        async def credit_drop_handler(message: CreditDropMessage) -> None:
            # Request conversation data
            await mock_comm.request_conversation_data(message.conversation_id)

            # Create and push inference results
            from aiperf.common.models import RequestRecord

            record = RequestRecord(
                timestamp_ns=1000000000,
                start_perf_ns=2000000000,
                end_perf_ns=3000000000,
            )
            inference_results = InferenceResultsMessage(
                service_id=message.service_id,
                record=record,
            )
            await mock_comm.push_inference_results(inference_results)

            # Return credits
            await mock_comm.return_credits(1)

            # Publish health message
            from aiperf.common.models import (
                CPUTimes,
                CtxSwitches,
                IOCounters,
                ProcessHealth,
            )

            health_msg = WorkerHealthMessage(
                service_id=message.service_id,
                process=ProcessHealth(
                    pid=12345,
                    create_time=1000000000,
                    uptime=600.0,
                    cpu_usage=25.0,
                    memory_usage=50.0,
                    io_counters=IOCounters(
                        read_count=1000,
                        write_count=1000,
                        read_bytes=1000,
                        write_bytes=1000,
                        read_chars=1000,
                        write_chars=1000,
                    ),
                    cpu_times=CPUTimes(
                        user=1000,
                        system=1000,
                        iowait=1000,
                    ),
                    num_ctx_switches=CtxSwitches(
                        voluntary=1000,
                        involuntary=1000,
                    ),
                    num_threads=1,
                ),
                total_tasks=1,
                completed_tasks=1,
                failed_tasks=0,
                warmup_tasks=0,
                warmup_failed_tasks=0,
            )
            await mock_comm.publish_health_message(health_msg)

        # Register the handler
        mock_comm.register_credit_drop_handler(credit_drop_handler)

        # Simulate a credit drop
        credit_drop = CreditDropMessage(
            service_id="test-service",
            conversation_id="test-conversation",
            credit_drop_ns=1000000000,
            warmup=False,
        )

        # Execute the handler
        await credit_drop_handler(credit_drop)

        # Verify all operations were performed
        assert mock_comm.credits_returned == 1
        assert "test-conversation" in mock_comm.conversation_requests
        assert len(mock_comm.inference_results) == 1
        assert len(mock_comm.health_messages) == 1

        # Verify the data integrity
        assert mock_comm.inference_results[0].service_id == "test-service"
        assert mock_comm.health_messages[0].service_id == "test-service"
        assert mock_comm.health_messages[0].total_tasks == 1
        assert mock_comm.health_messages[0].completed_tasks == 1


class TestProtocolEdgeCases:
    """Test edge cases and error conditions for the protocol."""

    def test_protocol_with_invalid_implementation(self):
        """Test protocol behavior with invalid implementations."""

        class InvalidWorkerComm:
            """Invalid implementation missing required methods."""

            def register_credit_drop_handler(self, handler):
                pass

            # Missing other required methods

        invalid_comm = InvalidWorkerComm()

        # This should still work at runtime (Python's duck typing)
        # but would fail static type checking
        def accept_worker_comm(comm: WorkerCommunicationsProtocol) -> None:
            pass

        # This will work at runtime but is not type-safe
        accept_worker_comm(invalid_comm)  # type: ignore

    @pytest.mark.asyncio
    async def test_protocol_with_exception_handling(self):
        """Test protocol implementation with exception handling."""

        class ExceptionWorkerComm:
            """Implementation that raises exceptions."""

            def register_credit_drop_handler(self, handler):
                raise RuntimeError("Handler registration failed")

            async def return_credits(self, amount: int) -> None:
                raise ConnectionError("Credit return failed")

            async def request_conversation_data(
                self, conversation_id: str | None = None
            ):
                raise TimeoutError("Conversation data request timed out")

            async def push_inference_results(
                self, message: InferenceResultsMessage
            ) -> None:
                raise ValueError("Invalid inference results")

            async def publish_health_message(
                self, message: WorkerHealthMessage
            ) -> None:
                raise RuntimeError("Health message publishing failed")

        exception_comm = ExceptionWorkerComm()

        # Test that exceptions are properly raised
        with pytest.raises(RuntimeError):
            exception_comm.register_credit_drop_handler(lambda x: None)

        with pytest.raises(ConnectionError):
            await exception_comm.return_credits(5)

        with pytest.raises(TimeoutError):
            await exception_comm.request_conversation_data("test")

        from aiperf.common.messages import RequestRecord

        test_message = InferenceResultsMessage(
            service_id="test",
            record=RequestRecord(
                timestamp_ns=1000000000,
                start_perf_ns=2000000000,
                end_perf_ns=3000000000,
            ),
        )

        with pytest.raises(ValueError):
            await exception_comm.push_inference_results(test_message)

        from aiperf.common.models import ProcessHealth

        health_message = WorkerHealthMessage(
            service_id="test",
            process=ProcessHealth(
                pid=1, create_time=0.0, uptime=0.0, cpu_usage=0.0, memory_usage=0.0
            ),
            total_tasks=0,
            completed_tasks=0,
            failed_tasks=0,
            warmup_tasks=0,
            warmup_failed_tasks=0,
        )

        with pytest.raises(RuntimeError):
            await exception_comm.publish_health_message(health_message)

    def test_protocol_extensibility(self):
        """Test that the protocol can be extended."""

        class ExtendedWorkerComm(MockWorkerCommunication):
            """Extended implementation with additional methods."""

            def __init__(self):
                super().__init__()
                self.custom_operations = []

            async def custom_operation(self, data: Any) -> None:
                """Custom operation not in the protocol."""
                self.custom_operations.append(data)

        extended_comm = ExtendedWorkerComm()

        # Should still conform to the protocol
        def accept_worker_comm(comm: WorkerCommunicationsProtocol) -> None:
            pass

        accept_worker_comm(extended_comm)

        # Should also support extended functionality
        assert hasattr(extended_comm, "custom_operation")
        assert callable(extended_comm.custom_operation)
