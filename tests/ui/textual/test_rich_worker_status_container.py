# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time

import pytest
from textual.app import App, ComposeResult
from textual.containers import Vertical

from aiperf.common.enums import CreditPhase
from aiperf.common.health_models import CPUTimes, CtxSwitches, IOCounters, ProcessHealth
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.worker_models import WorkerPhaseTaskStats
from aiperf.ui.textual.rich_worker_status_container import (
    RichWorkerStatusContainer,
    WorkerStatus,
    WorkerStatusData,
    WorkerStatusSummary,
)


class TestRichWorkerStatusContainer:
    """Test suite for RichWorkerStatusContainer."""

    def test_worker_status_enum(self):
        """Test WorkerStatus enum values."""
        assert WorkerStatus.HEALTHY == "healthy"
        assert WorkerStatus.HIGH_LOAD == "high_load"
        assert WorkerStatus.ERROR == "error"
        assert WorkerStatus.IDLE == "idle"
        assert WorkerStatus.STALE == "stale"

    def test_worker_status_summary_default(self):
        """Test default WorkerStatusSummary."""
        summary = WorkerStatusSummary()
        assert summary.healthy_count == 0
        assert summary.warning_count == 0
        assert summary.error_count == 0
        assert summary.idle_count == 0
        assert summary.stale_count == 0
        assert summary.total_count == 0

    def test_worker_status_summary_with_counts(self):
        """Test WorkerStatusSummary with actual counts."""
        summary = WorkerStatusSummary(
            healthy_count=5,
            warning_count=2,
            error_count=1,
            idle_count=3,
            stale_count=1,
        )
        assert summary.healthy_count == 5
        assert summary.warning_count == 2
        assert summary.error_count == 1
        assert summary.idle_count == 3
        assert summary.stale_count == 1
        assert summary.total_count == 12

    def test_worker_status_data_creation(self):
        """Test WorkerStatusData creation."""
        data = WorkerStatusData(
            worker_id="test-worker",
            status=WorkerStatus.HEALTHY,
            in_progress_tasks=5,
            completed_tasks=95,
            failed_tasks=2,
            cpu_usage=25.5,
            memory_display="512 MB",
            io_read_display="1.5 MB",
            io_write_display="512 KB",
        )

        assert data.worker_id == "test-worker"
        assert data.status == WorkerStatus.HEALTHY
        assert data.in_progress_tasks == 5
        assert data.completed_tasks == 95
        assert data.failed_tasks == 2
        assert data.cpu_usage == 25.5
        assert data.memory_display == "512 MB"
        assert data.io_read_display == "1.5 MB"
        assert data.io_write_display == "512 KB"

    def test_container_initialization(self):
        """Test RichWorkerStatusContainer initialization."""
        container = RichWorkerStatusContainer()

        assert container.worker_health == {}
        assert container.worker_last_seen == {}
        assert container.stale_threshold == 30.0
        assert container.error_rate_threshold == 0.1
        assert container.high_cpu_threshold == 75.0
        assert container.border_title == "Worker Status Monitor"

    def test_container_with_custom_thresholds(self):
        """Test RichWorkerStatusContainer with custom thresholds."""
        container = RichWorkerStatusContainer(
            stale_threshold=60.0,
            error_rate_threshold=0.2,
            high_cpu_threshold=85.0,
        )

        assert container.stale_threshold == 60.0
        assert container.error_rate_threshold == 0.2
        assert container.high_cpu_threshold == 85.0

    def test_determine_worker_status_healthy(self):
        """Test worker status determination - healthy case."""
        container = RichWorkerStatusContainer()

        health = self._create_sample_health_message("worker-1", cpu_usage=50.0)
        task_stats = WorkerPhaseTaskStats(total=100, completed=95, failed=2)
        current_time = time.time()
        last_seen = current_time - 10  # 10 seconds ago

        status = container._determine_worker_status(
            health, task_stats, last_seen, current_time
        )
        assert status == WorkerStatus.HEALTHY

    def test_determine_worker_status_stale(self):
        """Test worker status determination - stale case."""
        container = RichWorkerStatusContainer()

        health = self._create_sample_health_message("worker-1", cpu_usage=50.0)
        task_stats = WorkerPhaseTaskStats(total=100, completed=95, failed=2)
        current_time = time.time()
        last_seen = current_time - 60  # 60 seconds ago (stale)

        status = container._determine_worker_status(
            health, task_stats, last_seen, current_time
        )
        assert status == WorkerStatus.STALE

    def test_determine_worker_status_error(self):
        """Test worker status determination - error case."""
        container = RichWorkerStatusContainer()

        health = self._create_sample_health_message("worker-1", cpu_usage=50.0)
        task_stats = WorkerPhaseTaskStats(
            total=100, completed=70, failed=20
        )  # 20% error rate
        current_time = time.time()
        last_seen = current_time - 10  # 10 seconds ago

        status = container._determine_worker_status(
            health, task_stats, last_seen, current_time
        )
        assert status == WorkerStatus.ERROR

    def test_determine_worker_status_high_load(self):
        """Test worker status determination - high load case."""
        container = RichWorkerStatusContainer()

        health = self._create_sample_health_message(
            "worker-1", cpu_usage=85.0
        )  # High CPU
        task_stats = WorkerPhaseTaskStats(total=100, completed=95, failed=2)
        current_time = time.time()
        last_seen = current_time - 10  # 10 seconds ago

        status = container._determine_worker_status(
            health, task_stats, last_seen, current_time
        )
        assert status == WorkerStatus.HIGH_LOAD

    def test_determine_worker_status_idle(self):
        """Test worker status determination - idle case."""
        container = RichWorkerStatusContainer()

        health = self._create_sample_health_message("worker-1", cpu_usage=10.0)
        task_stats = WorkerPhaseTaskStats(total=0, completed=0, failed=0)  # No tasks
        current_time = time.time()
        last_seen = current_time - 10  # 10 seconds ago

        status = container._determine_worker_status(
            health, task_stats, last_seen, current_time
        )
        assert status == WorkerStatus.IDLE

    def test_process_worker_data_empty(self):
        """Test processing empty worker data."""
        container = RichWorkerStatusContainer()

        workers_data, summary = container._process_worker_data()

        assert workers_data == []
        assert summary.total_count == 0

    def test_process_worker_data_with_workers(self):
        """Test processing worker data with actual workers."""
        container = RichWorkerStatusContainer()

        # Create test data
        worker_health = {
            "worker-1": self._create_sample_health_message("worker-1", cpu_usage=25.0),
            "worker-2": self._create_sample_health_message("worker-2", cpu_usage=85.0),
        }

        container.worker_health = worker_health
        container.worker_last_seen = {
            "worker-1": time.time() - 10,
            "worker-2": time.time() - 10,
        }

        workers_data, summary = container._process_worker_data()

        assert len(workers_data) == 2
        assert summary.total_count == 2
        assert summary.healthy_count == 1  # worker-1
        assert summary.warning_count == 1  # worker-2 (high CPU)

    def test_update_worker_health(self):
        """Test updating worker health data."""
        container = RichWorkerStatusContainer()

        worker_health = {
            "worker-1": self._create_sample_health_message("worker-1", cpu_usage=25.0),
        }

        container.update_worker_health(worker_health)

        assert "worker-1" in container.worker_health
        assert "worker-1" in container.worker_last_seen

    def test_update_worker_last_seen(self):
        """Test updating worker last seen timestamp."""
        container = RichWorkerStatusContainer()

        # Initially empty
        assert "worker-1" not in container.worker_last_seen

        # Update last seen
        test_time = time.time() - 100
        container.update_worker_last_seen("worker-1", test_time)

        assert container.worker_last_seen["worker-1"] == test_time

    def test_clear_workers(self):
        """Test clearing all workers."""
        container = RichWorkerStatusContainer()

        # Add some data
        worker_health = {
            "worker-1": self._create_sample_health_message("worker-1", cpu_usage=25.0),
        }
        container.update_worker_health(worker_health)

        # Verify data exists
        assert len(container.worker_health) == 1
        assert len(container.worker_last_seen) == 1

        # Clear workers
        container.clear_workers()

        # Verify data is cleared
        assert len(container.worker_health) == 0
        assert len(container.worker_last_seen) == 0

    def test_get_worker_count(self):
        """Test getting worker count."""
        container = RichWorkerStatusContainer()

        # Initially empty
        assert container.get_worker_count() == 0

        # Add workers
        worker_health = {
            "worker-1": self._create_sample_health_message("worker-1", cpu_usage=25.0),
            "worker-2": self._create_sample_health_message("worker-2", cpu_usage=50.0),
        }
        container.update_worker_health(worker_health)

        assert container.get_worker_count() == 2

    def test_get_summary(self):
        """Test getting worker status summary."""
        container = RichWorkerStatusContainer()

        # Initially empty
        summary = container.get_summary()
        assert summary.total_count == 0

        # Add workers
        worker_health = {
            "worker-1": self._create_sample_health_message("worker-1", cpu_usage=25.0),
            "worker-2": self._create_sample_health_message("worker-2", cpu_usage=85.0),
        }
        container.update_worker_health(worker_health)

        summary = container.get_summary()
        assert summary.total_count == 2
        assert summary.healthy_count == 1
        assert summary.warning_count == 1

    def _create_sample_health_message(
        self, worker_id: str, cpu_usage: float = 25.0
    ) -> WorkerHealthMessage:
        """Create a sample WorkerHealthMessage for testing."""
        return WorkerHealthMessage(
            service_id=worker_id,
            process=ProcessHealth(
                pid=12345,
                create_time=time.time() - 3600,
                uptime=3600.0,
                cpu_usage=cpu_usage,
                memory_usage=512.0,
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
                CreditPhase.PROFILING: WorkerPhaseTaskStats(
                    total=100,
                    completed=90,
                    failed=2,
                ),
            },
        )


class TestRichWorkerStatusContainerApp(App):
    """Test app for RichWorkerStatusContainer."""

    def compose(self) -> ComposeResult:
        """Compose the test app."""
        with Vertical():
            yield RichWorkerStatusContainer()


@pytest.mark.asyncio
async def test_container_in_app():
    """Test that the container works in a Textual app."""
    app = TestRichWorkerStatusContainerApp()

    # This test just ensures the container can be composed and mounted
    # without errors. In a real scenario, you would use Textual's testing
    # framework to interact with the widgets.
    async with app.run_test():
        # Verify the container exists
        container = app.query_one(RichWorkerStatusContainer)
        assert container is not None
        assert container.get_worker_count() == 0
