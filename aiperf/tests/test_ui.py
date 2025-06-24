# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from unittest.mock import Mock

import pytest

from aiperf.common.enums import BenchmarkSuiteType
from aiperf.common.models import ProfileProgressMessage, ProfileStatsMessage
from aiperf.common.models.progress import ProfileProgress, ProfileSuiteProgress
from aiperf.common.progress_tracker import ProgressTracker
from aiperf.ui.logging_ui import TextualLogHandler
from aiperf.ui.widgets import DashboardFormatter, StatusClassifier


class TestDashboardFormatter:
    """Test the DashboardFormatter utility class."""

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (None, "--"),
            (0.5, "0.5s"),
            (30.2, "30.2s"),
            (60, "1m"),
            (75.3, "1m 15s"),
            (3600, "1h"),
            (3661, "1h 1m"),
            (86400, "1d"),
            (90061, "1d 1h"),
        ],
    )
    def test_format_duration(self, seconds: float | None, expected: str) -> None:
        """Test duration formatting with various inputs."""
        assert DashboardFormatter.format_duration(seconds) == expected

    @pytest.mark.parametrize(
        "count,total,expected",
        [
            (None, None, "--"),
            (150, 1000, "150 / 1,000"),
            (0, 500, "0 / 500"),
            (1234, 5678, "1,234 / 5,678"),
        ],
    )
    def test_format_count_with_total(
        self, count: int | None, total: int | None, expected: str
    ) -> None:
        """Test count with total formatting."""
        assert DashboardFormatter.format_count_with_total(count, total) == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, "--"),
            (0.0, "0.0%"),
            (15.234, "15.2%"),
            (100.0, "100.0%"),
        ],
    )
    def test_format_percentage(self, value: float | None, expected: str) -> None:
        """Test percentage formatting."""
        assert DashboardFormatter.format_percentage(value) == expected

    @pytest.mark.parametrize(
        "rate,expected",
        [
            (None, "-- req/s"),
            (0, "-- req/s"),
            (25.4, "25.4 req/s"),
            (100.0, "100.0 req/s"),
            (1234.56, "1,234.6 req/s"),
        ],
    )
    def test_format_rate(self, rate: float | None, expected: str) -> None:
        """Test rate formatting."""
        assert DashboardFormatter.format_rate(rate) == expected

    @pytest.mark.parametrize(
        "error_count,total,error_rate,expected",
        [
            (None, 100, 0.1, "--"),
            (2, 152, 0.013, "2 / 152 (1.3%)"),
            (0, 100, 0.0, "0 / 100 (0.0%)"),
        ],
    )
    def test_format_error_stats(
        self,
        error_count: int | None,
        total: int,
        error_rate: float | None,
        expected: str,
    ) -> None:
        """Test error stats formatting."""
        assert (
            DashboardFormatter.format_error_stats(error_count, total, error_rate)
            == expected
        )


class TestStatusClassifier:
    """Test the StatusClassifier utility class."""

    @pytest.mark.parametrize(
        "error_rate,expected",
        [
            (None, "status-idle"),
            (0.0, "error-none"),
            (0.03, "error"),
            (0.1, "error"),
        ],
    )
    def test_get_error_status(self, error_rate: float | None, expected: str) -> None:
        """Test error status classification."""
        assert StatusClassifier.get_error_status(error_rate) == expected

    @pytest.mark.parametrize(
        "is_complete,expected",
        [
            (True, "status-complete"),
            (False, "status-processing"),
        ],
    )
    def test_get_completion_status(self, is_complete: bool, expected: str) -> None:
        """Test completion status classification."""
        assert StatusClassifier.get_completion_status(is_complete) == expected


