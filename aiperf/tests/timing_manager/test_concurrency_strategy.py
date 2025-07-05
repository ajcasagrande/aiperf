# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Comprehensive unit tests for the ConcurrencyStrategy class.
"""

import asyncio
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiperf.common.messages import CreditReturnMessage
from aiperf.services.timing_manager.concurrency_strategy import ConcurrencyStrategy


@pytest.mark.asyncio
class TestConcurrencyStrategy:
    """Tests for the ConcurrencyStrategy class."""

    async def test_init_default_values(self, config, mock_credit_manager):
        """Test initialization with default environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)

            assert strategy._total_credits == 1000  # Default value
            assert strategy._concurrency == 10  # Default value
            assert strategy._sent_credits == 0
            assert strategy._completed_credits == 0
            assert strategy.start_time_ns == 0
            assert strategy._semaphore._value == 10
            assert strategy.config == config
            assert strategy.credit_manager == mock_credit_manager

    async def test_init_custom_env_values(self, config, mock_credit_manager):
        """Test initialization with custom environment variables."""
        with patch.dict(
            os.environ, {"AIPERF_TOTAL_REQUESTS": "500", "AIPERF_CONCURRENCY": "20"}
        ):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)

            assert strategy._total_credits == 500
            assert strategy._concurrency == 20
            assert strategy._semaphore._value == 20

    async def test_init_concurrency_limited_by_total_credits(
        self, config, mock_credit_manager
    ):
        """Test that concurrency is limited by total credits."""
        with patch.dict(
            os.environ, {"AIPERF_TOTAL_REQUESTS": "5", "AIPERF_CONCURRENCY": "20"}
        ):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)

            assert strategy._total_credits == 5
            assert strategy._concurrency == 5  # Limited by total credits
            assert strategy._semaphore._value == 5

    @patch("time.time_ns")
    async def test_start_sets_start_time_and_launches_tasks(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test that start() sets start time and launches background tasks."""
        mock_time_ns.return_value = 1000000000

        strategy = ConcurrencyStrategy(config, mock_credit_manager)

        # Mock the background task methods to prevent actual execution
        strategy._progress_report_loop = AsyncMock()
        strategy._credit_drop_loop = AsyncMock()

        await strategy.start()

        assert strategy.start_time_ns == 1000000000
        # Verify tasks were created (we can't easily verify they were started without more complex mocking)
        assert len(strategy.tasks) == 2

    async def test_credit_drop_loop_sends_all_credits(
        self, config, mock_credit_manager
    ):
        """Test that credit drop loop sends all credits respecting concurrency."""
        with patch.dict(
            os.environ, {"AIPERF_TOTAL_REQUESTS": "3", "AIPERF_CONCURRENCY": "2"}
        ):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)

            # Mock the semaphore to avoid deadlock - track acquire calls but don't actually block
            acquire_calls = []

            async def mock_acquire():
                acquire_calls.append(True)
                # Don't actually acquire to avoid deadlock in tests
                return True

            strategy._semaphore.acquire = mock_acquire

            # Run the credit drop loop
            await strategy._credit_drop_loop()

            # wait for the pending tasks to complete before checking the results
            await asyncio.gather(*strategy.tasks)

            # Verify all credits were sent
            assert strategy._sent_credits == 3
            assert len(acquire_calls) == 3
            assert len(mock_credit_manager.dropped_credits) == 3

    async def test_credit_drop_loop_with_zero_credits(
        self, config, mock_credit_manager
    ):
        """Test credit drop loop behavior with zero total credits."""
        with patch.dict(
            os.environ, {"AIPERF_TOTAL_REQUESTS": "0", "AIPERF_CONCURRENCY": "10"}
        ):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)

            await strategy._credit_drop_loop()

            # wait for the pending tasks to complete before checking the results
            await asyncio.gather(*strategy.tasks)

            assert strategy._sent_credits == 0
            assert len(mock_credit_manager.dropped_credits) == 0

    @patch("time.time_ns")
    async def test_on_credit_return_basic_functionality(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test basic credit return processing."""
        mock_time_ns.return_value = 1000000000

        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        strategy.start_time_ns = 1000000000 - 1

        # Mock the semaphore release
        strategy._semaphore.release = MagicMock()

        message = CreditReturnMessage(service_id="test-service")

        await strategy.on_credit_return(message)

        # wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        assert strategy._completed_credits == 1
        strategy._semaphore.release.assert_called_once()

    @patch("time.time_ns")
    async def test_on_credit_return_triggers_credits_complete(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test that credit return triggers credits complete when all credits are returned."""
        mock_time_ns.return_value = 2000000000

        with patch.dict(
            os.environ, {"AIPERF_TOTAL_REQUESTS": "2", "AIPERF_CONCURRENCY": "1"}
        ):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)
            strategy.start_time_ns = 1000000000
            strategy._completed_credits = 1  # One credit already completed

            # Mock the semaphore release
            strategy._semaphore.release = MagicMock()

            message = CreditReturnMessage(service_id="test-service")

            await strategy.on_credit_return(message)

            # wait for the pending tasks to complete before checking the results
            await asyncio.gather(*strategy.tasks)

            assert strategy._completed_credits == 2
            assert len(mock_credit_manager.credits_complete_calls) == 1
            assert mock_credit_manager.credits_complete_calls[0]["cancelled"] is False

    @patch("time.time_ns")
    async def test_on_credit_return_with_debug_logging(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test credit return processing with debug logging enabled."""
        mock_time_ns.return_value = 2000000000

        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        strategy.start_time_ns = 1000000000
        strategy._completed_credits = 0

        # Enable debug logging
        strategy.logger.setLevel(logging.DEBUG)

        # Mock the semaphore release
        strategy._semaphore.release = MagicMock()

        message = CreditReturnMessage(service_id="test-service")

        with patch.object(strategy.logger, "debug") as mock_debug:
            await strategy.on_credit_return(message)

            # Verify debug logging was called
            assert mock_debug.call_count >= 1

    @patch("time.time_ns")
    async def test_full_credit_lifecycle(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test a complete credit lifecycle from start to finish."""
        mock_time_ns.return_value = 1000000000

        with patch.dict(
            os.environ, {"AIPERF_TOTAL_REQUESTS": "2", "AIPERF_CONCURRENCY": "1"}
        ):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)

            # Mock the semaphore to avoid deadlock
            strategy._semaphore.acquire = AsyncMock()

            # Mock the background loops to prevent them from running indefinitely
            strategy._progress_report_loop = AsyncMock()
            strategy._credit_drop_loop = AsyncMock()

            # Start the strategy
            await strategy.start()

            # Simulate credit returns
            message1 = CreditReturnMessage(service_id="test-service")
            message2 = CreditReturnMessage(service_id="test-service")

            await strategy.on_credit_return(message1)
            await strategy.on_credit_return(message2)

            # wait for the pending tasks to complete before checking the results
            await asyncio.gather(*strategy.tasks)

            # Verify final state
            assert strategy._completed_credits == 2
            assert len(mock_credit_manager.credits_complete_calls) == 1
            assert mock_credit_manager.credits_complete_calls[0]["cancelled"] is False

    async def test_inheritance_from_base_classes(self, config, mock_credit_manager):
        """Test that ConcurrencyStrategy properly inherits from base classes."""
        strategy = ConcurrencyStrategy(config, mock_credit_manager)

        # Test CreditIssuingStrategy inheritance
        assert hasattr(strategy, "config")
        assert hasattr(strategy, "credit_manager")
        assert hasattr(strategy, "logger")
        assert callable(strategy.start)
        assert callable(strategy.stop)
        assert callable(strategy.on_credit_return)

        # Test AsyncTaskManagerMixin inheritance
        assert hasattr(strategy, "tasks")
        assert hasattr(strategy, "execute_async")
        assert callable(strategy.cancel_all_tasks)

    async def test_semaphore_behavior_with_concurrent_credits(
        self, config, mock_credit_manager
    ):
        """Test semaphore behavior with concurrent credit operations."""
        with patch.dict(
            os.environ, {"AIPERF_TOTAL_REQUESTS": "5", "AIPERF_CONCURRENCY": "2"}
        ):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)

            # Verify initial semaphore value
            assert strategy._semaphore._value == 2

            # Simulate acquiring permits
            await strategy._semaphore.acquire()
            assert strategy._semaphore._value == 1

            await strategy._semaphore.acquire()
            assert strategy._semaphore._value == 0

            # Simulate credit return releasing permits
            message = CreditReturnMessage(service_id="test-service")
            await strategy.on_credit_return(message)

            assert strategy._semaphore._value == 1

    async def test_credit_drop_and_return_flow(self, config, mock_credit_manager):
        """Test coordinated credit drop and return flow without deadlocks."""
        with patch.dict(
            os.environ, {"AIPERF_TOTAL_REQUESTS": "3", "AIPERF_CONCURRENCY": "2"}
        ):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)

            # Track semaphore operations
            acquire_count = 0
            release_count = 0

            async def mock_acquire():
                nonlocal acquire_count
                acquire_count += 1
                # Don't block - just track the calls
                return True

            def mock_release():
                nonlocal release_count
                release_count += 1
                return None

            strategy._semaphore.acquire = mock_acquire
            strategy._semaphore.release = mock_release

            # Run credit drop loop
            await strategy._credit_drop_loop()

            # wait for the pending tasks to complete before checking the results
            await asyncio.gather(*strategy.tasks)

            # Verify credits were sent
            assert strategy._sent_credits == 3
            assert acquire_count == 3
            assert len(mock_credit_manager.dropped_credits) == 3

            # Simulate credit returns
            message1 = CreditReturnMessage(service_id="test-service")
            message2 = CreditReturnMessage(service_id="test-service")
            message3 = CreditReturnMessage(service_id="test-service")

            await strategy.on_credit_return(message1)
            await strategy.on_credit_return(message2)
            await strategy.on_credit_return(message3)

            # wait for the pending tasks to complete before checking the results
            await asyncio.gather(*strategy.tasks)

            # Verify credits were returned
            assert strategy._completed_credits == 3
            assert release_count == 3
            assert len(mock_credit_manager.credits_complete_calls) == 1

    async def test_environment_variable_parsing(self, config, mock_credit_manager):
        """Test parsing of environment variables with edge cases."""
        # Test with string values that need conversion
        with patch.dict(
            os.environ, {"AIPERF_TOTAL_REQUESTS": "100", "AIPERF_CONCURRENCY": "50"}
        ):
            strategy = ConcurrencyStrategy(config, mock_credit_manager)

            assert isinstance(strategy._total_credits, int)
            assert isinstance(strategy._concurrency, int)
            assert strategy._total_credits == 100
            assert strategy._concurrency == 50

    @patch("time.time_ns")
    async def test_rate_calculation_in_debug_logs(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test that rate calculation in debug logs works correctly."""
        # Set up time progression
        mock_time_ns.side_effect = [
            1000000000,
            2000000000,
            3000000000,
        ]  # 1 second difference

        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        strategy.start_time_ns = 1000000000
        strategy._completed_credits = 0
        strategy._total_credits = 100

        # Enable debug logging
        strategy.logger.setLevel(logging.DEBUG)

        # Mock semaphore release
        strategy._semaphore.release = MagicMock()

        message = CreditReturnMessage(service_id="test-service")

        with patch.object(strategy.logger, "debug") as mock_debug:
            await strategy.on_credit_return(message)

            # Verify debug logging includes rate calculation
            mock_debug.assert_called()
            # Check that the debug message contains rate information
            debug_calls = [
                call for call in mock_debug.call_args_list if "requests/s" in str(call)
            ]
            assert len(debug_calls) > 0
