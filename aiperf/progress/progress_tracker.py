# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging

from pydantic import Field

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.credit_models import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    CreditPhaseStats,
    PhaseProcessingStats,
    RecordsProcessingStatsMessage,
)
from aiperf.common.enums import BenchmarkSuiteType, CreditPhase
from aiperf.common.pydantic_utils import AIPerfBaseModel
from aiperf.common.worker_models import WorkerHealthMessage, WorkerPhaseTaskStats


class CreditPhaseComputedStats(AIPerfBaseModel):
    """Contains additional stats for a credit phase based on computed values."""

    # Computed stats based on the TimingManager
    requests_per_second: float | None = Field(
        default=None, description="The average requests per second"
    )
    requests_eta: float | None = Field(
        default=None, description="The estimated time for all requests to be completed"
    )
    requests_update_ns: int | None = Field(
        default=None, description="The time of the last request update"
    )

    # Computed stats based on the RecordsManager
    records_per_second: float | None = Field(
        default=None, description="The average records processed per second"
    )
    records_eta: float | None = Field(
        default=None, description="The estimated time for all records to be processed"
    )
    records_update_ns: int | None = Field(
        default=None, description="The time of the last record update"
    )


class ProfileRunProgress(AIPerfBaseModel):
    """State of the profile run progress, including the progress of each credit phase, the processing stats, and the worker stats.

    The progress of each credit phase is tracked by from the TimingManager.
    The processing stats and worker processing stats are tracked from the RecordsManager.
    The worker task stats are tracked from the Workers.
    """

    # TODO: implement the profile_id
    profile_id: str | None = Field(default=None, description="The ID of the profile")
    start_ns: int | None = Field(
        default=None, description="The start time of the profile run in nanoseconds"
    )
    end_ns: int | None = Field(
        default=None, description="The end time of the profile run in nanoseconds"
    )
    active_phase: CreditPhase | None = Field(
        default=None, description="The active credit phase"
    )
    phases: dict[CreditPhase, CreditPhaseStats] = Field(
        default_factory=dict,
        description="The credit stats for each credit phase as reported by the TimingManager (sent, completed, etc.)",
    )
    processing_stats: dict[CreditPhase, PhaseProcessingStats] = Field(
        default_factory=dict,
        description="The processing stats for each credit phase as reported by the RecordsManager (processed, errors)",
    )
    worker_processing_stats: dict[str, dict[CreditPhase, PhaseProcessingStats]] = Field(
        default_factory=dict,
        description="The processing stats for each worker for each credit phase as reported by the RecordsManager (processed, errors)",
    )
    worker_task_stats: dict[str, dict[CreditPhase, WorkerPhaseTaskStats]] = Field(
        default_factory=dict,
        description="The task stats for each worker for each credit phase as reported by the Workers (total, completed, failed)",
    )
    computed_stats: dict[CreditPhase, CreditPhaseComputedStats] = Field(
        default_factory=dict,
        description="The computed stats for each credit phase (requests per second, eta, processed per second, processing eta)",
    )

    @property
    def is_started(self) -> bool:
        """Check if the profile run is started."""
        return any(phase.is_started for phase in self.phases.values())

    @property
    def is_complete(self) -> bool:
        """Check if the profile run is complete."""
        if not self.phases:
            return False
        return all(phase.is_complete for phase in self.phases.values())

    def update_requests_stats(self, phase: CreditPhaseStats, request_ns: int):
        """Update the requests stats based on the TimingManager stats."""
        computed = self.computed_stats.setdefault(
            phase.type, CreditPhaseComputedStats()
        )
        computed.requests_update_ns = request_ns

        if phase.start_ns is not None and (diff_ns := request_ns - phase.start_ns) > 0:
            dur_sec = diff_ns / NANOS_PER_SECOND
            computed.requests_per_second = phase.completed / dur_sec
            if pct := phase.progress_percent:
                pct_remaining = 1 - pct
                computed.requests_eta = pct_remaining / (pct / dur_sec)
            else:
                computed.requests_eta = None
        else:
            computed.requests_per_second = None
            computed.requests_eta = None

    def update_records_stats(
        self, phase: CreditPhase, request_ns: int, stats: PhaseProcessingStats
    ):
        """Update the records stats based on the RecordsManager stats."""
        computed = self.computed_stats.setdefault(phase, CreditPhaseComputedStats())
        computed.records_update_ns = request_ns

        # Check if the phase exists in phases before accessing it
        if phase in self.phases and (
            self.phases[phase].start_ns is not None
            and (diff_ns := request_ns - self.phases[phase].start_ns) > 0  # pyright: ignore
        ):
            dur_sec = diff_ns / NANOS_PER_SECOND
            computed.records_per_second = stats.processed / dur_sec
            if self.phases[phase].total is not None:
                computed.records_eta = (
                    self.phases[phase].total - stats.processed  # pyright: ignore
                ) / computed.records_per_second
            else:
                computed.records_eta = None
        else:
            computed.records_per_second = None
            computed.records_eta = None

    def on_credit_phase_progress(self, message: CreditPhaseProgressMessage):
        """Update the progress from a credit phase progress message."""
        self.phases[message.phase.type] = message.phase
        self.update_requests_stats(message.phase, message.request_ns)

    def on_credit_phase_start(self, message: CreditPhaseStartMessage):
        """Update the progress from a credit phase start message."""
        self.active_phase = message.phase.type
        self.phases[message.phase.type] = message.phase
        self.update_requests_stats(message.phase, message.request_ns)

    def on_credit_phase_complete(self, message: CreditPhaseCompleteMessage):
        """Update the progress from a credit phase complete message."""
        self.phases[message.phase.type] = message.phase
        self.update_requests_stats(message.phase, message.request_ns)

    def on_phase_processing_stats(self, message: RecordsProcessingStatsMessage):
        """Update the progress from a phase processing stats message."""
        self.processing_stats[message.current_phase] = message.phase_stats
        for worker_id, worker_stats in message.worker_stats.items():
            if worker_id not in self.worker_processing_stats:
                self.worker_processing_stats[worker_id] = {}
            self.worker_processing_stats[worker_id][message.current_phase] = (
                worker_stats
            )
        self.update_records_stats(
            message.current_phase, message.request_ns, message.phase_stats
        )

    def on_worker_health(self, message: WorkerHealthMessage):
        """Update the progress from a worker health message."""
        worker_id = message.service_id
        for phase, stats in message.task_stats.items():
            if worker_id not in self.worker_task_stats:
                self.worker_task_stats[worker_id] = {}
            self.worker_task_stats[worker_id][phase] = stats


