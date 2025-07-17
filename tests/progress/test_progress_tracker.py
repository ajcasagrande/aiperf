# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for ProgressTracker."""

import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase
from aiperf.common.enums._benchmark import BenchmarkSuiteType
from aiperf.common.health_models import ProcessHealth
from aiperf.common.worker_models import WorkerHealthMessage
from aiperf.progress.progress_models import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    CreditPhaseStats,
    PhaseProcessingStats,
    RecordsProcessingStatsMessage,
)
from aiperf.progress.progress_tracker import (
    BenchmarkSuiteProgress,
    CreditPhaseComputedStats,
    ProfileRunProgress,
    ProgressTracker,
)


class TestProgressTracker:
    """Test ProgressTracker functionality."""

    def test_progress_tracker_creation(self):
        """Test creating a ProgressTracker instance."""
        tracker = ProgressTracker()

        assert tracker.suite is None
        assert tracker.current_profile_run is None
        assert tracker.active_phase is None
        assert tracker.logger is not None

    def test_configure_with_suite_and_profile_run(self):
        """Test configuring ProgressTracker with suite and profile run."""
        tracker = ProgressTracker()
        profile_run = ProfileRunProgress(profile_id="test-profile")
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )

        tracker.configure(suite, profile_run)

        assert tracker.suite is not None
        assert tracker.current_profile_run is not None
        assert tracker.current_profile_run.profile_id == "test-profile"

    def test_active_credit_phase_property(self):
        """Test active_credit_phase property."""
        tracker = ProgressTracker()

        # Initially None
        assert tracker.active_phase is None

        # Configure with profile run
        profile_run = ProfileRunProgress(
            profile_id="test-profile",
            active_phase=CreditPhase.PROFILING,
        )
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )
        tracker.configure(suite, profile_run)

        assert tracker.active_phase == CreditPhase.PROFILING

    def test_on_credit_phase_start(self, credit_phase_start_message):
        """Test handling credit phase start message."""
        tracker = ProgressTracker()
        profile_run = ProfileRunProgress(profile_id="test-profile")
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )
        tracker.configure(suite, profile_run)

        tracker.on_credit_phase_start(credit_phase_start_message)

        assert tracker.current_profile_run.active_phase == CreditPhase.PROFILING
        assert CreditPhase.PROFILING in tracker.current_profile_run.phase_infos
        assert tracker.current_profile_run.phase_infos[CreditPhase.PROFILING].is_started

    def test_on_credit_phase_progress(self, credit_phase_progress_message):
        """Test handling credit phase progress message."""
        tracker = ProgressTracker()
        profile_run = ProfileRunProgress(profile_id="test-profile")
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )
        tracker.configure(suite, profile_run)

        tracker.on_credit_phase_progress(credit_phase_progress_message)

        assert CreditPhase.PROFILING in tracker.current_profile_run.phase_infos
        phase = tracker.current_profile_run.phase_infos[CreditPhase.PROFILING]
        assert phase.sent == 50
        assert phase.completed == 25

    def test_on_credit_phase_complete(self, credit_phase_complete_message):
        """Test handling credit phase complete message."""
        tracker = ProgressTracker()
        profile_run = ProfileRunProgress(profile_id="test-profile")
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )
        tracker.configure(suite, profile_run)

        tracker.on_credit_phase_complete(credit_phase_complete_message)

        assert CreditPhase.PROFILING in tracker.current_profile_run.phase_infos
        phase = tracker.current_profile_run.phase_infos[CreditPhase.PROFILING]
        assert phase.is_complete

    def test_on_phase_processing_stats(self, records_processing_stats_message):
        """Test handling phase processing stats message."""
        tracker = ProgressTracker()
        profile_run = ProfileRunProgress(profile_id="test-profile")
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )
        tracker.configure(suite, profile_run)

        tracker.on_phase_processing_stats(records_processing_stats_message)

        assert CreditPhase.PROFILING in tracker.current_profile_run.processing_stats
        stats = tracker.current_profile_run.processing_stats[CreditPhase.PROFILING]
        assert stats.processed == 45
        assert stats.errors == 5

        # Check worker stats
        assert "worker-1" in tracker.current_profile_run.worker_processing_stats
        worker_stats = tracker.current_profile_run.worker_processing_stats["worker-1"]
        assert CreditPhase.PROFILING in worker_stats
        assert worker_stats[CreditPhase.PROFILING].processed == 25
        assert worker_stats[CreditPhase.PROFILING].errors == 3

    def test_on_worker_health(self, worker_health_message):
        """Test handling worker health message."""
        tracker = ProgressTracker()
        profile_run = ProfileRunProgress(profile_id="test-profile")
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )
        tracker.configure(suite, profile_run)

        tracker.on_worker_health(worker_health_message)

        worker_id = "test-worker"
        assert worker_id in tracker.current_profile_run.worker_task_stats
        task_stats = tracker.current_profile_run.worker_task_stats[worker_id]
        assert CreditPhase.PROFILING in task_stats
        assert task_stats[CreditPhase.PROFILING].total == 100
        assert task_stats[CreditPhase.PROFILING].completed == 75
        assert task_stats[CreditPhase.PROFILING].failed == 5

    def test_requests_stats_computation(self):
        """Test computation of request statistics."""
        tracker = ProgressTracker()
        profile_run = ProfileRunProgress(profile_id="test-profile")
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )
        tracker.configure(suite, profile_run)

        # Create a phase with timing data
        phase_stats = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns() - 5 * NANOS_PER_SECOND,  # 5 seconds ago
            total=100,
            sent=100,
            completed=50,
        )

        # Update request stats
        tracker.current_profile_run.update_requests_stats(phase_stats, time.time_ns())

        computed_stats = tracker.current_profile_run.computed_stats[
            CreditPhase.PROFILING
        ]
        assert computed_stats.requests_per_second is not None
        assert computed_stats.requests_per_second > 0
        assert computed_stats.requests_eta is not None
        assert computed_stats.requests_update_ns is not None

    def test_records_stats_computation(self):
        """Test computation of record processing statistics."""
        tracker = ProgressTracker()
        profile_run = ProfileRunProgress(profile_id="test-profile")
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )
        tracker.configure(suite, profile_run)

        # Set up phase with timing data
        phase_stats = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns() - 5 * NANOS_PER_SECOND,  # 5 seconds ago
            total=100,
            sent=100,
            completed=50,
        )
        tracker.current_profile_run.phase_infos[CreditPhase.PROFILING] = phase_stats

        # Create processing stats
        processing_stats = PhaseProcessingStats(processed=30, errors=5)

        # Update records stats
        tracker.current_profile_run.update_records_stats(
            CreditPhase.PROFILING, time.time_ns(), processing_stats
        )

        computed_stats = tracker.current_profile_run.computed_stats[
            CreditPhase.PROFILING
        ]
        assert computed_stats.records_per_second is not None
        assert computed_stats.records_per_second > 0
        assert computed_stats.records_eta is not None
        assert computed_stats.records_update_ns is not None

    def test_profile_run_progress_properties(self):
        """Test ProfileRunProgress properties."""
        profile_run = ProfileRunProgress(profile_id="test-profile")

        # Initially not started or complete
        assert not profile_run.is_started
        assert not profile_run.is_complete

        # Add a started phase
        phase_stats = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns(),
            total=100,
            sent=50,
            completed=25,
        )
        profile_run.phase_infos[CreditPhase.PROFILING] = phase_stats

        assert profile_run.is_started
        assert not profile_run.is_complete

        # Complete the phase
        phase_stats.end_ns = time.time_ns()

        assert profile_run.is_started
        assert profile_run.is_complete

    def test_no_current_profile_run_handling(self):
        """Test that methods handle missing current profile run gracefully."""
        tracker = ProgressTracker()

        # All methods should not raise errors with no current profile run
        phase_stats = CreditPhaseStats(
            type=CreditPhase.PROFILING,
            start_ns=time.time_ns(),
            total=100,
            sent=50,
            completed=25,
        )

        start_message = CreditPhaseStartMessage(
            service_id="test-service",
            phase=phase_stats,
        )
        progress_message = CreditPhaseProgressMessage(
            service_id="test-service",
            phase=phase_stats,
        )
        complete_message = CreditPhaseCompleteMessage(
            service_id="test-service",
            phase=phase_stats,
        )
        processing_message = RecordsProcessingStatsMessage(
            service_id="test-service",
            current_phase=CreditPhase.PROFILING,
            phase_stats=PhaseProcessingStats(processed=10, errors=1),
            worker_stats={},
        )
        health_message = WorkerHealthMessage(
            service_id="test-worker",
            process=ProcessHealth(
                pid=12345,
                memory_usage_mb=512.5,
                cpu_usage_percent=25.0,
            ),
            task_stats={},
        )

        # Should not raise errors
        tracker.on_message(start_message)
        tracker.on_message(progress_message)
        tracker.on_message(complete_message)
        tracker.on_message(processing_message)
        tracker.on_message(health_message)

        # Should still be None
        assert tracker.current_profile_run is None

    def test_credit_phase_computed_stats_model(self):
        """Test CreditPhaseComputedStats model."""
        stats = CreditPhaseComputedStats(
            requests_per_second=10.5,
            requests_eta=30.0,
            requests_update_ns=time.time_ns(),
            records_per_second=8.2,
            records_eta=45.0,
            records_update_ns=time.time_ns(),
        )

        assert stats.requests_per_second == 10.5
        assert stats.requests_eta == 30.0
        assert stats.requests_update_ns is not None
        assert stats.records_per_second == 8.2
        assert stats.records_eta == 45.0
        assert stats.records_update_ns is not None

    def test_benchmark_suite_progress_model(self):
        """Test BenchmarkSuiteProgress model."""
        profile_run = ProfileRunProgress(profile_id="test-profile")
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[profile_run],
            current_profile_run=profile_run,
        )

        assert len(suite.profile_runs) == 1
        assert suite.current_profile_run is not None
        assert suite.current_profile_run.profile_id == "test-profile"
