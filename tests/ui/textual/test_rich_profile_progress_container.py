# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time

import pytest
from textual.app import App, ComposeResult
from textual.containers import Vertical

from aiperf.common.credit_models import CreditPhaseStats, PhaseProcessingStats
from aiperf.common.enums import CreditPhase
from aiperf.common.worker_models import WorkerPhaseTaskStats
from aiperf.progress.progress_tracker import (
    CreditPhaseComputedStats,
    ProfileRunProgress,
)
from aiperf.ui.textual.rich_profile_progress_container import (
    PhaseOverviewData,
    ProfileProgressData,
    ProfileStatus,
    RichProfileProgressContainer,
)


class MockProgressTracker:
    """Mock progress tracker for testing."""

    def __init__(self):
        self.current_profile_run = None
        self.active_credit_phase = None


class TestRichProfileProgressContainer:
    """Test suite for RichProfileProgressContainer."""

    def test_profile_status_enum(self):
        """Test ProfileStatus enum values."""
        assert ProfileStatus.COMPLETE == "complete"
        assert ProfileStatus.PROCESSING == "processing"
        assert ProfileStatus.IDLE == "idle"

    def test_profile_progress_data_default(self):
        """Test default ProfileProgressData."""
        data = ProfileProgressData(status=ProfileStatus.IDLE)
        assert data.profile_id is None
        assert data.status == ProfileStatus.IDLE
        assert data.active_phase is None
        assert data.requests_completed == 0
        assert data.requests_total is None
        assert data.requests_progress_percent is None
        assert data.processed_count == 0
        assert data.errors_count == 0
        assert data.error_percent == 0.0
        assert data.active_workers == 0
        assert data.total_workers == 0
        assert data.phase_duration is None

    def test_profile_progress_data_with_values(self):
        """Test ProfileProgressData with actual values."""
        data = ProfileProgressData(
            profile_id="test-profile",
            status=ProfileStatus.PROCESSING,
            active_phase=CreditPhase.PROFILING,
            requests_completed=150,
            requests_total=1000,
            requests_progress_percent=15.0,
            processed_count=140,
            errors_count=5,
            error_percent=3.57,
            active_workers=3,
            total_workers=5,
            phase_duration="2m 30s",
        )

        assert data.profile_id == "test-profile"
        assert data.status == ProfileStatus.PROCESSING
        assert data.active_phase == CreditPhase.PROFILING
        assert data.requests_completed == 150
        assert data.requests_total == 1000
        assert data.requests_progress_percent == 15.0
        assert data.processed_count == 140
        assert data.errors_count == 5
        assert data.error_percent == 3.57
        assert data.active_workers == 3
        assert data.total_workers == 5
        assert data.phase_duration == "2m 30s"

    def test_error_color_class(self):
        """Test error color class determination."""
        # No errors
        data = ProfileProgressData(status=ProfileStatus.IDLE, error_percent=0.0)
        assert data.error_color_class == "error-none"

        # Medium errors
        data = ProfileProgressData(status=ProfileStatus.IDLE, error_percent=5.0)
        assert data.error_color_class == "error-medium"

        # High errors
        data = ProfileProgressData(status=ProfileStatus.IDLE, error_percent=15.0)
        assert data.error_color_class == "error-high"

    def test_phase_overview_data_creation(self):
        """Test PhaseOverviewData creation."""
        data = PhaseOverviewData(
            phase=CreditPhase.PROFILING,
            status="Running",
            progress="500/1000 (50.0%)",
            rate="12.5 req/s",
            status_style="phase-running",
        )

        assert data.phase == CreditPhase.PROFILING
        assert data.status == "Running"
        assert data.progress == "500/1000 (50.0%)"
        assert data.rate == "12.5 req/s"
        assert data.status_style == "phase-running"

    def test_container_initialization(self):
        """Test RichProfileProgressContainer initialization."""
        container = RichProfileProgressContainer()

        assert container.progress_tracker is None
        assert container.show_phase_overview is True
        assert container.border_title == "Profile Progress Monitor"

    def test_container_with_progress_tracker(self):
        """Test RichProfileProgressContainer with progress tracker."""
        progress_tracker = MockProgressTracker()
        container = RichProfileProgressContainer(
            progress_tracker=progress_tracker, show_phase_overview=False
        )

        assert container.progress_tracker is progress_tracker
        assert container.show_phase_overview is False

    def test_process_profile_data_idle(self):
        """Test processing profile data - idle case."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()

        # Create empty profile run
        profile_run = ProfileRunProgress(profile_id="test-profile")
        container.progress_tracker = progress_tracker
        container.progress_tracker.current_profile_run = profile_run

        progress_data = container._process_profile_data(profile_run)

        assert progress_data.profile_id == "test-profile"
        assert progress_data.status == ProfileStatus.IDLE
        assert progress_data.active_phase is None
        assert progress_data.requests_completed == 0
        assert progress_data.requests_total is None

    def test_process_profile_data_processing(self):
        """Test processing profile data - processing case."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()

        # Create profile run with active phase
        profile_run = ProfileRunProgress(
            profile_id="test-profile", start_ns=time.time_ns() - 1000000000
        )

        # Add phase stats
        phase_stats = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns() - 1000000000,
            total_expected_requests=1000,
            sent=300,
            completed=250,
        )
        profile_run.phases[CreditPhase.PROFILING] = phase_stats

        # Add computed stats
        computed_stats = CreditPhaseComputedStats(
            requests_per_second=12.5,
            requests_eta=60.0,
            records_per_second=11.8,
            records_eta=65.0,
        )
        profile_run.computed_stats[CreditPhase.PROFILING] = computed_stats

        # Add processing stats
        processing_stats = PhaseProcessingStats(processed=240, errors=10)
        profile_run.processing_stats[CreditPhase.PROFILING] = processing_stats

        container.progress_tracker = progress_tracker
        container.progress_tracker.current_profile_run = profile_run
        container.progress_tracker.active_credit_phase = CreditPhase.PROFILING

        progress_data = container._process_profile_data(profile_run)

        assert progress_data.profile_id == "test-profile"
        assert progress_data.status == ProfileStatus.PROCESSING
        assert progress_data.active_phase == CreditPhase.PROFILING
        assert progress_data.requests_completed == 250
        assert progress_data.requests_total == 1000
        assert progress_data.requests_progress_percent == 25.0
        assert progress_data.requests_per_second == 12.5
        assert progress_data.processed_count == 240
        assert progress_data.errors_count == 10
        assert abs(progress_data.error_percent - 4.17) < 0.01

    def test_process_profile_data_complete(self):
        """Test processing profile data - complete case."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()

        # Create completed profile run
        profile_run = ProfileRunProgress(
            profile_id="test-profile",
            start_ns=time.time_ns() - 2000000000,
            end_ns=time.time_ns() - 1000000000,
        )

        # Add completed phase stats
        phase_stats = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns() - 2000000000,
            end_ns=time.time_ns() - 1000000000,
            total_expected_requests=1000,
            sent=1000,
            completed=1000,
        )
        profile_run.phases[CreditPhase.PROFILING] = phase_stats

        container.progress_tracker = progress_tracker
        container.progress_tracker.current_profile_run = profile_run

        progress_data = container._process_profile_data(profile_run)

        assert progress_data.status == ProfileStatus.COMPLETE
        assert progress_data.requests_completed == 1000
        assert progress_data.requests_total == 1000
        assert progress_data.requests_progress_percent == 100.0

    def test_process_profile_data_with_workers(self):
        """Test processing profile data with worker statistics."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()

        # Create profile run with worker stats
        profile_run = ProfileRunProgress(
            profile_id="test-profile", start_ns=time.time_ns() - 1000000000
        )

        # Add worker task stats
        profile_run.worker_task_stats = {
            "worker-001": {
                CreditPhase.PROFILING: WorkerPhaseTaskStats(
                    total=100, completed=80, failed=2
                )
            },
            "worker-002": {
                CreditPhase.PROFILING: WorkerPhaseTaskStats(
                    total=100, completed=75, failed=1
                )
            },
            "worker-003": {
                CreditPhase.PROFILING: WorkerPhaseTaskStats(
                    total=100, completed=85, failed=0
                )
            },
        }

        container.progress_tracker = progress_tracker
        container.progress_tracker.current_profile_run = profile_run
        container.progress_tracker.active_credit_phase = CreditPhase.PROFILING

        progress_data = container._process_profile_data(profile_run)

        assert progress_data.total_workers == 3
        assert progress_data.active_workers == 3  # All have tasks in progress

    def test_process_phases_data(self):
        """Test processing phases data for overview."""
        container = RichProfileProgressContainer()

        # Create profile run with multiple phases
        profile_run = ProfileRunProgress(profile_id="test-profile")

        # Completed warmup phase
        warmup_stats = CreditPhaseStats(
            type=CreditPhase.WARMUP,
            start_ns=time.time_ns() - 3000000000,
            end_ns=time.time_ns() - 2000000000,
            total_expected_requests=50,
            sent=50,
            completed=50,
        )
        profile_run.phases[CreditPhase.WARMUP] = warmup_stats

        # Running steady state phase
        steady_stats = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns() - 2000000000,
            total_expected_requests=1000,
            sent=300,
            completed=250,
        )
        profile_run.phases[CreditPhase.PROFILING] = steady_stats

        # Add computed stats for steady state
        computed_stats = CreditPhaseComputedStats(requests_per_second=12.5)
        profile_run.computed_stats[CreditPhase.PROFILING] = computed_stats

        phases_data = container._process_phases_data(profile_run)

        # Check that all phases are included
        assert len(phases_data) == len(CreditPhase)

        # Find warmup phase
        warmup_phase = next(p for p in phases_data if p.phase == CreditPhase.WARMUP)
        assert warmup_phase.status == "Complete"
        assert warmup_phase.status_style == "phase-complete"
        assert warmup_phase.progress == "50/50 (100.0%)"

        # Find steady state phase
        steady_phase = next(p for p in phases_data if p.phase == CreditPhase.PROFILING)
        assert steady_phase.status == "Running"
        assert steady_phase.status_style == "phase-running"
        assert steady_phase.progress == "250/1000 (25.0%)"
        assert steady_phase.rate == "12.5 req/s"

        # Find cooldown phase (should be not started)
        cooldown_phase = next(p for p in phases_data if p.phase == CreditPhase.COOLDOWN)
        assert cooldown_phase.status == "Not Started"
        assert cooldown_phase.status_style == "phase-not-started"
        assert cooldown_phase.progress == "--"
        assert cooldown_phase.rate == "--"

    def test_update_progress_no_tracker(self):
        """Test updating progress with no tracker."""
        container = RichProfileProgressContainer()

        # Should not raise any exceptions
        container.update_progress()

    def test_update_progress_no_profile_run(self):
        """Test updating progress with tracker but no profile run."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()

        container.update_progress(progress_tracker)

        assert container.progress_tracker is progress_tracker

    def test_update_progress_with_profile_run(self):
        """Test updating progress with valid profile run."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()

        # Create profile run
        profile_run = ProfileRunProgress(profile_id="test-profile")
        progress_tracker.current_profile_run = profile_run

        container.update_progress(progress_tracker)

        assert container.progress_tracker is progress_tracker

    def test_set_progress_tracker(self):
        """Test setting progress tracker."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()

        container.set_progress_tracker(progress_tracker)

        assert container.progress_tracker is progress_tracker

    def test_get_current_status_no_tracker(self):
        """Test getting current status with no tracker."""
        container = RichProfileProgressContainer()

        status = container.get_current_status()

        assert status == ProfileStatus.IDLE

    def test_get_current_status_idle(self):
        """Test getting current status - idle."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()
        profile_run = ProfileRunProgress(profile_id="test-profile")

        container.progress_tracker = progress_tracker
        container.progress_tracker.current_profile_run = profile_run

        status = container.get_current_status()

        assert status == ProfileStatus.IDLE

    def test_get_current_status_processing(self):
        """Test getting current status - processing."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()
        profile_run = ProfileRunProgress(
            profile_id="test-profile", start_ns=time.time_ns() - 1000000000
        )

        container.progress_tracker = progress_tracker
        container.progress_tracker.current_profile_run = profile_run

        status = container.get_current_status()

        assert status == ProfileStatus.PROCESSING

    def test_get_current_status_complete(self):
        """Test getting current status - complete."""
        container = RichProfileProgressContainer()
        progress_tracker = MockProgressTracker()
        profile_run = ProfileRunProgress(
            profile_id="test-profile",
            start_ns=time.time_ns() - 2000000000,
            end_ns=time.time_ns() - 1000000000,
        )

        # Add completed phase
        phase_stats = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns() - 2000000000,
            end_ns=time.time_ns() - 1000000000,
            total_expected_requests=1000,
            sent=1000,
            completed=1000,
        )
        profile_run.phases[CreditPhase.PROFILING] = phase_stats

        container.progress_tracker = progress_tracker
        container.progress_tracker.current_profile_run = profile_run

        status = container.get_current_status()

        assert status == ProfileStatus.COMPLETE

    def test_toggle_phase_overview(self):
        """Test toggling phase overview."""
        container = RichProfileProgressContainer(show_phase_overview=True)

        # Initial state
        assert container.show_phase_overview is True

        # Toggle off
        container.toggle_phase_overview()
        assert container.show_phase_overview is False

        # Toggle back on
        container.toggle_phase_overview()
        assert container.show_phase_overview is True

    def test_container_without_phase_overview(self):
        """Test container without phase overview."""
        container = RichProfileProgressContainer(show_phase_overview=False)

        assert container.show_phase_overview is False


class TestRichProfileProgressContainerApp(App):
    """Test app for RichProfileProgressContainer."""

    def compose(self) -> ComposeResult:
        """Compose the test app."""
        with Vertical():
            yield RichProfileProgressContainer()


@pytest.mark.asyncio
async def test_container_in_app():
    """Test that the container works in a Textual app."""
    app = TestRichProfileProgressContainerApp()

    # This test just ensures the container can be composed and mounted
    # without errors. In a real scenario, you would use Textual's testing
    # framework to interact with the widgets.
    async with app.run_test():
        # Verify the container exists
        container = app.query_one(RichProfileProgressContainer)
        assert container is not None
        assert container.get_current_status() == ProfileStatus.IDLE