# class SweepRunProgress(AIPerfBaseModel):
#     """State of the sweep run progress. TBD"""

#     sweep_id: str = Field(..., description="The ID of the sweep")


class BenchmarkSuiteProgress(AIPerfBaseModel):
    """State of the benchmark suite progress."""

    type: BenchmarkSuiteType = Field(..., description="The type of benchmark suite")
    start_ns: int | None = Field(
        default=None, description="The start time of the benchmark suite in nanoseconds"
    )
    end_ns: int | None = Field(
        default=None, description="The end time of the benchmark suite in nanoseconds"
    )
    profile_runs: list[ProfileRunProgress] = Field(
        default_factory=list, description="The state of the profile runs in the suite"
    )
    current_profile_run: ProfileRunProgress | None = Field(
        default_factory=ProfileRunProgress,
        description="The current profile run progress",
    )


class ProgressTracker:
    """A progress tracker that tracks the progress of the entire benchmark suite."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.suite: BenchmarkSuiteProgress | None = None

    def configure(
        self, suite: BenchmarkSuiteProgress, current_profile_run: ProfileRunProgress
    ):
        """Configure the progress tracker with a benchmark suite."""
        self.suite = suite
        self.suite.current_profile_run = current_profile_run

    @property
    def current_profile_run(self) -> ProfileRunProgress | None:
        if self.suite is None:
            return None
        return self.suite.current_profile_run

    @property
    def active_credit_phase(self) -> CreditPhase | None:
        if self.current_profile_run is None:
            return None
        return self.current_profile_run.active_phase

    def on_credit_phase_progress(self, message: CreditPhaseProgressMessage):
        """Update the progress from a credit phase progress message."""
        if self.current_profile_run is None:
            return
        self.current_profile_run.on_credit_phase_progress(message)

    def on_credit_phase_start(self, message: CreditPhaseStartMessage):
        """Update the progress from a credit phase start message."""
        if self.current_profile_run is None:
            return
        self.current_profile_run.on_credit_phase_start(message)

    def on_credit_phase_complete(self, message: CreditPhaseCompleteMessage):
        """Update the progress from a credit phase complete message."""
        if self.current_profile_run is None:
            return
        self.current_profile_run.on_credit_phase_complete(message)

    def on_phase_processing_stats(self, message: RecordsProcessingStatsMessage):
        """Update the progress from a phase processing stats message."""
        if self.current_profile_run is None:
            return
        self.current_profile_run.on_phase_processing_stats(message)

    def on_worker_health(self, message: WorkerHealthMessage):
        """Update the progress from a worker health message."""
        if self.current_profile_run is None:
            return
        self.current_profile_run.on_worker_health(message)
