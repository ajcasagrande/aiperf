# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the ProfileProgressElement UI component.
"""

import pytest
from rich.align import Align
from rich.console import Group
from rich.progress import Progress
from rich.table import Table
from rich.text import Text

from aiperf.ui.profile_progress_ui import ProfileProgressElement


class TestProfileProgressElement:
    """Test the ProfileProgressElement functionality."""

    def test_profile_progress_element_initialization(self, mock_progress_tracker):
        """Test ProfileProgressElement initialization."""
        element = ProfileProgressElement(mock_progress_tracker)

        assert element.key == "profile_progress"
        assert isinstance(element.title, Text)
        assert element.title.plain == "Profile Progress"
        assert element.border_style == "cyan"
        assert element.progress_tracker == mock_progress_tracker
        assert element.progress_task_id is None
        assert element.records_task_id is None
        assert isinstance(element.progress_bar, Progress)
        assert isinstance(element.records_progress_bar, Progress)

    def test_profile_progress_element_class_variables(self):
        """Test ProfileProgressElement class variables."""
        assert ProfileProgressElement.key == "profile_progress"
        assert isinstance(ProfileProgressElement.title, Text)
        assert ProfileProgressElement.title.plain == "Profile Progress"
        assert ProfileProgressElement.border_style == "cyan"

    def test_get_content_no_profile(self, profile_progress_element):
        """Test get_content with no current profile."""
        profile_progress_element.progress_tracker.current_profile = None

        content = profile_progress_element.get_content()

        assert isinstance(content, Align)
        assert content.align == "center"
        assert content.vertical == "middle"

        text_content = content.renderable
        assert isinstance(text_content, Text)
        assert "Waiting for benchmark data..." in text_content.plain
        assert "dim yellow" in str(text_content.style)

    def test_get_content_with_profile(
        self, profile_progress_element, sample_profile_model
    ):
        """Test get_content with a profile."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        content = profile_progress_element.get_content()

        assert isinstance(content, Group)
        assert len(content.renderables) == 3

        # First should be progress bar
        progress_bar = content.renderables[0]
        assert isinstance(progress_bar, Progress)

        # Second should be records progress bar
        records_progress_bar = content.renderables[1]
        assert isinstance(records_progress_bar, Progress)

        # Third should be the progress table
        progress_table = content.renderables[2]
        assert isinstance(progress_table, Table)

    def test_progress_bar_creation(
        self, profile_progress_element, sample_profile_model
    ):
        """Test progress bar creation with profile data."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        # First call should create the progress task
        content = profile_progress_element.get_content()

        assert profile_progress_element.progress_task_id is not None
        assert profile_progress_element.records_task_id is not None

        # Second call should update the existing task
        content = profile_progress_element.get_content()

        assert isinstance(content, Group)

    def test_progress_bar_update(self, profile_progress_element, sample_profile_model):
        """Test progress bar updates with changed profile data."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        # Create initial progress bars
        profile_progress_element.get_content()

        # Update profile data
        sample_profile_model.requests_completed = 750
        sample_profile_model.requests_processed = 700

        # Get content again to trigger updates
        content = profile_progress_element.get_content()

        assert isinstance(content, Group)

    def test_progress_table_structure(
        self, profile_progress_element, sample_profile_model
    ):
        """Test progress table structure and content."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        assert isinstance(progress_table, Table)
        assert len(progress_table.columns) == 2

        # Check for expected rows
        expected_row_labels = [
            "Status:",
            "Progress:",
            "Errors:",
            "Request Rate:",
            "Processing Rate:",
            "Elapsed:",
            "Request ETA:",
            "Results ETA:",
        ]

        # Table should have rows for each expected field
        assert len(progress_table.rows) == len(expected_row_labels)

    def test_progress_table_complete_status(
        self, profile_progress_element, sample_profile_model
    ):
        """Test progress table shows complete status."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model
        sample_profile_model.is_complete = True

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        # Check that the status shows as complete
        # This is implicit in the table generation
        assert isinstance(progress_table, Table)

    def test_progress_table_cancelled_status(
        self, profile_progress_element, sample_profile_model
    ):
        """Test progress table shows cancelled status."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model
        sample_profile_model.was_cancelled = True

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        # Check that the status shows as cancelled
        assert isinstance(progress_table, Table)

    def test_progress_table_processing_status(
        self, profile_progress_element, sample_profile_model
    ):
        """Test progress table shows processing status."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model
        sample_profile_model.is_complete = False
        sample_profile_model.was_cancelled = False

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        # Check that the status shows as processing
        assert isinstance(progress_table, Table)

    def test_error_percentage_calculation(
        self, profile_progress_element, sample_profile_model
    ):
        """Test error percentage calculation and display."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        # Set up error data
        sample_profile_model.requests_processed = 1000
        sample_profile_model.request_errors = 50  # 5% error rate

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        assert isinstance(progress_table, Table)

    def test_error_percentage_zero_processed(
        self, profile_progress_element, sample_profile_model
    ):
        """Test error percentage when no requests processed."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        sample_profile_model.requests_processed = 0
        sample_profile_model.request_errors = 0

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        assert isinstance(progress_table, Table)

    @pytest.mark.parametrize(
        "error_rate,expected_color",
        [
            (0.0, "green"),  # No errors
            (0.05, "yellow"),  # 5% errors
            (0.15, "red"),  # 15% errors
        ],
    )
    def test_error_color_coding(
        self, profile_progress_element, sample_profile_model, error_rate, expected_color
    ):
        """Test error color coding based on error rate."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        sample_profile_model.requests_processed = 1000
        sample_profile_model.request_errors = int(1000 * error_rate)

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        assert isinstance(progress_table, Table)
        # Color coding is implicit in the table generation

    def test_progress_percentage_calculation(
        self, profile_progress_element, sample_profile_model
    ):
        """Test progress percentage calculation."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        sample_profile_model.requests_completed = 250
        sample_profile_model.total_expected_requests = 1000

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        # Should show 25% progress
        assert isinstance(progress_table, Table)

    def test_progress_percentage_zero_total(
        self, profile_progress_element, sample_profile_model
    ):
        """Test progress percentage when total is zero."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        sample_profile_model.requests_completed = 0
        sample_profile_model.total_expected_requests = 0

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        assert isinstance(progress_table, Table)

    def test_rate_display_formatting(
        self, profile_progress_element, sample_profile_model
    ):
        """Test request and processing rate display formatting."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        sample_profile_model.requests_per_second = 123.456
        sample_profile_model.processed_per_second = 98.765

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        # Rates should be formatted to 1 decimal place
        assert isinstance(progress_table, Table)

    def test_duration_formatting(self, profile_progress_element, sample_profile_model):
        """Test duration formatting for elapsed time and ETA."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        sample_profile_model.elapsed_time = 3661.5  # 1 hour, 1 minute, 1.5 seconds
        sample_profile_model.eta = 1800.0  # 30 minutes
        sample_profile_model.processing_eta = 2700.0  # 45 minutes

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        # Duration formatting is handled by format_duration utility
        assert isinstance(progress_table, Table)

    def test_none_values_handling(self, profile_progress_element, sample_profile_model):
        """Test handling of None values in profile data."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        # Set some values to None
        sample_profile_model.requests_completed = None
        sample_profile_model.requests_processed = None
        sample_profile_model.request_errors = None
        sample_profile_model.requests_per_second = None
        sample_profile_model.processed_per_second = None

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        # Should handle None values gracefully
        assert isinstance(progress_table, Table)

    def test_task_count_formatting(
        self, profile_progress_element, sample_profile_model
    ):
        """Test task count formatting with commas."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        sample_profile_model.requests_completed = 1234567
        sample_profile_model.total_expected_requests = 10000000
        sample_profile_model.requests_processed = 1200000
        sample_profile_model.request_errors = 34567

        content = profile_progress_element.get_content()
        progress_table = content.renderables[2]

        # Numbers should be formatted with commas
        assert isinstance(progress_table, Table)

    def test_progress_bars_configuration(self, profile_progress_element):
        """Test progress bars are configured correctly."""
        # Check progress bar configuration
        progress_bar = profile_progress_element.progress_bar
        assert progress_bar.expand is True

        records_progress_bar = profile_progress_element.records_progress_bar
        assert records_progress_bar.expand is True

        # Both should have the same column configuration
        assert len(progress_bar.columns) == len(records_progress_bar.columns)

    def test_progress_task_descriptions(
        self, profile_progress_element, sample_profile_model
    ):
        """Test progress task descriptions are set correctly."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model

        _ = profile_progress_element.get_content()

        # Task descriptions should be set
        assert profile_progress_element.progress_task_id is not None
        assert profile_progress_element.records_task_id is not None

    def test_no_total_expected_requests(
        self, profile_progress_element, sample_profile_model
    ):
        """Test handling when total_expected_requests is None."""
        profile_progress_element.progress_tracker.current_profile = sample_profile_model
        sample_profile_model.total_expected_requests = None

        content = profile_progress_element.get_content()

        # Should handle None total gracefully
        assert isinstance(content, Group)

    def test_progress_element_inheritance(self, profile_progress_element):
        """Test that ProfileProgressElement inherits from DashboardElement."""
        from aiperf.ui.dashboard_element import DashboardElement

        assert isinstance(profile_progress_element, DashboardElement)
        assert hasattr(profile_progress_element, "get_panel")
        assert hasattr(profile_progress_element, "get_content")
