# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Comprehensive unit tests for the ConcurrencyStrategy class.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.models import CreditReturnMessage
from aiperf.services.timing_manager.concurrency_strategy import (
    ConcurrencyStrategy,
)
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.tests.timing_manager.conftest import MockCreditManager
from aiperf.tests.utils.async_test_utils import MockSemaphore


def seconds_to_ns(seconds: float) -> int:
    """Convert seconds to nanoseconds."""
    return int(seconds * NANOS_PER_SECOND)


def create_concurrency_strategy(
    config: TimingManagerConfig,
    mock_credit_manager: MockCreditManager,
    concurrency: int,
    request_count: int,
    auto_return: bool = True,
) -> ConcurrencyStrategy:
    """Create a ConcurrencyStrategy instance."""
    config.concurrency = concurrency
    config.request_count = request_count
    mock_credit_manager.auto_credit_return = auto_return
    strategy = ConcurrencyStrategy(config, mock_credit_manager)
    mock_credit_manager.credit_strategy = strategy
    strategy.logger.info = MagicMock()
    strategy.logger.debug = MagicMock()
    return strategy


@pytest.mark.asyncio
class TestConcurrencyStrategy:
    """Tests for the ConcurrencyStrategy class."""

    async def test_start_sets_start_time_and_launches_tasks(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test that start() sets start time and launches background tasks."""
        mock_time_ns.return_value = seconds_to_ns(10)

        strategy = create_concurrency_strategy(
            config, mock_credit_manager, concurrency=1, request_count=1
        )

        strategy._progress_report_loop = AsyncMock()

        await strategy.start()

        # Wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        assert strategy.active_phase.start_time_ns == seconds_to_ns(10)

    async def test_credit_drop_loop_sends_all_credits(
        self, config, mock_credit_manager, patch_semaphore
    ):
        """Test that credit drop loop sends all credits respecting concurrency."""

        strategy = create_concurrency_strategy(
            config, mock_credit_manager, concurrency=2, request_count=3
        )

        # Run the credit drop loop
        await strategy._execute_phase(strategy.profiling)

        # Wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        # Verify all credits were sent
        assert isinstance(strategy._semaphore, MockSemaphore)
        assert strategy.profiling.sent_credits == 3
        assert strategy._semaphore.acquire_count == 3
        assert strategy._semaphore.wait_count == 1
        assert len(mock_credit_manager.dropped_credits) == 3

    async def test_credit_drop_loop_with_zero_credits(
        self, config, mock_credit_manager, patch_semaphore
    ):
        """Test credit drop loop behavior with zero total credits."""
        strategy = create_concurrency_strategy(
            config, mock_credit_manager, concurrency=10, request_count=0
        )

        await strategy._execute_phase(strategy.profiling)

        # Wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        assert strategy.profiling.sent_credits == 0
        assert len(mock_credit_manager.dropped_credits) == 0

    async def test_on_credit_return_basic_functionality(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test basic credit return processing."""
        mock_time_ns.return_value = seconds_to_ns(2)

        strategy = create_concurrency_strategy(
            config, mock_credit_manager, concurrency=1, request_count=1
        )
        strategy.profiling.start_time_ns = seconds_to_ns(1)

        message = CreditReturnMessage(service_id="test-service")

        await strategy._on_credit_return(message)

        # Wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        assert strategy.profiling.completed_credits == 1
        assert isinstance(strategy._semaphore, MockSemaphore)
        assert strategy._semaphore.release_count == 1

    async def test_on_credit_return_triggers_credits_complete(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test that credit return triggers credits complete when all credits are returned."""
        mock_time_ns.return_value = seconds_to_ns(2)

        strategy = create_concurrency_strategy(
            config, mock_credit_manager, concurrency=1, request_count=2
        )

        strategy.profiling.start_time_ns = seconds_to_ns(1)
        strategy.profiling.completed_credits = 1  # One credit already completed

        message = CreditReturnMessage(service_id="test-service")

        await strategy._on_credit_return(message)

        # Wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        assert strategy.profiling.completed_credits == 2
        assert len(mock_credit_manager.credits_complete_calls) == 1
        assert isinstance(strategy._semaphore, MockSemaphore)
        assert strategy._semaphore.release_count == 1
        assert mock_credit_manager.credits_complete_calls[0]["cancelled"] is False

    async def test_full_credit_lifecycle(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test a complete credit lifecycle from start to finish."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_concurrency_strategy(
            config, mock_credit_manager, concurrency=1, request_count=2
        )

        # Mock the background loops to prevent them from running indefinitely
        strategy._progress_report_loop = AsyncMock()
        strategy._execute_phase = AsyncMock()

        # Start the strategy
        await strategy.start()

        # Simulate credit returns
        message1 = CreditReturnMessage(service_id="test-service")
        message2 = CreditReturnMessage(service_id="test-service")

        await strategy._on_credit_return(message1)
        await strategy._on_credit_return(message2)

        # Wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        # Verify final state
        assert isinstance(strategy._semaphore, MockSemaphore)
        await strategy._semaphore.cancel_tasks()
        assert strategy.profiling.completed_credits == 2
        assert len(mock_credit_manager.credits_complete_calls) == 1
        assert strategy._semaphore.release_count == 2
        assert mock_credit_manager.credits_complete_calls[0]["cancelled"] is False

    async def test_credit_drop_and_return_flow(
        self, config, mock_credit_manager, patch_semaphore
    ):
        """Test coordinated credit drop and return flow without deadlocks."""
        strategy = create_concurrency_strategy(
            config,
            mock_credit_manager,
            concurrency=2,
            request_count=3,
            auto_return=False,
        )

        # Run credit drop loop
        await strategy._execute_phase(strategy.profiling)

        # Wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        # Verify credits were sent
        assert isinstance(strategy._semaphore, MockSemaphore)
        await strategy._semaphore.cancel_tasks()
        assert strategy.profiling.sent_credits == 3
        assert strategy._semaphore.acquire_count == 3
        assert len(mock_credit_manager.dropped_credits) == 3

        # Concurrency is 2, so we should have 1 wait
        assert strategy._semaphore.wait_count == 1

        # Simulate credit returns
        message1 = CreditReturnMessage(service_id="test-service")
        message2 = CreditReturnMessage(service_id="test-service")
        message3 = CreditReturnMessage(service_id="test-service")

        await strategy._on_credit_return(message1)
        await strategy._on_credit_return(message2)
        await strategy._on_credit_return(message3)

        # Wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        # Verify credits were returned
        assert isinstance(strategy._semaphore, MockSemaphore)
        assert strategy.profiling.completed_credits == 3
        await strategy._semaphore.cancel_tasks()
        assert strategy._semaphore.release_count == 3
        assert len(mock_credit_manager.credits_complete_calls) == 1
        assert strategy._semaphore.acquire_count == 3

    async def test_credit_drop_semaphore_wait_count(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test that credit drop loop sends all credits with zero concurrency."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_concurrency_strategy(
            config, mock_credit_manager, concurrency=10, request_count=100
        )
        strategy._report_progress = AsyncMock()

        # Run the credit drop loop
        await strategy._execute_phase(strategy.profiling)

        # Wait for the pending tasks to complete before checking the results
        await asyncio.gather(*strategy.tasks)

        # Verify all credits were sent
        assert isinstance(strategy._semaphore, MockSemaphore)
        await strategy._semaphore.cancel_tasks()
        assert strategy._semaphore.initial_value == 10
        assert strategy.profiling.sent_credits == 100
        assert strategy._semaphore.acquire_count == 100
        assert strategy._semaphore.wait_count == 90
        assert len(mock_credit_manager.dropped_credits) == 100


@pytest.mark.asyncio
class TestConcurrencyStrategyWarmup:
    """Tests for the ConcurrencyStrategy warmup functionality."""

    async def test_warmup_phase_initialization(
        self, config, mock_credit_manager, patch_semaphore
    ):
        """Test that warmup phase is properly initialized when warmup_request_count > 0."""
        strategy = create_concurrency_strategy(
            config, mock_credit_manager, concurrency=2, request_count=5
        )
        config.warmup_request_count = 3

        # Reinitialize strategy with warmup
        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        mock_credit_manager.credit_strategy = strategy
        strategy.logger.info = MagicMock()
        strategy.logger.debug = MagicMock()

        assert strategy.warmup is not None
        assert strategy.warmup.total_credits == 3
        assert strategy.warmup.warmup is True
        assert strategy.profiling.total_credits == 5
        assert strategy.profiling.warmup is False
        assert strategy.active_phase is strategy.warmup

    async def test_warmup_phase_not_created_when_zero_requests(
        self, config, mock_credit_manager, patch_semaphore
    ):
        """Test that warmup phase is not created when warmup_request_count is 0."""
        strategy = create_concurrency_strategy(
            config, mock_credit_manager, concurrency=2, request_count=5
        )
        config.warmup_request_count = 0

        # Reinitialize strategy without warmup
        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        mock_credit_manager.credit_strategy = strategy
        strategy.logger.info = MagicMock()
        strategy.logger.debug = MagicMock()

        assert strategy.warmup is None
        assert strategy.active_phase is strategy.profiling

    async def test_warmup_phase_execution(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test that warmup phase executes correctly and sends warmup credits."""
        mock_time_ns.return_value = seconds_to_ns(1)
        config.warmup_request_count = 3

        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        mock_credit_manager.credit_strategy = strategy
        strategy.logger.info = MagicMock()
        strategy.logger.debug = MagicMock()

        # Execute warmup phase
        await strategy._execute_phase(strategy.warmup)

        # Wait for the pending tasks to complete
        await asyncio.gather(*strategy.tasks)

        # Verify warmup credits were sent
        assert strategy.warmup.sent_credits == 3
        assert len(mock_credit_manager.dropped_credits) == 3

        # Verify all dropped credits have warmup=True
        for credit in mock_credit_manager.dropped_credits:
            assert credit["warmup"] is True

    async def test_warmup_to_profiling_phase_transition(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test transition from warmup to profiling phase."""
        mock_time_ns.return_value = seconds_to_ns(1)
        config.warmup_request_count = 2
        config.request_count = 3

        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        mock_credit_manager.credit_strategy = strategy
        strategy.logger.info = MagicMock()
        strategy.logger.debug = MagicMock()

        # Mock the progress report loop to prevent it from running
        strategy._progress_report_loop = AsyncMock()

        # Start the strategy (this will execute both warmup and profiling)
        await strategy.start()

        # Simulate warmup completion
        await strategy.warmup.completed_event.wait()

        # Simulate credit returns for warmup phase
        for _ in range(2):
            await strategy._on_credit_return(
                CreditReturnMessage(service_id="test-service")
            )

        # Wait for tasks to complete
        await asyncio.gather(*strategy.tasks)

        # Verify warmup phase is complete
        assert strategy.warmup.completed_credits == 2
        assert len(mock_credit_manager.credits_complete_calls) == 1
        assert mock_credit_manager.credits_complete_calls[0]["warmup"] is True

    async def test_warmup_phase_credit_returns(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test credit return handling during warmup phase."""
        mock_time_ns.return_value = seconds_to_ns(1)
        config.warmup_request_count = 2

        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        mock_credit_manager.credit_strategy = strategy
        strategy.logger.info = MagicMock()
        strategy.logger.debug = MagicMock()

        # Set warmup as active phase
        strategy.active_phase = strategy.warmup
        strategy.warmup.start_time_ns = seconds_to_ns(1)

        # Process credit returns
        await strategy._on_credit_return(CreditReturnMessage(service_id="test-service"))
        await strategy._on_credit_return(CreditReturnMessage(service_id="test-service"))

        # Wait for tasks to complete
        await asyncio.gather(*strategy.tasks)

        # Verify warmup completion
        assert strategy.warmup.completed_credits == 2
        assert len(mock_credit_manager.credits_complete_calls) == 1
        assert mock_credit_manager.credits_complete_calls[0]["warmup"] is True
        assert mock_credit_manager.credits_complete_calls[0]["cancelled"] is False

    async def test_warmup_phase_concurrency_limiting(
        self, config, mock_credit_manager, patch_semaphore
    ):
        """Test that warmup phase respects concurrency limits."""
        config.warmup_request_count = 5
        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        mock_credit_manager.credit_strategy = strategy
        strategy.logger.info = MagicMock()
        strategy.logger.debug = MagicMock()

        # Execute warmup phase
        await strategy._execute_phase(strategy.warmup)

        # Wait for tasks to complete
        await asyncio.gather(*strategy.tasks)

        # Verify semaphore usage
        assert isinstance(strategy._semaphore, MockSemaphore)
        await strategy._semaphore.cancel_tasks()
        assert strategy._semaphore.acquire_count == 5
        assert strategy.warmup.sent_credits == 5

    async def test_warmup_phase_progress_reporting(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test that progress is reported correctly during warmup phase."""
        mock_time_ns.return_value = seconds_to_ns(1)
        config.warmup_request_count = 3

        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        mock_credit_manager.credit_strategy = strategy
        strategy.logger.info = MagicMock()
        strategy.logger.debug = MagicMock()

        # Set warmup as active phase
        strategy.active_phase = strategy.warmup
        strategy.warmup.start_time_ns = seconds_to_ns(1)

        # Report progress
        await strategy._report_progress()

        # Verify progress was reported for warmup
        assert len(mock_credit_manager.progress_calls) == 1
        progress_call = mock_credit_manager.progress_calls[0]
        assert progress_call["warmup"] is True
        assert progress_call["total"] == 3

    async def test_profiling_phase_after_warmup(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test that profiling phase starts correctly after warmup completion."""
        mock_time_ns.return_value = seconds_to_ns(1)
        config.warmup_request_count = 1
        config.request_count = 2

        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        mock_credit_manager.credit_strategy = strategy
        strategy.logger.info = MagicMock()
        strategy.logger.debug = MagicMock()

        # Complete warmup phase first
        await strategy._execute_phase(strategy.warmup)

        # Complete warmup by processing returns
        await strategy._on_credit_return(CreditReturnMessage(service_id="test-service"))

        # Wait for warmup completion
        await asyncio.gather(*strategy.tasks)

        # Verify warmup is complete
        assert strategy.warmup.completed_credits == 1

        # Execute profiling phase
        await strategy._execute_phase(strategy.profiling)

        # Wait for profiling tasks
        await asyncio.gather(*strategy.tasks)

        # Verify profiling credits were sent (not warmup)
        profiling_credits = [
            credit
            for credit in mock_credit_manager.dropped_credits
            if not credit["warmup"]
        ]
        assert len(profiling_credits) == 2
        assert strategy.profiling.sent_credits == 2

    async def test_full_warmup_and_profiling_lifecycle(
        self, mock_time_ns, config, mock_credit_manager, patch_semaphore
    ):
        """Test complete lifecycle from warmup through profiling."""
        mock_time_ns.return_value = seconds_to_ns(1)
        config.warmup_request_count = 2
        config.request_count = 3

        strategy = ConcurrencyStrategy(config, mock_credit_manager)
        mock_credit_manager.credit_strategy = strategy
        strategy.logger.info = MagicMock()
        strategy.logger.debug = MagicMock()

        # Mock progress report loop to prevent interference
        strategy._progress_report_loop = AsyncMock()

        # Start strategy
        await strategy.start()

        # Process warmup credit returns
        await strategy._on_credit_return(CreditReturnMessage(service_id="test-service"))
        await strategy._on_credit_return(CreditReturnMessage(service_id="test-service"))

        # Process profiling credit returns
        await strategy._on_credit_return(CreditReturnMessage(service_id="test-service"))
        await strategy._on_credit_return(CreditReturnMessage(service_id="test-service"))
        await strategy._on_credit_return(CreditReturnMessage(service_id="test-service"))

        # Wait for all tasks to complete
        await asyncio.gather(*strategy.tasks)

        # Verify final state
        assert isinstance(strategy._semaphore, MockSemaphore)
        await strategy._semaphore.cancel_tasks()

        # Check that both warmup and profiling completed
        assert len(mock_credit_manager.credits_complete_calls) == 2
        warmup_complete = next(
            call
            for call in mock_credit_manager.credits_complete_calls
            if call["warmup"]
        )
        profiling_complete = next(
            call
            for call in mock_credit_manager.credits_complete_calls
            if not call["warmup"]
        )

        assert warmup_complete["cancelled"] is False
        assert profiling_complete["cancelled"] is False

        # Verify correct number of credits
        warmup_credits = [
            credit for credit in mock_credit_manager.dropped_credits if credit["warmup"]
        ]
        profiling_credits = [
            credit
            for credit in mock_credit_manager.dropped_credits
            if not credit["warmup"]
        ]

        assert len(warmup_credits) == 2
        assert len(profiling_credits) == 3
        assert strategy.warmup.completed_credits == 2
        assert strategy.profiling.completed_credits == 3
