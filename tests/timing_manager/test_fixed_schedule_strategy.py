# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the timing manager fixed schedule strategy.
"""

import time

import pytest
from pytest import approx

from aiperf.common.constants import MILLIS_PER_SECOND
from aiperf.common.enums import CreditPhase, TimingMode
from aiperf.common.models import CreditPhaseStats
from aiperf.timing import FixedScheduleStrategy, TimingManagerConfig
from tests.timing_manager.conftest import MockCreditManager
from tests.utils.time_traveler import TimeTraveler

# Test constants
SPEEDUP_2X_FASTER = 2.0
SPEEDUP_2X_SLOWER = 0.5
SPEEDUP_4X_FASTER = 4.0
SPEEDUP_1000X_FASTER = 1000.0
YEAR_IN_MILLISECONDS = 365 * 24 * 60 * 60 * 1000


class TestFixedScheduleStrategy:
    """Tests for the fixed schedule strategy."""

    @pytest.fixture
    def simple_schedule(self) -> list[tuple[int, str]]:
        """Simple schedule with 3 requests."""
        return [
            (0, "conv1"),
            (100, "conv2"),
            (200, "conv3"),
        ]

    @pytest.fixture
    def schedule_with_offset(self) -> list[tuple[int, str]]:
        """Schedule with auto offset."""
        return [(1000, "conv1"), (1100, "conv2"), (1200, "conv3")]

    def _create_strategy(
        self,
        mock_credit_manager: MockCreditManager,
        schedule: list[tuple[int, str]],
        auto_offset: bool = False,
        manual_offset: int | None = None,
        speedup: float | None = None,
    ) -> tuple[FixedScheduleStrategy, CreditPhaseStats]:
        """Helper to create a strategy with optional config overrides."""
        config = TimingManagerConfig.model_construct(
            timing_mode=TimingMode.FIXED_SCHEDULE,
            auto_offset_timestamps=auto_offset,
            fixed_schedule_start_offset=manual_offset,
            fixed_schedule_speedup=speedup,
        )
        return FixedScheduleStrategy(
            config=config,
            credit_manager=mock_credit_manager,
            schedule=schedule,
        ), CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns(),
            total_expected_requests=len(schedule),
        )

    def test_initialization_phase_configs(
        self,
        simple_schedule: list[tuple[int, str]],
        mock_credit_manager: MockCreditManager,
    ):
        """Test initialization creates correct phase configurations."""
        strategy, _ = self._create_strategy(mock_credit_manager, simple_schedule)

        assert len(strategy.ordered_phase_configs) == 1
        assert strategy._num_requests == len(simple_schedule)
        assert strategy._schedule == simple_schedule

        # Check phase types - only profiling phase supported
        assert strategy.ordered_phase_configs[0].type == CreditPhase.PROFILING

    def test_empty_schedule_raises_error(self, mock_credit_manager: MockCreditManager):
        """Test that empty schedule raises ValueError."""
        with pytest.raises(ValueError, match="No schedule loaded"):
            self._create_strategy(mock_credit_manager, [])

    @pytest.mark.parametrize(
        "schedule,expected_groups,expected_keys",
        [
            (
                [(0, "conv1"), (100, "conv2"), (200, "conv3")],
                {0: ["conv1"], 100: ["conv2"], 200: ["conv3"]},
                [0, 100, 200],
            ),
            (
                [(0, "conv1"), (0, "conv2"), (100, "conv3"), (100, "conv4")],
                {0: ["conv1", "conv2"], 100: ["conv3", "conv4"]},
                [0, 100],
            ),
        ],
    )
    def test_timestamp_grouping(
        self,
        mock_credit_manager: MockCreditManager,
        schedule: list[tuple[int, str]],
        expected_groups: dict[int, list[str]],
        expected_keys: list[int],
    ):
        """Test that timestamps are properly grouped."""
        strategy, _ = self._create_strategy(mock_credit_manager, schedule)

        assert strategy._timestamp_groups == expected_groups
        assert strategy._sorted_timestamp_keys == expected_keys

    @pytest.mark.parametrize(
        "auto_offset,manual_offset,expected_zero_ms",
        [
            (True, None, 1000),  # Auto offset to first timestamp
            (False, 500, 500),  # Manual offset
            (False, None, 0),  # No offset
        ],
    )
    def test_schedule_offset_configurations(
        self,
        mock_credit_manager: MockCreditManager,
        schedule_with_offset: list[tuple[int, str]],
        auto_offset: bool,
        manual_offset: int | None,
        expected_zero_ms: int,
    ):
        """Test different schedule offset configurations."""
        strategy, _ = self._create_strategy(
            mock_credit_manager, schedule_with_offset, auto_offset, manual_offset
        )

        assert strategy._schedule_zero_ms == expected_zero_ms

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "schedule,expected_duration",
        [
            ([(0, "conv1"), (100, "conv2"), (200, "conv3")], 0.2),  # 200ms total
            ([(0, "conv1"), (0, "conv2"), (0, "conv3")], 0.0),  # All at once
            ([(-100, "conv1"), (-50, "conv2"), (0, "conv3")], 0.0),  # Past timestamps
        ],
    )
    async def test_execution_timing(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
        schedule: list[tuple[int, str]],
        expected_duration: float,
    ):
        """Test that execution timing is correct for different schedules."""
        strategy, phase_stats = self._create_strategy(mock_credit_manager, schedule)

        with time_traveler.sleeps_for(expected_duration):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == len(schedule)
        assert len(mock_credit_manager.dropped_credits) == len(schedule)

        # Verify all conversation IDs were processed
        sent_conversations = {
            credit.conversation_id for credit in mock_credit_manager.dropped_credits
        }
        assert sent_conversations == {conv_id for _, conv_id in schedule}

    @pytest.mark.parametrize("auto_offset", [True, False])
    @pytest.mark.parametrize(
        "schedule",
        [
            [(1000, "conv1"), (1100, "conv2"), (1200, "conv3")],
            [(600, "conv1"), (700, "conv2"), (800, "conv3")],
            [(0, "conv1"), (100, "conv2"), (200, "conv3")],
        ],
    )  # fmt: skip
    @pytest.mark.asyncio
    async def test_execution_with_auto_offset(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
        auto_offset: bool,
        schedule: list[tuple[int, str]],
    ):
        """Test execution timing with auto offset timestamps."""
        strategy, phase_stats = self._create_strategy(
            mock_credit_manager, schedule, auto_offset
        )

        first_timestamp_ms = schedule[0][0]
        last_timestamp_ms = schedule[-1][0]

        sleep_duration_ms = (
            last_timestamp_ms - first_timestamp_ms if auto_offset else last_timestamp_ms
        )
        with time_traveler.sleeps_for(sleep_duration_ms / MILLIS_PER_SECOND):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == 3
        expected_zero_ms = first_timestamp_ms if auto_offset else 0
        assert strategy._schedule_zero_ms == expected_zero_ms

    @pytest.mark.parametrize(
        "speedup,expected_time_scale",
        [
            (None, 1.0),   # Default behavior (no speedup)
            (1.0, 1.0),    # No speedup
            (SPEEDUP_2X_FASTER, 0.5),    # 2x faster
            (SPEEDUP_2X_SLOWER, 2.0),    # 2x slower
            (10.0, 0.1),   # 10x faster
            (0.1, 10.0),   # 10x slower
        ],
    )  # fmt: skip
    def test_speedup_time_scale_calculation(
        self,
        simple_schedule: list[tuple[int, str]],
        mock_credit_manager: MockCreditManager,
        speedup: float | None,
        expected_time_scale: float,
    ):
        """Test that speedup parameter correctly calculates time scale."""
        strategy, _ = self._create_strategy(
            mock_credit_manager, simple_schedule, speedup=speedup
        )

        assert strategy._time_scale == expected_time_scale

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "speedup,schedule",
        [
            # 2x faster - should take half the time
            (SPEEDUP_2X_FASTER, [(0, "conv1"), (100, "conv2"), (200, "conv3")]),
            # 4x faster - should take quarter the time
            (SPEEDUP_4X_FASTER, [(0, "conv1"), (100, "conv2"), (200, "conv3")]),
            # 2x slower - should take double the time
            (SPEEDUP_2X_SLOWER, [(0, "conv1"), (100, "conv2"), (200, "conv3")]),
            # Different schedule with larger gaps
            (SPEEDUP_2X_FASTER, [(0, "conv1"), (500, "conv2"), (1000, "conv3")]),
            # Edge case: all at same timestamp should still be instant
            (SPEEDUP_2X_FASTER, [(0, "conv1"), (0, "conv2"), (0, "conv3")]),
            (SPEEDUP_2X_SLOWER, [(0, "conv1"), (0, "conv2"), (0, "conv3")]),
        ],
    )  # fmt: skip
    async def test_speedup_execution_timing(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
        speedup: float,
        schedule: list[tuple[int, str]],
    ):
        """Test that speedup parameter affects actual execution timing."""
        strategy, phase_stats = self._create_strategy(
            mock_credit_manager, schedule, auto_offset=False, speedup=speedup
        )

        # Calculate expected duration based on the last timestamp (since auto_offset=False)
        # With auto_offset=False, duration is calculated from schedule_zero_ms=0 to the last timestamp
        last_timestamp_ms = schedule[-1][0]
        base_duration_sec = last_timestamp_ms / MILLIS_PER_SECOND
        expected_duration = base_duration_sec / speedup

        with time_traveler.sleeps_for(expected_duration):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == len(schedule)
        assert len(mock_credit_manager.dropped_credits) == len(schedule)

    @pytest.mark.asyncio
    async def test_speedup_with_auto_offset(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
    ):
        """Test speedup works correctly with auto offset timestamps."""
        # Schedule starts at 1000ms with 200ms total duration
        schedule = [(1000, "conv1"), (1100, "conv2"), (1200, "conv3")]
        speedup = SPEEDUP_2X_FASTER

        strategy, phase_stats = self._create_strategy(
            mock_credit_manager, schedule, auto_offset=True, speedup=speedup
        )

        # With auto offset, the duration should be (1200-1000)ms = 200ms
        # At 2x speed: 200ms / 2 = 100ms = 0.1s
        base_duration_sec = (1200 - 1000) / MILLIS_PER_SECOND  # 0.2s
        expected_duration = base_duration_sec / speedup  # 0.1s

        with time_traveler.sleeps_for(expected_duration):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == 3
        assert strategy._schedule_zero_ms == 1000  # First timestamp

    @pytest.mark.asyncio
    async def test_speedup_with_manual_offset(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
    ):
        """Test speedup works correctly with manual offset."""
        schedule = [(1000, "conv1"), (1100, "conv2"), (1200, "conv3")]
        manual_offset = 500
        speedup = SPEEDUP_2X_SLOWER

        strategy, phase_stats = self._create_strategy(
            mock_credit_manager, schedule, manual_offset=manual_offset, speedup=speedup
        )

        # With manual offset of 500, effective duration is (1200-500) = 700ms
        # At 0.5x speed: 700ms / 0.5 = 1400ms = 1.4s
        base_duration_sec = (1200 - manual_offset) / MILLIS_PER_SECOND  # 0.7s
        expected_duration = base_duration_sec / speedup  # 1.4s

        with time_traveler.sleeps_for(expected_duration):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == 3
        assert strategy._schedule_zero_ms == manual_offset

    @pytest.mark.asyncio
    async def test_speedup_with_negative_timestamps(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
    ):
        """Test speedup behavior with negative timestamps (past events)."""
        # All timestamps are in the past, should execute immediately
        schedule = [(-100, "conv1"), (-50, "conv2"), (0, "conv3")]
        speedup = (
            SPEEDUP_2X_FASTER  # Even with speedup, past events should be immediate
        )

        strategy, phase_stats = self._create_strategy(
            mock_credit_manager, schedule, speedup=speedup
        )

        # Should still take no time since all timestamps are <= 0
        with time_traveler.sleeps_for(0.0):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == 3

    def test_speedup_edge_cases(
        self,
        simple_schedule: list[tuple[int, str]],
        mock_credit_manager: MockCreditManager,
    ):
        """Test edge cases for speedup parameter."""
        # Test very small speedup (very slow execution)
        strategy_slow, _ = self._create_strategy(
            mock_credit_manager, simple_schedule, speedup=0.001
        )
        assert strategy_slow._time_scale == 1000.0

        # Test very large speedup (very fast execution)
        strategy_fast, _ = self._create_strategy(
            mock_credit_manager, simple_schedule, speedup=SPEEDUP_1000X_FASTER
        )
        assert strategy_fast._time_scale == 0.001

    def test_speedup_zero_raises_validation_error(
        self,
        simple_schedule: list[tuple[int, str]],
        mock_credit_manager: MockCreditManager,
    ):
        """Test that speedup = 0.0 raises a validation error in InputConfig."""
        from aiperf.common.config import InputConfig

        with pytest.raises(ValueError, match="Input should be greater than 0"):
            InputConfig(fixed_schedule_speedup=0.0)

    def test_speedup_zero_fallback_behavior(
        self,
        simple_schedule: list[tuple[int, str]],
        mock_credit_manager: MockCreditManager,
    ):
        """Test fallback behavior if speedup=0.0 somehow bypasses validation."""
        # Use model_construct to bypass validation (testing internal behavior)
        config = TimingManagerConfig.model_construct(
            timing_mode=TimingMode.FIXED_SCHEDULE,
            fixed_schedule_speedup=0.0,
        )
        strategy = FixedScheduleStrategy(config, mock_credit_manager, simple_schedule)
        # Should default to time_scale of 1.0 (no speedup)
        assert strategy._time_scale == 1.0

    def test_speedup_negative_raises_validation_error(
        self,
        simple_schedule: list[tuple[int, str]],
        mock_credit_manager: MockCreditManager,
    ):
        """Test that negative speedup values raise validation errors."""
        from aiperf.common.config import InputConfig

        with pytest.raises(ValueError, match="Input should be greater than 0"):
            InputConfig(fixed_schedule_speedup=-1.0)

        with pytest.raises(ValueError, match="Input should be greater than 0"):
            InputConfig(fixed_schedule_speedup=-0.5)

    @pytest.mark.parametrize(
        "speedup,expected_time_scale",
        [
            (1e-9, 1e9),  # extremely small speedup
            (1e9, 1e-9),  # extremely large speedup
            (1e-15, 1e15),  # edge case near machine epsilon
            (1e-6, 1e6),  # very small speedup
            (1e6, 1e-6),  # very large speedup
        ],
    )
    def test_speedup_extreme_floating_point_values(
        self,
        simple_schedule: list[tuple[int, str]],
        mock_credit_manager: MockCreditManager,
        speedup: float,
        expected_time_scale: float,
    ):
        """Test extreme floating-point speedup values for precision issues."""
        strategy, _ = self._create_strategy(
            mock_credit_manager, simple_schedule, speedup=speedup
        )
        assert strategy._time_scale == approx(expected_time_scale)

    @pytest.fixture
    def uneven_schedule(self) -> list[tuple[int, str]]:
        """Schedule with uneven timestamp spacing."""
        return [
            (0, "conv1"),  # Start immediately
            (1, "conv2"),  # Very close together
            (1000, "conv3"),  # Large gap
            (1001, "conv4"),  # Close again
            (10000, "conv5"),  # Another large gap
        ]

    @pytest.mark.asyncio
    async def test_uneven_schedule_spacing(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
        uneven_schedule: list[tuple[int, str]],
    ):
        """Test that uneven schedule spacing works correctly with scaling."""
        speedup = SPEEDUP_2X_FASTER
        strategy, phase_stats = self._create_strategy(
            mock_credit_manager, uneven_schedule, auto_offset=False, speedup=speedup
        )

        # With auto_offset=False, duration is from schedule_zero_ms=0 to last timestamp (10000ms)
        last_timestamp_ms = uneven_schedule[-1][0]  # 10000
        base_duration_sec = last_timestamp_ms / MILLIS_PER_SECOND  # 10.0 seconds
        expected_duration = base_duration_sec / speedup  # 5.0 seconds

        with time_traveler.sleeps_for(expected_duration):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == len(uneven_schedule)
        assert len(mock_credit_manager.dropped_credits) == len(uneven_schedule)

        # Verify the timestamp groups maintain relative spacing
        assert strategy._timestamp_groups[0] == ["conv1"]
        assert strategy._timestamp_groups[1] == ["conv2"]
        assert strategy._timestamp_groups[1000] == ["conv3"]
        assert strategy._timestamp_groups[1001] == ["conv4"]
        assert strategy._timestamp_groups[10000] == ["conv5"]

    @pytest.fixture
    def overlap_prone_schedule(self) -> list[tuple[int, str]]:
        """Schedule with timestamps that could overlap after scaling."""
        return [
            (0, "conv1"),
            (1, "conv2"),  # 1ms apart
            (2, "conv3"),  # 1ms apart
            (3, "conv4"),  # 1ms apart
            (100, "conv5"),  # Larger gap
        ]

    @pytest.mark.asyncio
    async def test_timestamp_overlap_after_scaling(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
        overlap_prone_schedule: list[tuple[int, str]],
    ):
        """Test behavior when timestamps could overlap after scaling."""
        speedup = SPEEDUP_1000X_FASTER
        strategy, phase_stats = self._create_strategy(
            mock_credit_manager,
            overlap_prone_schedule,
            auto_offset=False,
            speedup=speedup,
        )

        # Even with extreme speedup, timestamps should remain distinct
        # since we use the original timestamps as dictionary keys
        assert len(strategy._timestamp_groups) == 5
        assert 0 in strategy._timestamp_groups
        assert 1 in strategy._timestamp_groups
        assert 2 in strategy._timestamp_groups
        assert 3 in strategy._timestamp_groups
        assert 100 in strategy._timestamp_groups

        # With auto_offset=False, duration is from schedule_zero_ms=0 to last timestamp (100ms)
        last_timestamp_ms = overlap_prone_schedule[-1][0]  # 100
        base_duration_sec = last_timestamp_ms / MILLIS_PER_SECOND  # 0.1 seconds
        expected_duration = base_duration_sec / speedup  # 0.0001 seconds

        with time_traveler.sleeps_for(expected_duration):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == len(overlap_prone_schedule)

    def test_timestamp_grouping_with_extreme_speedup(
        self,
        mock_credit_manager: MockCreditManager,
        overlap_prone_schedule: list[tuple[int, str]],
    ):
        """Test that close timestamps with high speedup don't cause issues in grouping."""
        speedup = 1e6  # Million times faster
        strategy, _ = self._create_strategy(
            mock_credit_manager, overlap_prone_schedule, speedup=speedup
        )

        # The time scale should be extremely small
        assert strategy._time_scale == approx(1e-6)

        # But timestamp grouping should still work correctly
        # (no timestamps should be lost or merged)
        total_conversations = sum(
            len(convs) for convs in strategy._timestamp_groups.values()
        )
        assert total_conversations == len(overlap_prone_schedule)

    @pytest.fixture
    def large_timestamp_schedule(self) -> list[tuple[int, str]]:
        """Schedule with very large timestamps."""
        return [
            (10**9, "conv1"),  # 1 billion ms ~= 11.5 days
            (10**9 + 1000, "conv2"),  # 1 second later
            (10**12, "conv3"),  # 1 trillion ms ~= 31.7 years
        ]

    def test_very_large_timestamps_precision(
        self,
        mock_credit_manager: MockCreditManager,
        large_timestamp_schedule: list[tuple[int, str]],
    ):
        """Test behavior with very large timestamps that could cause precision issues."""
        speedup = SPEEDUP_2X_FASTER
        strategy, _ = self._create_strategy(
            mock_credit_manager,
            large_timestamp_schedule,
            auto_offset=True,
            speedup=speedup,
        )

        # Verify timestamps are preserved exactly in grouping
        assert 10**9 in strategy._timestamp_groups
        assert 10**9 + 1000 in strategy._timestamp_groups
        assert 10**12 in strategy._timestamp_groups

        # Verify time scale calculation doesn't overflow
        assert strategy._time_scale == 0.5

        # Check that the schedule zero point is set correctly with auto offset
        assert strategy._schedule_zero_ms == 10**9  # First timestamp

    @pytest.mark.asyncio
    async def test_large_timestamps_execution(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
        large_timestamp_schedule: list[tuple[int, str]],
    ):
        """Test execution with large timestamps doesn't cause overflow issues."""
        speedup = SPEEDUP_1000X_FASTER
        strategy, phase_stats = self._create_strategy(
            mock_credit_manager,
            large_timestamp_schedule,
            auto_offset=True,
            speedup=speedup,
        )

        # With auto_offset=True, duration is calculated as (last_timestamp - first_timestamp)
        first_timestamp_ms = large_timestamp_schedule[0][0]  # 10^9
        last_timestamp_ms = large_timestamp_schedule[-1][0]  # 10^12
        base_duration_ms = last_timestamp_ms - first_timestamp_ms
        base_duration_sec = base_duration_ms / MILLIS_PER_SECOND
        expected_duration = base_duration_sec / speedup

        # Since timing is mocked, we can test the full duration without worrying about timeouts
        # The key test is that large timestamp arithmetic doesn't overflow or cause precision errors
        with time_traveler.sleeps_for(expected_duration):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == len(large_timestamp_schedule)

    @pytest.mark.asyncio
    async def test_very_long_duration_execution(
        self,
        mock_credit_manager: MockCreditManager,
        time_traveler: TimeTraveler,
    ):
        """Test that extremely long durations work correctly with mocked timing."""
        # Create a schedule with a very large time span
        year_in_ms = YEAR_IN_MILLISECONDS
        schedule = [
            (0, "conv1"),
            (year_in_ms, "conv2"),
        ]

        speedup = 1.0  # No speedup - test the full duration
        strategy, phase_stats = self._create_strategy(
            mock_credit_manager, schedule, auto_offset=False, speedup=speedup
        )

        # Expected duration in seconds
        expected_duration_sec = year_in_ms / MILLIS_PER_SECOND
        with time_traveler.sleeps_for(expected_duration_sec):
            await strategy._execute_single_phase(phase_stats)
            await strategy.wait_for_tasks()

        assert phase_stats.sent == len(schedule)

    def test_timestamp_arithmetic_precision(
        self,
        mock_credit_manager: MockCreditManager,
    ):
        """Test that timestamp arithmetic maintains precision with large values."""
        # Test with timestamps near float64 precision limits
        very_large = int(2**53 - 1)  # Largest integer exactly representable in float64
        schedule = [
            (very_large - 1000, "conv1"),
            (very_large, "conv2"),
            (very_large + 1000, "conv3"),
        ]

        strategy, _ = self._create_strategy(
            mock_credit_manager, schedule, auto_offset=True, speedup=SPEEDUP_2X_FASTER
        )

        # Verify all timestamps are preserved distinctly
        assert len(strategy._timestamp_groups) == 3
        assert very_large - 1000 in strategy._timestamp_groups
        assert very_large in strategy._timestamp_groups
        assert very_large + 1000 in strategy._timestamp_groups

        # Verify schedule zero is set to first timestamp
        assert strategy._schedule_zero_ms == very_large - 1000

    def test_timestamp_spacing_preservation_with_scaling(
        self,
        mock_credit_manager: MockCreditManager,
    ):
        """Test that relative timestamp spacing is preserved during scaling."""
        # Schedule with specific spacing pattern
        schedule = [
            (1000, "conv1"),  # Base time
            (1001, "conv2"),  # 1ms later
            (1010, "conv3"),  # 9ms later
            (1100, "conv4"),  # 90ms later
        ]

        speedup = 10.0
        strategy, _ = self._create_strategy(
            mock_credit_manager, schedule, auto_offset=True, speedup=speedup
        )

        # Verify all original timestamps are preserved as keys
        expected_timestamps = {1000, 1001, 1010, 1100}
        actual_timestamps = set(strategy._timestamp_groups.keys())
        assert actual_timestamps == expected_timestamps

        # Verify the relative spacing will be scaled correctly during execution
        # The _time_scale factor should be applied to all time calculations
        assert strategy._time_scale == 0.1  # 1/10.0
        assert strategy._schedule_zero_ms == 1000  # First timestamp with auto_offset

        # The actual timing calculations happen during execution, but the
        # timestamp structure is preserved for correct relative timing
