# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic import Field

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.credit_models import (
    CreditPhaseStats,
    PhaseProcessingStats,
)
from aiperf.common.enums import BenchmarkSuiteType, CreditPhase
from aiperf.common.messages import (
    ProfileResultsMessage,
)
from aiperf.common.pydantic_utils import AIPerfBaseModel
from aiperf.common.worker_models import WorkerPhaseTaskStats

logger = AIPerfLogger(__name__)


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


class FullCreditPhaseProgressInfo(
    CreditPhaseStats, PhaseProcessingStats, CreditPhaseComputedStats
):
    """Full state of the credit phase progress, including the progress of the phase, the processing stats, and the worker stats."""

    last_record_update_ns: int | None = Field(
        default=None,
        description="The last time the records stats were updated in nanoseconds",
    )
    worker_processing_stats: dict[str, PhaseProcessingStats] = Field(
        default_factory=dict,
        description="The processing stats for each worker as reported by the RecordsManager (processed, errors)",
    )
    last_request_update_ns: int | None = Field(
        default=None,
        description="The last time the requests stats were updated in nanoseconds",
    )
    worker_request_stats: dict[str, WorkerPhaseTaskStats] = Field(
        default_factory=dict,
        description="The request stats for each worker as reported by the Workers (total, completed, failed)",
    )

    @property
    def elapsed_time(self) -> float | None:
        """Get the elapsed time."""
        if not self.start_ns or not self.last_request_update_ns:
            return None
        return (self.last_request_update_ns - self.start_ns) / NANOS_PER_SECOND


class ProfileRunProgress(AIPerfBaseModel):
    """State of the profile run progress, including the progress of each credit phase, the processing stats, and the worker stats.

    The progress of each credit phase is tracked by from the TimingManager.
    The processing stats and worker processing stats are tracked from the RecordsManager.
    The worker task stats are tracked from the Workers.
    """

    # TODO: implement the profile_id
    profile_id: str | None = Field(default=None, description="The ID of the profile")
    start_ns: int | None = Field(
        default=None,
        description="The start time of the profile run in nanoseconds. If None, the profile run has not started yet.",
    )
    end_ns: int | None = Field(
        default=None,
        description="The end time of the profile run in nanoseconds. If None, the profile run has not ended yet.",
    )
    last_update_ns: int | None = Field(
        default=None,
        description="The last time the progress was updated in nanoseconds",
    )
    active_phase: CreditPhase | None = Field(
        default=None, description="The active credit phase"
    )
    phase_infos: dict[CreditPhase, FullCreditPhaseProgressInfo] = Field(
        default_factory=dict,
        description="The full credit stats for each credit phase as reported by the TimingManager and RecordsManager.",
    )
    profile_results: ProfileResultsMessage | None = Field(
        default=None, description="The profile results"
    )
    was_cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled early",
    )

    @property
    def is_started(self) -> bool:
        """Check if the profile run is started."""
        return any(phase.is_started for phase in self.phase_infos.values())

    @property
    def is_complete(self) -> bool:
        """Check if the profile run is complete."""
        if not self.phase_infos:
            return False
        return all(phase.is_complete for phase in self.phase_infos.values())

    # @property
    # def total_expected_requests(self) -> int | None:
    #     """Get the total number of requests."""
    #     if not self.phase_infos:
    #         return None
    #     return sum(
    #         phase.total_expected_requests
    #         for phase in self.phase_infos.values()
    #         if phase.total_expected_requests is not None
    #     )

    @property
    def requests_completed(self) -> int | None:
        """Get the number of requests completed."""
        if not self.phase_infos:
            return None
        return sum(
            phase.completed
            for phase in self.phase_infos.values()
            if phase.completed is not None
        )

    @property
    def requests_processed(self) -> int | None:
        """Get the number of requests processed."""
        if not self.phase_infos:
            return None
        return sum(
            phase.processed
            for phase in self.phase_infos.values()
            if phase.processed is not None
        )

    @property
    def request_errors(self) -> int | None:
        """Get the number of requests with errors."""
        if not self.phase_infos:
            return None
        return sum(
            phase.errors
            for phase in self.phase_infos.values()
            if phase.errors is not None
        )

    @property
    def requests_per_second(self) -> float | None:
        """Get the requests per second."""
        if not self.active_phase:
            return None
        if not self.phase_infos:
            return None
        return self.phase_infos[self.active_phase].requests_per_second

    @property
    def requests_eta(self) -> float | None:
        """Get the requests eta."""
        if not self.active_phase:
            return None
        if not self.phase_infos:
            return None
        return self.phase_infos[self.active_phase].requests_eta

    @property
    def processed_per_second(self) -> float | None:
        """Get the processed per second."""
        if not self.active_phase:
            return None
        if not self.phase_infos:
            return None
        return self.phase_infos[self.active_phase].records_per_second

    @property
    def processing_eta(self) -> float | None:
        """Get the processed eta."""
        if not self.active_phase:
            return None
        if not self.phase_infos:
            return None
        return self.phase_infos[self.active_phase].records_eta

    @property
    def elapsed_time(self) -> float | None:
        """Get the elapsed time."""
        if not self.start_ns or not self.last_update_ns:
            return None
        return (self.last_update_ns - self.start_ns) / NANOS_PER_SECOND

    @property
    def eta(self) -> float | None:
        """Get the eta."""
        if not self.requests_eta or not self.processing_eta:
            return None
        return max(self.requests_eta, self.processing_eta)


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
