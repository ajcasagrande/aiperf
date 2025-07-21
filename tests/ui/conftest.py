# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Shared fixtures for UI testing.

This file contains fixtures that are automatically discovered by pytest
and made available to test functions in the UI test directory.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from aiperf.common.enums import MessageType
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.models import IOCounters, ProcessHealth
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui import (
    AIPerfRichDashboard,
    DashboardElement,
    LogsDashboardMixin,
    ProfileProgressElement,
    WorkerStatusElement,
)


@pytest.fixture
def mock_console():
    """Mock Rich Console for testing."""
    with patch("aiperf.ui.rich_dashboard.Console") as mock_console:
        console_instance = MagicMock()
        mock_console.return_value = console_instance
        yield console_instance


@pytest.fixture
def mock_live():
    """Mock Rich Live for testing."""
    with patch("aiperf.ui.rich_dashboard.Live") as mock_live:
        live_instance = MagicMock()
        mock_live.return_value = live_instance
        yield live_instance


@pytest.fixture
def mock_progress_tracker():
    """Mock ProgressTracker for testing."""
    progress_tracker = MagicMock(spec=ProgressTracker)
    progress_tracker.current_profile = None
    return progress_tracker


@pytest.fixture
def sample_profile_model():
    """Sample ProfileProgress for testing."""
    profile = ProfileProgress(
        profile_id="test_profile",
        total_expected_requests=1000,
        requests_completed=500,
        requests_processed=450,
        request_errors=10,
        requests_per_second=25.5,
        processed_per_second=22.0,
        elapsed_time=20.0,
        eta=20.0,
        processing_eta=25.0,
        is_complete=False,
        was_cancelled=False,
    )
    return profile


@pytest.fixture
def sample_io_counters():
    """Sample IOCounters for testing."""
    return IOCounters(
        read_count=1000,
        write_count=500,
        read_bytes=1024 * 1024,
        write_bytes=512 * 1024,
        read_chars=2048 * 1024,
        write_chars=1024 * 1024,
    )


@pytest.fixture
def sample_process_health(sample_io_counters):
    """Sample ProcessHealth for testing."""
    return ProcessHealth(
        pid=12345,
        create_time=time.time() - 3600,
        uptime=3600.0,
        cpu_usage=45.5,
        memory_usage=2048.0,
        io_counters=sample_io_counters,
        cpu_times=None,
        num_ctx_switches=None,
        num_threads=4,
    )


@pytest.fixture
def sample_worker_health_message(sample_process_health):
    """Sample WorkerHealthMessage for testing."""
    return WorkerHealthMessage(
        message_type=MessageType.WorkerHealth,
        service_id="worker_001",
        process=sample_process_health,
        total_tasks=1000,
        completed_tasks=950,
        failed_tasks=25,
        warmup_tasks=100,
        warmup_failed_tasks=5,
    )


@pytest.fixture
def multiple_worker_health_messages(sample_io_counters):
    """Multiple WorkerHealthMessage instances for testing."""
    messages = []
    for i in range(3):
        process_health = ProcessHealth(
            pid=12345 + i,
            create_time=time.time() - 3600,
            uptime=3600.0,
            cpu_usage=45.5 + i * 10,
            memory_usage=2048.0 + i * 512,
            io_counters=sample_io_counters,
            cpu_times=None,
            num_ctx_switches=None,
            num_threads=4,
        )

        message = WorkerHealthMessage(
            message_type=MessageType.WorkerHealth,
            service_id=f"worker_{i:03d}",
            process=process_health,
            total_tasks=1000 + i * 100,
            completed_tasks=950 + i * 90,
            failed_tasks=25 + i * 5,
            warmup_tasks=100,
            warmup_failed_tasks=5,
        )
        messages.append(message)

    return messages


@pytest.fixture
def worker_health_dict(multiple_worker_health_messages):
    """Dictionary of worker health messages for testing."""
    return {msg.service_id: msg for msg in multiple_worker_health_messages}


@pytest.fixture
def worker_last_seen_dict(multiple_worker_health_messages):
    """Dictionary of worker last seen times for testing."""
    current_time = time.time()
    return {
        msg.service_id: current_time - i * 10
        for i, msg in enumerate(multiple_worker_health_messages)
    }


@pytest.fixture
def mock_log_queue():
    """Mock log queue for testing."""
    queue = MagicMock()
    queue.empty.return_value = False
    return queue


@pytest.fixture
def mock_get_global_log_queue(mock_log_queue):
    """Mock the get_global_log_queue function."""
    with patch(
        "aiperf.ui.logs_mixin.get_global_log_queue", return_value=mock_log_queue
    ):
        yield mock_log_queue


@pytest.fixture
async def logs_mixin_instance(mock_get_global_log_queue):
    """Instance of LogsDashboardMixin for testing."""

    class TestLogsMixin(LogsDashboardMixin):
        def __init__(self):
            super().__init__()

    logs_mixin = TestLogsMixin()
    await logs_mixin.run_async()
    yield logs_mixin
    await logs_mixin.shutdown()
    await logs_mixin.shutdown_event.wait()


@pytest.fixture
def dashboard_element_instance():
    """Test implementation of DashboardElement."""

    class TestDashboardElement(DashboardElement):
        key = "test_element"
        title = "Test Element"
        border_style = "green"

        def get_content(self):
            return "Test content"

    return TestDashboardElement()


@pytest.fixture
def worker_status_element(worker_health_dict, worker_last_seen_dict):
    """WorkerStatusElement instance for testing."""
    return WorkerStatusElement(worker_health_dict, worker_last_seen_dict)


@pytest.fixture
def profile_progress_element(mock_progress_tracker):
    """ProfileProgressElement instance for testing."""
    return ProfileProgressElement(mock_progress_tracker)


@pytest.fixture
def aiperf_rich_dashboard(mock_progress_tracker, mock_console, mock_live):
    """AIPerfRichDashboard instance for testing."""
    return AIPerfRichDashboard(mock_progress_tracker)


@pytest.fixture
def aiperf_ui(mock_progress_tracker):
    """AIPerfUI instance for testing."""
    return AIPerfUI(mock_progress_tracker)


@pytest.fixture(autouse=True)
def mock_lifecycle_hooks():
    """Mock lifecycle hooks to prevent actual startup/shutdown."""
    with (
        patch("aiperf.ui.aiperf_ui.on_start"),
        patch("aiperf.ui.aiperf_ui.on_stop"),
        patch("aiperf.ui.rich_dashboard.on_start"),
        patch("aiperf.ui.rich_dashboard.on_stop"),
        patch("aiperf.ui.rich_dashboard.aiperf_auto_task"),
        patch("aiperf.ui.logs_mixin.aiperf_auto_task"),
    ):
        yield