class TestProgressTracker:
    """Test the ProgressTracker functionality."""

    @pytest.fixture
    def progress_tracker(self) -> ProgressTracker:
        """Create a fresh ProgressTracker instance."""
        return ProgressTracker()

    def test_configure_profile_suite(self, progress_tracker: ProgressTracker) -> None:
        """Test configuring a profile suite."""
        progress_tracker.configure(BenchmarkSuiteType.SINGLE_PROFILE)

        assert progress_tracker.suite is not None
        assert isinstance(progress_tracker.suite, ProfileSuiteProgress)
        assert progress_tracker.current_profile is None

    def test_update_profile_progress(self, progress_tracker: ProgressTracker) -> None:
        """Test updating profile progress."""
        progress_tracker.configure(BenchmarkSuiteType.SINGLE_PROFILE)

        # Create a profile
        profile = ProfileProgress(
            profile_id="test-profile",
            start_time_ns=time.time_ns(),
        )
        progress_tracker.suite.current_profile = profile

        # Update progress
        message = ProfileProgressMessage(
            service_id="test-service",
            start_ns=time.time_ns(),
            total=1000,
            completed=250,
        )

        progress_tracker.update_profile_progress(message)

        assert progress_tracker.current_profile.total_expected_requests == 1000
        assert progress_tracker.current_profile.requests_completed == 250
        assert progress_tracker.current_profile.requests_per_second > 0
        assert progress_tracker.current_profile.elapsed_time >= 0

    def test_update_profile_stats(self, progress_tracker: ProgressTracker) -> None:
        """Test updating profile stats."""
        progress_tracker.configure(BenchmarkSuiteType.SINGLE_PROFILE)

        # Create a profile
        profile = ProfileProgress(
            profile_id="test-profile",
            start_time_ns=time.time_ns(),
            total_expected_requests=100,
        )
        progress_tracker.suite.current_profile = profile

        # Update stats
        message = ProfileStatsMessage(
            service_id="test-service",
            error_count=5,
            completed=95,
            worker_completed={"worker1": 50, "worker2": 45},
            worker_errors={"worker1": 2, "worker2": 3},
        )

        progress_tracker.update_profile_stats(message)

        assert progress_tracker.current_profile.request_errors == 5
        assert progress_tracker.current_profile.successful_requests == 90
        assert progress_tracker.current_profile.requests_processed == 95
        assert progress_tracker.current_profile.worker_completed == {
            "worker1": 50,
            "worker2": 45,
        }
        assert progress_tracker.current_profile.worker_errors == {
            "worker1": 2,
            "worker2": 3,
        }


class TestTextualLogHandler:
    """Test the TextualLogHandler functionality."""

    @pytest.fixture
    def mock_log_widget(self) -> Mock:
        """Create a mock RichLog widget."""
        widget = Mock()
        widget.display = True
        return widget

    @pytest.fixture
    def log_handler(self, mock_log_widget: Mock) -> TextualLogHandler:
        """Create a TextualLogHandler with mock widget."""
        return TextualLogHandler(mock_log_widget)

    def test_emit_info_message(
        self, log_handler: TextualLogHandler, mock_log_widget: Mock
    ) -> None:
        """Test emitting an info log message."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test info message",
            args=(),
            exc_info=None,
        )

        log_handler.emit(record)

        mock_log_widget.write.assert_called_once()
        call_args = mock_log_widget.write.call_args[0][0]
        assert "[bold cyan]" in call_args
        assert "Test info message" in call_args

    def test_emit_error_message(
        self, log_handler: TextualLogHandler, mock_log_widget: Mock
    ) -> None:
        """Test emitting an error log message."""
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test error message",
            args=(),
            exc_info=None,
        )

        log_handler.emit(record)

        mock_log_widget.write.assert_called_once()
        call_args = mock_log_widget.write.call_args[0][0]
        assert "[bold red]" in call_args
        assert "Test error message" in call_args

    def test_emit_with_disabled_display(
        self, log_handler: TextualLogHandler, mock_log_widget: Mock
    ) -> None:
        """Test that nothing is written when display is disabled."""
        mock_log_widget.display = False

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        log_handler.emit(record)

        mock_log_widget.write.assert_not_called()


@pytest.fixture
def sample_profile_progress() -> ProfileProgress:
    """Create a sample ProfileProgress for testing."""
    return ProfileProgress(
        profile_id="test-profile",
        start_time_ns=time.time_ns(),
        total_expected_requests=1000,
        requests_completed=250,
        request_errors=5,
        successful_requests=245,
        requests_processed=250,
        requests_per_second=25.5,
        processed_per_second=25.0,
        elapsed_time=10.0,
        eta=30.0,
        is_complete=False,
        was_cancelled=False,
    )
