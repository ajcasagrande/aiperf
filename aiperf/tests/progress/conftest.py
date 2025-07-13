# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Test fixtures for progress module tests."""

import time
from unittest.mock import Mock

import pytest

from aiperf.common.credit_models import CreditPhaseStats, PhaseProcessingStats
from aiperf.common.enums import CreditPhase
from aiperf.common.enums.benchmark_suite import BenchmarkSuiteType
from aiperf.common.health_models import CPUTimes, CtxSwitches, IOCounters, ProcessHealth
from aiperf.common.messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    RecordsProcessingStatsMessage,
)
from aiperf.common.worker_models import WorkerHealthMessage, WorkerPhaseTaskStats
from aiperf.progress.progress_models import ProfileResultsMessage
from aiperf.progress.progress_tracker import (
    BenchmarkSuiteProgress,
    ProfileRunProgress,
    ProgressTracker,
)
from aiperf.ui.progress_logger import SimpleProgressLogger


@pytest.fixture
def profile_run_progress():
    """Create a basic ProfileRunProgress instance."""
    return ProfileRunProgress(
        profile_id="test-profile",
        active_phase=CreditPhase.STEADY_STATE,
    )


@pytest.fixture
def benchmark_suite_progress():
    """Create a basic BenchmarkSuiteProgress instance."""
    profile_run = ProfileRunProgress(profile_id="test-profile")
    return BenchmarkSuiteProgress(
        type=BenchmarkSuiteType.SINGLE_PROFILE,
        profile_runs=[profile_run],
        current_profile_run=profile_run,
    )


@pytest.fixture
def progress_tracker():
    """Create a fresh ProgressTracker instance."""
    return ProgressTracker()


@pytest.fixture
def simple_progress_logger(progress_tracker):
    """Create a SimpleProgressLogger instance."""
    return SimpleProgressLogger(progress_tracker)


@pytest.fixture
def credit_phase_stats():
    """Create a CreditPhaseStats instance."""
    return CreditPhaseStats(
        type=CreditPhase.STEADY_STATE,
        start_ns=time.time_ns(),
        total=100,
        sent=50,
        completed=25,
    )


@pytest.fixture
def credit_phase_progress_message(credit_phase_stats):
    """Create a CreditPhaseProgressMessage instance."""
    return CreditPhaseProgressMessage(
        service_id="test-service",
        phase_stats_map={CreditPhase.STEADY_STATE: credit_phase_stats},
    )


@pytest.fixture
def credit_phase_start_message(credit_phase_stats):
    """Create a CreditPhaseStartMessage instance."""
    return CreditPhaseStartMessage(
        service_id="test-service",
        phase_stats=credit_phase_stats,
    )


@pytest.fixture
def credit_phase_complete_message(credit_phase_stats):
    """Create a CreditPhaseCompleteMessage instance."""
    credit_phase_stats.end_ns = time.time_ns()
    return CreditPhaseCompleteMessage(
        service_id="test-service",
        phase_stats=credit_phase_stats,
    )


@pytest.fixture
def phase_processing_stats():
    """Create a PhaseProcessingStats instance."""
    return PhaseProcessingStats(
        processed=45,
        errors=5,
    )


@pytest.fixture
def records_processing_stats_message(phase_processing_stats):
    """Create a RecordsProcessingStatsMessage instance."""
    return RecordsProcessingStatsMessage(
        service_id="test-service",
        current_phase=CreditPhase.STEADY_STATE,
        processing_stats=phase_processing_stats,
        worker_stats={
            "worker-1": PhaseProcessingStats(processed=25, errors=3),
            "worker-2": PhaseProcessingStats(processed=20, errors=2),
        },
    )


@pytest.fixture
def worker_health_message():
    """Create a WorkerHealthMessage instance."""
    return WorkerHealthMessage(
        service_id="test-worker",
        process=ProcessHealth(
            pid=12345,
            create_time=time.time() - 100,  # Process started 100 seconds ago
            uptime=100.0,
            cpu_usage=25.0,
            memory_usage=512.5,
            io_counters=IOCounters(
                read_count=1000,
                write_count=500,
                read_bytes=1024000,
                write_bytes=512000,
                read_chars=2048000,
                write_chars=1024000,
            ),
            cpu_times=CPUTimes(
                user=10.5,
                system=5.2,
                iowait=0.3,
            ),
            num_ctx_switches=CtxSwitches(
                voluntary=1000,
                involuntary=50,
            ),
            num_threads=4,
        ),
        task_stats={
            CreditPhase.STEADY_STATE: WorkerPhaseTaskStats(
                total=100,
                completed=75,
                failed=5,
            ),
        },
    )


@pytest.fixture
def profile_results_message():
    """Create a ProfileResultsMessage instance."""
    return ProfileResultsMessage(
        service_id="test-service",
        records=[],
        total=100,
        completed=100,
        start_ns=time.time_ns() - 1000000000,  # 1 second ago
        end_ns=time.time_ns(),
        was_cancelled=False,
        errors_by_type=[],
    )


@pytest.fixture
def mock_tqdm():
    """Create a mock tqdm instance."""
    mock = Mock()
    mock.n = 0
    mock.total = 100
    mock.refresh = Mock()
    mock.close = Mock()
    return mock
