# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Comprehensive unit tests for the RequestRateStrategy class.
"""

import asyncio
import contextlib
import math
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import RequestRateMode
from aiperf.common.exceptions import InvalidStateError
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.services.timing_manager.request_rate_strategy import RequestRateStrategy
from tests.timing_manager.conftest import MockCreditManager
from tests.utils.async_test_utils import real_sleep


def seconds_to_ns(seconds: float) -> int:
    """Convert seconds to nanoseconds."""
    return int(seconds * NANOS_PER_SECOND)


def create_yielding_sleep_mock():
    """Create a mock asyncio.sleep that tracks calls but still yields control to event loop."""

    async def mock_sleep_func(duration):
        mock_sleep_func.call_count += 1
        mock_sleep_func.durations.append(duration)
        await asyncio.sleep(0)  # Yield control to event loop

    mock_sleep_func.call_count = 0
    mock_sleep_func.durations = []
    return mock_sleep_func


def create_request_rate_strategy(
    config: TimingManagerConfig,
    mock_credit_manager: MockCreditManager,
    request_rate: float,
    request_count: int,
    warmup_request_count: int = 0,
    auto_return: bool = True,
) -> RequestRateStrategy:
    """Create a RequestRateStrategy instance."""
    config.request_rate = request_rate
    config.request_count = request_count
    config.warmup_request_count = warmup_request_count
    mock_credit_manager.auto_credit_return = auto_return
    strategy = RequestRateStrategy(config, mock_credit_manager)
    mock_credit_manager.credit_strategy = strategy
    strategy.logger.info = MagicMock()
    strategy.logger.debug = MagicMock()
    return strategy


@pytest.mark.asyncio
class TestRequestRateStrategy:
    """Tests for the RequestRateStrategy class."""

    async def test_initialization_with_valid_config(self, config, mock_credit_manager):
        """Test that RequestRateStrategy initializes correctly with valid configuration."""
        strategy = create_request_rate_strategy(
            config, mock_credit_manager, request_rate=10.0, request_count=100
        )

        assert strategy._request_rate == 10.0
        assert strategy.profiling.total == 100
        assert strategy.warmup is None
        assert strategy.profiling.sent == 0
        assert strategy.profiling.completed == 0
        assert strategy.active_phase == strategy.profiling

    async def test_initialization_with_warmup(self, config, mock_credit_manager):
        """Test that RequestRateStrategy initializes correctly with warmup."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=5.0,
            request_count=50,
            warmup_request_count=10,
        )

        assert strategy._request_rate == 5.0
        assert strategy.profiling.total == 50
        assert strategy.warmup is not None
        assert strategy.warmup.total == 10
        assert strategy.warmup.completed_event is not None
        assert strategy.active_phase == strategy.warmup

    async def test_initialization_without_request_rate_raises_error(
        self, config, mock_credit_manager
    ):
        """Test that RequestRateStrategy raises error when request_rate is None."""
        config.request_rate = None

        with pytest.raises(InvalidStateError, match="Request rate is not set"):
            RequestRateStrategy(config, mock_credit_manager)

    async def test_warmup_loop_basic_functionality(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test basic warmup loop functionality."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=2.0,
            request_count=10,
            warmup_request_count=3,
        )

        # Mock asyncio.sleep to track calls but still yield control
        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            # Run warmup phase
            await strategy._execute_phase(strategy.warmup)

            # Wait for pending tasks
            await asyncio.gather(*strategy.tasks)

            # Verify warmup completion
            assert strategy.warmup.sent == 3
            assert mock_sleep_func.call_count == 3

            # Verify sleep duration (1/request_rate = 0.5 seconds)
            expected_sleep_duration = 1.0 / 2.0
            for duration in mock_sleep_func.durations:
                assert abs(duration - expected_sleep_duration) < 0.01

    async def test_warmup_loop_with_zero_warmup_requests(
        self, config, mock_credit_manager
    ):
        """Test warmup loop with zero warmup requests."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=50,
            warmup_request_count=0,
        )

        # Verify no warmup phase was created
        assert strategy.warmup is None
        assert strategy.active_phase == strategy.profiling

    async def test_credit_drop_loop_basic_functionality(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test basic credit drop loop functionality."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=5.0,
            request_count=10,
            warmup_request_count=0,
        )

        # Mock asyncio.sleep to track calls
        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            # Run credit drop phase (profiling phase)
            await strategy._execute_phase(strategy.profiling)

            # Wait for pending tasks
            await asyncio.gather(*strategy.tasks)

            # Verify credits were sent
            assert strategy.profiling.sent == 10
            assert len(mock_credit_manager.dropped_credits) == 10
            assert mock_sleep_func.call_count == 10

            # Verify sleep duration (1/request_rate = 0.2 seconds)
            expected_sleep_duration = 1.0 / 5.0
            for duration in mock_sleep_func.durations:
                assert abs(duration - expected_sleep_duration) < 0.01

    async def test_credit_drop_loop_waits_for_warmup(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test that credit drop loop waits for warmup completion."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=5,
            warmup_request_count=2,
        )

        # Warmup not completed yet
        assert not strategy.warmup.completed_event.is_set()

        # Create a task to complete warmup after a delay
        async def complete_warmup():
            await real_sleep(0.01)  # Small delay
            strategy.warmup.completed_event.set()

        # Start both tasks
        warmup_task = asyncio.create_task(complete_warmup())

        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            drop_task = asyncio.create_task(
                strategy._execute_phase(
                    strategy.profiling, strategy.warmup.completed_event
                )
            )

            # Wait for both tasks
            await asyncio.gather(warmup_task, drop_task, *strategy.tasks)

            # Verify warmup completion was awaited
            assert strategy.warmup.completed_event.is_set()
            assert strategy.profiling.sent == 5

    async def test_credit_drop_loop_with_zero_rate(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test credit drop loop with zero wait duration."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=1000.0,  # High rate = small wait duration
            request_count=5,
            warmup_request_count=0,
        )

        # Mock asyncio.sleep to track calls
        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            # Run credit drop loop
            await strategy._execute_phase(strategy.profiling)

            # Wait for pending tasks
            await asyncio.gather(*strategy.tasks)

            # Verify credits were sent
            assert strategy.profiling.sent == 5
            assert len(mock_credit_manager.dropped_credits) == 5
            assert mock_sleep_func.call_count == 5

    async def test_start_method_launches_all_tasks(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test that start method launches all required background tasks."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=5,
            warmup_request_count=2,
        )

        # Mock the individual methods to prevent actual execution
        strategy._progress_report_loop = AsyncMock()
        strategy._execute_phase = AsyncMock()

        # Start the strategy
        await strategy.start()

        # Verify all tasks were launched (progress loop + warmup phase + profiling phase)
        assert len(strategy.tasks) == 3

    async def test_progress_report_loop_basic_functionality(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test basic progress report loop functionality."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=100,
            warmup_request_count=0,
        )

        # Mock the credit manager method
        mock_credit_manager.publish_progress = AsyncMock()

        # Create a task that will cancel after a short time
        async def cancel_after_delay():
            await real_sleep(0.01)
            # Signal completion to stop the loop
            strategy.active_phase.completed_event.set()

        # Start the progress report loop and cancellation
        cancel_task = asyncio.create_task(cancel_after_delay())

        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(strategy._progress_report_loop(), cancel_task)

        # Verify progress was reported
        assert mock_credit_manager.publish_progress.call_count > 0

    async def test_progress_report_loop_handles_cancellation(
        self, config, mock_credit_manager
    ):
        """Test that progress report loop handles cancellation gracefully."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=100,
            warmup_request_count=0,
        )

        # Mock the credit manager method to raise CancelledError
        mock_credit_manager.publish_progress = AsyncMock(
            side_effect=asyncio.CancelledError()
        )

        # Run the progress report loop
        with contextlib.suppress(asyncio.CancelledError):
            await strategy._progress_report_loop()

        # Verify the method was called at least once
        assert mock_credit_manager.publish_progress.call_count >= 1

    async def test_on_credit_return_basic_functionality(
        self, config, mock_credit_manager
    ):
        """Test basic credit return processing."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=5,
            warmup_request_count=0,
        )

        # Process a credit return
        message = CreditReturnMessage(service_id="test-service")
        await strategy._on_credit_return(message)

        # Verify credit was processed
        assert strategy.active_phase.completed == 1

    async def test_on_credit_return_triggers_completion(
        self, config, mock_credit_manager
    ):
        """Test that credit return triggers completion when all credits are returned."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=3,
            warmup_request_count=0,
        )

        # Process credit returns
        message = CreditReturnMessage(service_id="test-service")
        await strategy._on_credit_return(message)
        await strategy._on_credit_return(message)
        await strategy._on_credit_return(message)

        # Wait for pending tasks
        await asyncio.gather(*strategy.tasks)

        # Verify completion was triggered
        assert strategy.active_phase.completed == 3
        assert len(mock_credit_manager.credits_complete_calls) == 1
        assert mock_credit_manager.credits_complete_calls[0]["cancelled"] is False

    async def test_on_credit_return_partial_completion(
        self, config, mock_credit_manager
    ):
        """Test credit return processing with partial completion."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=5,
            warmup_request_count=0,
        )

        # Process some credit returns
        message = CreditReturnMessage(service_id="test-service")
        await strategy._on_credit_return(message)
        await strategy._on_credit_return(message)

        # Wait for pending tasks
        await asyncio.gather(*strategy.tasks)

        # Verify partial completion
        assert strategy.active_phase.completed == 2
        assert len(mock_credit_manager.credits_complete_calls) == 0

    async def test_full_lifecycle_without_warmup(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test complete lifecycle without warmup."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=100.0,  # High rate for fast execution
            request_count=3,
            warmup_request_count=0,
        )

        # Mock sleep to speed up execution
        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            # Start the strategy
            await strategy.start()

            # Wait for all tasks to complete credit sending
            await asyncio.gather(*strategy.tasks)

            # Process credit returns
            message = CreditReturnMessage(service_id="test-service")
            await strategy._on_credit_return(message)
            await strategy._on_credit_return(message)
            await strategy._on_credit_return(message)

            # Verify final state
            assert strategy.profiling.sent == 3
            assert strategy.profiling.completed == 3
            assert len(mock_credit_manager.dropped_credits) == 3
            assert len(mock_credit_manager.credits_complete_calls) == 1

    async def test_full_lifecycle_with_warmup(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test complete lifecycle with warmup."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=100.0,  # High rate for fast execution
            request_count=3,
            warmup_request_count=2,
        )

        # Mock sleep to speed up execution
        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            # Start the strategy
            await strategy.start()

            # Wait for all tasks to complete credit sending
            await asyncio.gather(*strategy.tasks)

            # Process credit returns (warmup + profiling)
            message = CreditReturnMessage(service_id="test-service")
            await strategy._on_credit_return(message)  # warmup credit 1
            await strategy._on_credit_return(
                message
            )  # warmup credit 2 (completes warmup)
            await strategy._on_credit_return(message)  # profiling credit 1
            await strategy._on_credit_return(message)  # profiling credit 2
            await strategy._on_credit_return(
                message
            )  # profiling credit 3 (completes profiling)

            # Verify final state (warmup + profiling credits)
            assert strategy.warmup.sent == 2
            assert strategy.profiling.sent == 3
            assert (
                len(mock_credit_manager.dropped_credits) == 5
            )  # 2 warmup + 3 profiling
            assert (
                len(mock_credit_manager.credits_complete_calls) == 2
            )  # warmup + profiling

    async def test_warmup_timing_calculation(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test that warmup timing is calculated correctly."""
        start_time = seconds_to_ns(10)
        mock_time_ns.return_value = start_time

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=2.0,
            request_count=10,
            warmup_request_count=5,
        )

        # Run warmup phase
        await strategy._execute_phase(strategy.warmup)

        # Verify timing
        assert strategy.warmup.start_time_ns == start_time

    async def test_rate_limiting_accuracy(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test that rate limiting is applied accurately."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=4.0,  # 0.25 seconds per request
            request_count=5,
            warmup_request_count=0,
        )

        # Mock asyncio.sleep to track calls
        sleep_durations = []

        async def track_sleep(duration):
            sleep_durations.append(duration)
            await asyncio.sleep(0)  # Yield control

        with patch("asyncio.sleep", side_effect=track_sleep):
            # Run credit drop loop
            await strategy._execute_phase(strategy.profiling)

            # Wait for pending tasks
            await asyncio.gather(*strategy.tasks)

            # Verify sleep durations
            expected_duration = 1.0 / 4.0  # 0.25 seconds
            assert len(sleep_durations) == 5
            for duration in sleep_durations:
                assert abs(duration - expected_duration) < 0.01

    async def test_error_handling_in_progress_loop(self, config, mock_credit_manager):
        """Test error handling in progress report loop."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=100,
            warmup_request_count=0,
        )

        # Mock the credit manager method to raise an exception
        mock_credit_manager.publish_progress = AsyncMock(
            side_effect=Exception("Test error")
        )

        # Mock logger to capture debug messages
        strategy.logger.debug = MagicMock()

        # Create a task that will cancel after a short time
        async def cancel_after_delay():
            await real_sleep(0.01)
            # Signal completion to stop the loop
            strategy.active_phase.completed_event.set()

        # Start the progress report loop and cancellation
        cancel_task = asyncio.create_task(cancel_after_delay())

        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(strategy._progress_report_loop(), cancel_task)

        # Verify the method was called despite errors
        assert mock_credit_manager.publish_progress.call_count > 0


@pytest.mark.asyncio
class TestRequestRateStrategyEdgeCases:
    """Tests for edge cases and error conditions in RequestRateStrategy."""

    async def test_very_high_request_rate(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test behavior with very high request rates."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10000.0,  # Very high rate
            request_count=10,
            warmup_request_count=0,
        )

        # Mock asyncio.sleep to track calls
        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            # Run credit drop loop
            await strategy._execute_phase(strategy.profiling)

            # Wait for pending tasks
            await asyncio.gather(*strategy.tasks)

            # Verify credits were sent
            assert strategy.profiling.sent == 10
            assert len(mock_credit_manager.dropped_credits) == 10

            # Verify sleep was called with very small durations
            expected_duration = 1.0 / 10000.0  # 0.0001 seconds
            for duration in mock_sleep_func.durations:
                assert abs(duration - expected_duration) < 0.00001

    async def test_very_low_request_rate(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test behavior with very low request rates."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=0.1,  # Very low rate = 10 seconds per request
            request_count=2,
            warmup_request_count=0,
        )

        # Mock asyncio.sleep to track calls
        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            # Run credit drop loop
            await strategy._execute_phase(strategy.profiling)

            # Wait for pending tasks
            await asyncio.gather(*strategy.tasks)

            # Verify credits were sent
            assert strategy.profiling.sent == 2
            assert len(mock_credit_manager.dropped_credits) == 2

            # Verify sleep was called with long durations
            expected_duration = 1.0 / 0.1  # 10 seconds
            for duration in mock_sleep_func.durations:
                assert abs(duration - expected_duration) < 0.01

    async def test_zero_request_count(self, config, mock_credit_manager):
        """Test behavior with zero request count."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=0,
            warmup_request_count=0,
        )

        # Run credit drop loop
        await strategy._execute_phase(strategy.profiling)

        # Wait for pending tasks
        await asyncio.gather(*strategy.tasks)

        # Verify no credits were sent
        assert strategy.profiling.sent == 0
        assert len(mock_credit_manager.dropped_credits) == 0

    async def test_single_request_count(
        self, mock_time_ns, config, mock_credit_manager
    ):
        """Test behavior with single request count."""
        mock_time_ns.return_value = seconds_to_ns(1)

        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=5.0,
            request_count=1,
            warmup_request_count=0,
        )

        # Mock asyncio.sleep to track calls
        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            # Run credit drop loop
            await strategy._execute_phase(strategy.profiling)

            # Wait for pending tasks
            await asyncio.gather(*strategy.tasks)

            # Verify single credit was sent
            assert strategy.profiling.sent == 1
            assert len(mock_credit_manager.dropped_credits) == 1
            assert mock_sleep_func.call_count == 1

    async def test_warmup_event_behavior(self, config, mock_credit_manager):
        """Test warmup event setting and clearing behavior."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=5,
            warmup_request_count=2,
        )

        # Initially event should not be set
        assert not strategy.warmup.completed_event.is_set()

        # Mock asyncio.sleep to speed up execution
        mock_sleep_func = create_yielding_sleep_mock()

        with patch("asyncio.sleep", side_effect=mock_sleep_func):
            # Run warmup phase
            await strategy._execute_phase(strategy.warmup)

            # Wait for pending tasks
            await asyncio.gather(*strategy.tasks)

            # After warmup, verify credits were sent
            assert strategy.warmup.sent == 2

    async def test_concurrent_credit_returns(self, config, mock_credit_manager):
        """Test handling of concurrent credit returns."""
        strategy = create_request_rate_strategy(
            config,
            mock_credit_manager,
            request_rate=10.0,
            request_count=5,
            warmup_request_count=0,
        )

        # Create multiple credit return tasks
        messages = [CreditReturnMessage(service_id="test-service") for _ in range(5)]

        # Process all credit returns concurrently
        await asyncio.gather(*[strategy._on_credit_return(msg) for msg in messages])

        # Wait for pending tasks
        await asyncio.gather(*strategy.tasks)

        # Verify all credits were processed
        assert strategy.active_phase.completed == 5
        assert len(mock_credit_manager.credits_complete_calls) == 1
        assert mock_credit_manager.credits_complete_calls[0]["cancelled"] is False


@pytest.mark.asyncio
class TestRequestRateStrategyPoissonDistribution:
    """Tests for verifying Poisson distribution behavior in RequestRateStrategy."""

    async def test_poisson_rate_follows_exponential_distribution(
        self, config, mock_credit_manager
    ):
        """Test that _execute_poisson_rate generates inter-arrival times following exponential distribution."""
        # Set up strategy with Poisson mode
        request_rate = 20.0  # 20 requests per second
        expected_mean_interval = 1.0 / request_rate  # 0.05 seconds
        request_count = 200  # Collect enough samples for statistical analysis

        config.request_rate = request_rate
        config.request_count = request_count
        config.warmup_request_count = 0
        config.request_rate_mode = RequestRateMode.POISSON
        config.random_seed = 42  # For reproducible results

        # Create strategy
        strategy = RequestRateStrategy(config, mock_credit_manager)

        # Track precise timestamps when credits are dropped
        credit_drop_times = []
        original_drop_credit = mock_credit_manager.drop_credit

        async def timestamp_drop_credit(*args, **kwargs):
            credit_drop_times.append(time.perf_counter())
            await original_drop_credit(*args, **kwargs)

        mock_credit_manager.drop_credit = timestamp_drop_credit

        # Run the Poisson rate execution
        start_time = time.perf_counter()
        await strategy._execute_poisson_rate(strategy.profiling)

        # Calculate inter-arrival times
        assert len(credit_drop_times) == request_count, (
            f"Expected {request_count} credits, got {len(credit_drop_times)}"
        )

        inter_arrival_times = []
        for i in range(1, len(credit_drop_times)):
            interval = credit_drop_times[i] - credit_drop_times[i - 1]
            inter_arrival_times.append(interval)

        inter_arrival_times = np.array(inter_arrival_times)

        # Statistical tests for exponential distribution
        # 1. Test mean: For exponential distribution with rate λ, mean = 1/λ
        actual_mean = np.mean(inter_arrival_times)
        assert (
            abs(actual_mean - expected_mean_interval) < expected_mean_interval * 0.2
        ), (
            f"Mean inter-arrival time {actual_mean:.4f} deviates too much from expected {expected_mean_interval:.4f}"
        )

        # 2. Test standard deviation: For exponential distribution, std = mean
        actual_std = np.std(inter_arrival_times)
        expected_std = expected_mean_interval
        assert abs(actual_std - expected_std) < expected_std * 0.3, (
            f"Standard deviation {actual_std:.4f} deviates too much from expected {expected_std:.4f}"
        )

        # 3. Test coefficient of variation: For exponential distribution, CV = 1
        cv = actual_std / actual_mean
        assert abs(cv - 1.0) < 0.2, (
            f"Coefficient of variation {cv:.4f} should be close to 1.0 for exponential distribution"
        )

        # 4. Test that ~63.2% of values are less than the mean (exponential CDF property)
        values_below_mean = np.sum(inter_arrival_times < actual_mean)
        proportion_below_mean = values_below_mean / len(inter_arrival_times)
        expected_proportion = 1 - math.exp(-1)  # ≈ 0.632
        assert abs(proportion_below_mean - expected_proportion) < 0.1, (
            f"Proportion below mean {proportion_below_mean:.3f} should be close to {expected_proportion:.3f}"
        )

    async def test_poisson_rate_independence_of_intervals(
        self, config, mock_credit_manager
    ):
        """Test that inter-arrival times in Poisson process are independent (low correlation)."""
        # Set up strategy with Poisson mode
        request_rate = 15.0
        request_count = 150

        config.request_rate = request_rate
        config.request_count = request_count
        config.warmup_request_count = 0
        config.request_rate_mode = RequestRateMode.POISSON
        config.random_seed = 123  # For reproducible results

        strategy = RequestRateStrategy(config, mock_credit_manager)

        # Track timestamps
        credit_drop_times = []
        original_drop_credit = mock_credit_manager.drop_credit

        async def timestamp_drop_credit(*args, **kwargs):
            credit_drop_times.append(time.perf_counter())
            await original_drop_credit(*args, **kwargs)

        mock_credit_manager.drop_credit = timestamp_drop_credit

        # Run the Poisson rate execution
        await strategy._execute_poisson_rate(strategy.profiling)

        # Calculate inter-arrival times
        inter_arrival_times = []
        for i in range(1, len(credit_drop_times)):
            interval = credit_drop_times[i] - credit_drop_times[i - 1]
            inter_arrival_times.append(interval)

        inter_arrival_times = np.array(inter_arrival_times)

        # Test independence by checking correlation between consecutive intervals
        # For independent events, correlation should be close to 0
        if len(inter_arrival_times) > 2:
            correlation = np.corrcoef(
                inter_arrival_times[:-1], inter_arrival_times[1:]
            )[0, 1]
            # Allow for some variance due to finite sample size, but correlation should be low
            assert abs(correlation) < 0.2, (
                f"Correlation between consecutive intervals {correlation:.4f} indicates lack of independence"
            )

    async def test_poisson_rate_with_different_rates(self, config, mock_credit_manager):
        """Test that Poisson process works correctly with different request rates."""
        test_rates = [5.0, 10.0, 50.0]

        for request_rate in test_rates:
            config.request_rate = request_rate
            config.request_count = 100
            config.warmup_request_count = 0
            config.request_rate_mode = RequestRateMode.POISSON
            config.random_seed = 42

            strategy = RequestRateStrategy(config, mock_credit_manager)

            # Track timestamps
            credit_drop_times = []
            original_drop_credit = mock_credit_manager.drop_credit

            async def timestamp_drop_credit(*args, **kwargs):
                credit_drop_times.append(time.perf_counter())
                await original_drop_credit(*args, **kwargs)

            mock_credit_manager.drop_credit = timestamp_drop_credit

            # Reset for each test
            credit_drop_times.clear()
            mock_credit_manager.dropped_credits.clear()
            strategy.profiling.sent = 0

            # Run the test
            await strategy._execute_poisson_rate(strategy.profiling)

            # Calculate actual rate
            if len(credit_drop_times) >= 2:
                total_time = credit_drop_times[-1] - credit_drop_times[0]
                actual_rate = (len(credit_drop_times) - 1) / total_time

                # Allow for some variance, but rate should be approximately correct
                assert abs(actual_rate - request_rate) < request_rate * 0.3, (
                    f"For rate {request_rate}, actual rate {actual_rate:.2f} deviates too much"
                )

    async def test_poisson_memoryless_property(self, config, mock_credit_manager):
        """Test the memoryless property of exponential distribution in Poisson process."""
        request_rate = 25.0
        request_count = 200

        config.request_rate = request_rate
        config.request_count = request_count
        config.warmup_request_count = 0
        config.request_rate_mode = RequestRateMode.POISSON
        config.random_seed = 456

        strategy = RequestRateStrategy(config, mock_credit_manager)

        # Track timestamps
        credit_drop_times = []
        original_drop_credit = mock_credit_manager.drop_credit

        async def timestamp_drop_credit(*args, **kwargs):
            credit_drop_times.append(time.perf_counter())
            await original_drop_credit(*args, **kwargs)

        mock_credit_manager.drop_credit = timestamp_drop_credit

        # Run the test
        await strategy._execute_poisson_rate(strategy.profiling)

        # Calculate inter-arrival times
        inter_arrival_times = []
        for i in range(1, len(credit_drop_times)):
            interval = credit_drop_times[i] - credit_drop_times[i - 1]
            inter_arrival_times.append(interval)

        inter_arrival_times = np.array(inter_arrival_times)

        # Test memoryless property: P(X > s + t | X > s) = P(X > t)
        # We'll test this by checking that conditioning on larger values doesn't change the distribution
        threshold = np.median(inter_arrival_times)
        above_threshold = inter_arrival_times[inter_arrival_times > threshold]

        if len(above_threshold) > 10:
            # For values above threshold, subtract threshold (memoryless property)
            shifted_values = above_threshold - threshold

            # These shifted values should have the same exponential distribution
            # Test by comparing means (approximately)
            original_mean = np.mean(inter_arrival_times)
            shifted_mean = np.mean(shifted_values)

            # Due to memoryless property, shifted mean should be close to original mean
            assert abs(shifted_mean - original_mean) < original_mean * 0.4, (
                f"Memoryless property violated: shifted mean {shifted_mean:.4f} vs original {original_mean:.4f}"
            )
