# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the AIPerfUI main class.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aiperf.ui.aiperf_ui import AIPerfUI
from aiperf.ui.profile_progress_ui import ProfileProgressElement
from aiperf.ui.rich_dashboard import AIPerfRichDashboard
from aiperf.ui.worker_status_ui import WorkerStatusElement


class TestAIPerfUI:
    """Test the AIPerfUI main class functionality."""

    def test_aiperf_ui_initialization(self, mock_progress_tracker):
        """Test AIPerfUI initialization."""
        ui = AIPerfUI(mock_progress_tracker)

        assert isinstance(ui.dashboard, AIPerfRichDashboard)
        assert ui.progress_tracker == mock_progress_tracker
        assert ui.dashboard.progress_tracker == mock_progress_tracker

    def test_aiperf_ui_inheritance(self, aiperf_ui):
        """Test AIPerfUI inheritance from lifecycle mixin."""
        from aiperf.common.hooks import AIPerfLifecycleMixin

        assert isinstance(aiperf_ui, AIPerfLifecycleMixin)

    @pytest.mark.asyncio
    async def test_on_start_lifecycle_hook(self, aiperf_ui):
        """Test _on_start lifecycle hook."""
        aiperf_ui.dashboard.run_async = AsyncMock()

        await aiperf_ui._on_start()

        aiperf_ui.dashboard.run_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_stop_lifecycle_hook(self, aiperf_ui):
        """Test _on_stop lifecycle hook."""
        aiperf_ui.dashboard.shutdown = AsyncMock()

        await aiperf_ui._on_stop()

        aiperf_ui.dashboard.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_profile_progress_update_not_running(self, aiperf_ui):
        """Test on_profile_progress_update when dashboard not running."""
        aiperf_ui.dashboard.running = False
        aiperf_ui.progress_tracker.current_profile = MagicMock()
        aiperf_ui.dashboard.refresh_element = MagicMock()

        await aiperf_ui.on_profile_progress_update()

        aiperf_ui.dashboard.refresh_element.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_profile_progress_update_no_profile(self, aiperf_ui):
        """Test on_profile_progress_update when no current profile."""
        aiperf_ui.dashboard.running = True
        aiperf_ui.progress_tracker.current_profile = None
        aiperf_ui.dashboard.refresh_element = MagicMock()

        await aiperf_ui.on_profile_progress_update()

        aiperf_ui.dashboard.refresh_element.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_profile_progress_update_running_with_profile(self, aiperf_ui):
        """Test on_profile_progress_update when dashboard running and has profile."""
        aiperf_ui.dashboard.running = True
        aiperf_ui.progress_tracker.current_profile = MagicMock()
        aiperf_ui.dashboard.refresh_element = MagicMock()

        await aiperf_ui.on_profile_progress_update()

        aiperf_ui.dashboard.refresh_element.assert_called_once_with(
            ProfileProgressElement.key
        )

    @pytest.mark.asyncio
    async def test_on_processing_stats_update_not_running(self, aiperf_ui):
        """Test on_processing_stats_update when dashboard not running."""
        aiperf_ui.dashboard.running = False
        aiperf_ui.progress_tracker.current_profile = MagicMock()
        aiperf_ui.dashboard.refresh_element = MagicMock()

        await aiperf_ui.on_processing_stats_update()

        aiperf_ui.dashboard.refresh_element.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_processing_stats_update_no_profile(self, aiperf_ui):
        """Test on_processing_stats_update when no current profile."""
        aiperf_ui.dashboard.running = True
        aiperf_ui.progress_tracker.current_profile = None
        aiperf_ui.dashboard.refresh_element = MagicMock()

        await aiperf_ui.on_processing_stats_update()

        aiperf_ui.dashboard.refresh_element.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_processing_stats_update_running_with_profile(self, aiperf_ui):
        """Test on_processing_stats_update when dashboard running and has profile."""
        aiperf_ui.dashboard.running = True
        aiperf_ui.progress_tracker.current_profile = MagicMock()
        aiperf_ui.dashboard.refresh_element = MagicMock()

        await aiperf_ui.on_processing_stats_update()

        aiperf_ui.dashboard.refresh_element.assert_called_once_with(
            ProfileProgressElement.key
        )

    @pytest.mark.asyncio
    async def test_on_worker_health_update(
        self, aiperf_ui, sample_worker_health_message
    ):
        """Test on_worker_health_update method."""
        aiperf_ui.dashboard.update_worker_health = MagicMock()
        aiperf_ui.dashboard.running = True
        aiperf_ui.dashboard.refresh_element = MagicMock()

        await aiperf_ui.on_worker_health_update(sample_worker_health_message)

        aiperf_ui.dashboard.update_worker_health.assert_called_once_with(
            sample_worker_health_message
        )
        aiperf_ui.dashboard.refresh_element.assert_called_once_with(
            WorkerStatusElement.key
        )

    @pytest.mark.asyncio
    async def test_on_worker_health_update_not_running(
        self, aiperf_ui, sample_worker_health_message
    ):
        """Test on_worker_health_update when dashboard not running."""
        aiperf_ui.dashboard.update_worker_health = MagicMock()
        aiperf_ui.dashboard.running = False
        aiperf_ui.dashboard.refresh_element = MagicMock()

        await aiperf_ui.on_worker_health_update(sample_worker_health_message)

        aiperf_ui.dashboard.update_worker_health.assert_called_once_with(
            sample_worker_health_message
        )
        aiperf_ui.dashboard.refresh_element.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_worker_health_updates(
        self, aiperf_ui, multiple_worker_health_messages
    ):
        """Test multiple worker health updates."""
        aiperf_ui.dashboard.update_worker_health = MagicMock()
        aiperf_ui.dashboard.running = True
        aiperf_ui.dashboard.refresh_element = MagicMock()

        for message in multiple_worker_health_messages:
            await aiperf_ui.on_worker_health_update(message)

        assert aiperf_ui.dashboard.update_worker_health.call_count == len(
            multiple_worker_health_messages
        )
        assert aiperf_ui.dashboard.refresh_element.call_count == len(
            multiple_worker_health_messages
        )

    @pytest.mark.asyncio
    async def test_progress_updates_with_state_changes(self, aiperf_ui):
        """Test progress updates with changing dashboard state."""
        aiperf_ui.dashboard.refresh_element = MagicMock()
        aiperf_ui.progress_tracker.current_profile = MagicMock()

        # Initially not running
        aiperf_ui.dashboard.running = False
        await aiperf_ui.on_profile_progress_update()
        assert aiperf_ui.dashboard.refresh_element.call_count == 0

        # Start running
        aiperf_ui.dashboard.running = True
        await aiperf_ui.on_profile_progress_update()
        assert aiperf_ui.dashboard.refresh_element.call_count == 1

        # Stop running
        aiperf_ui.dashboard.running = False
        await aiperf_ui.on_profile_progress_update()
        assert aiperf_ui.dashboard.refresh_element.call_count == 1

    @pytest.mark.asyncio
    async def test_progress_updates_with_profile_changes(self, aiperf_ui):
        """Test progress updates with changing profile state."""
        aiperf_ui.dashboard.refresh_element = MagicMock()
        aiperf_ui.dashboard.running = True

        # No profile initially
        aiperf_ui.progress_tracker.current_profile = None
        await aiperf_ui.on_profile_progress_update()
        assert aiperf_ui.dashboard.refresh_element.call_count == 0

        # Profile available
        aiperf_ui.progress_tracker.current_profile = MagicMock()
        await aiperf_ui.on_profile_progress_update()
        assert aiperf_ui.dashboard.refresh_element.call_count == 1

        # Profile removed
        aiperf_ui.progress_tracker.current_profile = None
        await aiperf_ui.on_profile_progress_update()
        assert aiperf_ui.dashboard.refresh_element.call_count == 1

    def test_ui_docstring_and_class_attributes(self, aiperf_ui):
        """Test UI has proper docstring and class attributes."""
        assert AIPerfUI.__doc__ is not None
        assert "Rich-based UI functionality" in AIPerfUI.__doc__

    @pytest.mark.asyncio
    async def test_dashboard_lifecycle_integration(self, aiperf_ui):
        """Test that the UI can start and stop the dashboard."""
        # Mock dashboard methods
        aiperf_ui.dashboard.run_async = AsyncMock()
        aiperf_ui.dashboard.shutdown = AsyncMock()

        # Test start
        await aiperf_ui._on_start()
        aiperf_ui.dashboard.run_async.assert_called_once()

        # Test stop
        await aiperf_ui._on_stop()
        aiperf_ui.dashboard.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_in_methods(self, aiperf_ui):
        """Test that the UI can handle errors in methods."""
        # Mock dashboard methods to raise exceptions
        aiperf_ui.dashboard.refresh_element = MagicMock(
            side_effect=Exception("Dashboard error")
        )
        aiperf_ui.dashboard.running = True
        aiperf_ui.progress_tracker.current_profile = MagicMock()

        # Expect no exceptions to be raised
        await aiperf_ui.on_profile_progress_update()
        await aiperf_ui.on_processing_stats_update()
        assert aiperf_ui.dashboard.refresh_element.call_count == 2

    def test_ui_integration_with_dashboard_components(self, aiperf_ui):
        """Test that the UI can integrate with dashboard components."""
        dashboard = aiperf_ui.dashboard

        # Check that dashboard has required elements
        assert ProfileProgressElement.key in dashboard.elements
        assert WorkerStatusElement.key in dashboard.elements

        # Check that elements are properly configured
        profile_element = dashboard.elements[ProfileProgressElement.key]
        worker_element = dashboard.elements[WorkerStatusElement.key]

        assert profile_element.progress_tracker == aiperf_ui.progress_tracker
        assert worker_element.worker_health is dashboard.worker_health
        assert worker_element.worker_last_seen is dashboard.worker_last_seen
