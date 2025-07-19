# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the AIPerfRichDashboard.
"""

from unittest.mock import patch

import pytest
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

from aiperf.ui import (
    AIPerfRichDashboard,
    HeaderElement,
    ProfileProgressElement,
    WorkerStatusElement,
)


class TestAIPerfRichDashboard:
    """Test the AIPerfRichDashboard functionality."""

    def test_rich_dashboard_initialization(
        self, mock_progress_tracker, mock_console, mock_live
    ):
        """Test AIPerfRichDashboard initialization."""
        dashboard = AIPerfRichDashboard(mock_progress_tracker)

        # Console is mocked in fixtures, so check it's assigned
        assert dashboard.console is not None
        assert dashboard.progress_tracker == mock_progress_tracker
        assert isinstance(dashboard.worker_health, dict)
        assert isinstance(dashboard.worker_last_seen, dict)
        assert len(dashboard.worker_health) == 0
        assert len(dashboard.worker_last_seen) == 0
        assert isinstance(dashboard.elements, dict)
        assert len(dashboard.elements) == 3
        assert isinstance(dashboard.layout, Layout)
        assert dashboard.live is None
        assert dashboard.running is False

    def test_dashboard_elements_initialization(self, aiperf_rich_dashboard):
        """Test dashboard elements are initialized correctly."""
        elements = aiperf_rich_dashboard.elements

        assert HeaderElement.key in elements
        assert ProfileProgressElement.key in elements
        assert WorkerStatusElement.key in elements

        assert isinstance(elements[HeaderElement.key], HeaderElement)
        assert isinstance(elements[ProfileProgressElement.key], ProfileProgressElement)
        assert isinstance(elements[WorkerStatusElement.key], WorkerStatusElement)

    def test_layout_creation(self, aiperf_rich_dashboard):
        """Test layout structure is created correctly."""
        layout = aiperf_rich_dashboard.layout

        assert isinstance(layout, Layout)
        # Check that layout sections can be accessed
        header_section = layout["header"]
        body_section = layout["body"]
        logs_section = layout["logs"]
        left_section = layout["body"]["left"]
        right_section = layout["body"]["right"]

        assert header_section is not None
        assert body_section is not None
        assert logs_section is not None
        assert left_section is not None
        assert right_section is not None

    def test_get_logs_panel(self, aiperf_rich_dashboard):
        """Test logs panel creation."""
        panel = aiperf_rich_dashboard.get_logs_panel()

        assert isinstance(panel, Panel)
        assert panel.title == Text("System Logs", style="bold")
        assert panel.border_style == "yellow"
        assert panel.height == 12
        assert panel.title_align == "left"

    def test_update_display_not_running(self, aiperf_rich_dashboard):
        """Test update_display when not running."""
        aiperf_rich_dashboard.running = False

        # Should not raise an error
        aiperf_rich_dashboard.update_display()

    def test_update_display_running(self, aiperf_rich_dashboard):
        """Test update_display when running."""
        aiperf_rich_dashboard.running = True

        with patch.object(aiperf_rich_dashboard, "layout") as mock_layout:
            aiperf_rich_dashboard.update_display()

            # Should update each element
            assert mock_layout.__getitem__.called

    def test_update_display_with_exception(self, aiperf_rich_dashboard):
        """Test update_display handles exceptions gracefully."""
        aiperf_rich_dashboard.running = True

        with patch.object(aiperf_rich_dashboard, "layout") as mock_layout:
            mock_layout.__getitem__.side_effect = Exception("Layout error")

            # Should not raise an error
            aiperf_rich_dashboard.update_display()

    def test_refresh_element(self, aiperf_rich_dashboard):
        """Test refresh_element method."""
        with patch.object(aiperf_rich_dashboard, "layout") as mock_layout:
            aiperf_rich_dashboard.refresh_element(HeaderElement.key)

            # Should update the specified element
            mock_layout.__getitem__.assert_called_with(HeaderElement.key)

    def test_update_worker_health(
        self, aiperf_rich_dashboard, sample_worker_health_message
    ):
        """Test update_worker_health method."""
        with patch("time.time", return_value=1234567890.0):
            aiperf_rich_dashboard.update_worker_health(sample_worker_health_message)

        service_id = sample_worker_health_message.service_id
        assert service_id in aiperf_rich_dashboard.worker_health
        assert (
            aiperf_rich_dashboard.worker_health[service_id]
            == sample_worker_health_message
        )
        assert service_id in aiperf_rich_dashboard.worker_last_seen
        assert aiperf_rich_dashboard.worker_last_seen[service_id] == 1234567890.0

    def test_update_worker_health_multiple_workers(
        self, aiperf_rich_dashboard, multiple_worker_health_messages
    ):
        """Test update_worker_health with multiple workers."""
        with patch("time.time", return_value=1234567890.0):
            for message in multiple_worker_health_messages:
                aiperf_rich_dashboard.update_worker_health(message)

        assert len(aiperf_rich_dashboard.worker_health) == len(
            multiple_worker_health_messages
        )
        assert len(aiperf_rich_dashboard.worker_last_seen) == len(
            multiple_worker_health_messages
        )

        for message in multiple_worker_health_messages:
            service_id = message.service_id
            assert service_id in aiperf_rich_dashboard.worker_health
            assert aiperf_rich_dashboard.worker_health[service_id] == message

    @pytest.mark.asyncio
    async def test_update_logs_not_running(self, aiperf_rich_dashboard):
        """Test _update_logs when not running."""
        aiperf_rich_dashboard.running = False

        # Should not raise an error
        await aiperf_rich_dashboard._update_logs()

    @pytest.mark.asyncio
    async def test_update_logs_running(self, aiperf_rich_dashboard):
        """Test _update_logs when running."""
        aiperf_rich_dashboard.running = True

        with patch.object(aiperf_rich_dashboard, "layout") as mock_layout:
            await aiperf_rich_dashboard._update_logs()

            # Should update logs section
            mock_layout.__getitem__.assert_called_with("logs")

    @pytest.mark.asyncio
    async def test_start_dashboard(self, aiperf_rich_dashboard, mock_live):
        """Test dashboard startup."""
        await aiperf_rich_dashboard._start()

        assert aiperf_rich_dashboard.running is True
        assert aiperf_rich_dashboard.live is not None
        # Live is created and started
        assert aiperf_rich_dashboard.live.start.called

    @pytest.mark.asyncio
    async def test_stop_dashboard(self, aiperf_rich_dashboard, mock_live):
        """Test dashboard shutdown."""
        aiperf_rich_dashboard.running = True
        aiperf_rich_dashboard.live = mock_live

        await aiperf_rich_dashboard._stop()

        assert aiperf_rich_dashboard.running is False
        mock_live.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_dashboard_with_final_renderable(
        self, aiperf_rich_dashboard, mock_live, mock_console
    ):
        """Test dashboard shutdown with final renderable."""
        aiperf_rich_dashboard.running = True
        aiperf_rich_dashboard.live = mock_live
        aiperf_rich_dashboard.console = mock_console

        # Set up final renderable
        mock_live.renderable = "final_state"

        await aiperf_rich_dashboard._stop()

        assert aiperf_rich_dashboard.running is False
        mock_live.stop.assert_called_once()
        mock_console.print.assert_called_once_with("final_state")

    def test_dashboard_inheritance(self, aiperf_rich_dashboard):
        """Test dashboard inheritance from mixins."""
        from aiperf.common.hooks import AIPerfLifecycleMixin
        from aiperf.ui import LogsDashboardMixin

        assert isinstance(aiperf_rich_dashboard, LogsDashboardMixin)
        assert isinstance(aiperf_rich_dashboard, AIPerfLifecycleMixin)

    def test_layout_sections(self, aiperf_rich_dashboard):
        """Test layout sections are properly configured."""
        layout = aiperf_rich_dashboard.layout

        assert layout["header"].size == 3
        assert layout["body"].ratio == 2
        assert layout["logs"].size == 12

        # Check left/right split in body
        assert layout["body"]["left"].ratio == 1
        assert layout["body"]["right"].ratio == 1

    def test_worker_health_data_structure(self, aiperf_rich_dashboard):
        """Test worker health data structures."""
        assert isinstance(aiperf_rich_dashboard.worker_health, dict)
        assert isinstance(aiperf_rich_dashboard.worker_last_seen, dict)
        assert len(aiperf_rich_dashboard.worker_health) == 0
        assert len(aiperf_rich_dashboard.worker_last_seen) == 0

    def test_elements_have_correct_keys(self, aiperf_rich_dashboard):
        """Test elements have correct keys."""
        elements = aiperf_rich_dashboard.elements

        expected_keys = {
            HeaderElement.key,
            ProfileProgressElement.key,
            WorkerStatusElement.key,
        }

        assert set(elements.keys()) == expected_keys

    def test_layout_update_methods(self, aiperf_rich_dashboard):
        """Test layout update methods are available."""
        layout = aiperf_rich_dashboard.layout

        # Layout should have update method
        assert hasattr(layout, "update")

        # Each section should have update method
        for section_name in ["header", "body", "logs"]:
            assert hasattr(layout[section_name], "update")

    def test_progress_tracker_reference(
        self, aiperf_rich_dashboard, mock_progress_tracker
    ):
        """Test progress tracker reference is maintained."""
        assert aiperf_rich_dashboard.progress_tracker == mock_progress_tracker

        # Profile progress element should have the same reference
        profile_element = aiperf_rich_dashboard.elements[ProfileProgressElement.key]
        assert profile_element.progress_tracker == mock_progress_tracker

    def test_worker_status_element_references(self, aiperf_rich_dashboard):
        """Test worker status element has correct references."""
        worker_element = aiperf_rich_dashboard.elements[WorkerStatusElement.key]

        # Worker status element should reference the same dictionaries
        assert worker_element.worker_health is aiperf_rich_dashboard.worker_health
        assert worker_element.worker_last_seen is aiperf_rich_dashboard.worker_last_seen
