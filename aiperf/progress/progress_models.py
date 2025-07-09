# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from typing import Literal

from pydantic import Field, SerializeAsAny

from aiperf.common.enums import (
    CaseInsensitiveStrEnum,
    CreditPhase,
    MessageType,
)
from aiperf.common.messages import BaseServiceMessage
from aiperf.common.pydantic_utils import AIPerfBaseModel
from aiperf.common.record_models import ErrorDetailsCount, MetricResult


class ProfileCompletionTrigger(CaseInsensitiveStrEnum):
    """Determines how the profile completion is determined in order to know how to track the progress."""

    REQUEST_COUNT = "request_count"
    """The profile will run for a fixed number of requests."""

    # TIME_BASED = "time_based"
    # """The profile will run for a fixed amount of time."""

    # STABILIZATION_BASED = "stabilization_based"
    # """The profile will run until the metrics stabilize. TDB"""

    # GOODPUT_THRESHOLD = "goodput_threshold"
    # """The profile will run until the goodput threshold is met. TDB"""

    # CUSTOM = "custom"
    # """User defined trigger. TBD"""


class CreditPhaseStats(AIPerfBaseModel):
    """Model for phase credit stats. This is used by the TimingManager to track the progress of the credit phases.
    How many credits were dropped and how many were returned, as well as the progress percentage of the phase."""

    type: CreditPhase = Field(..., description="The type of credit phase")
    start_ns: int | None = Field(
        default=None,
        description="The start time of the credit phase in nanoseconds. If None, the phase has not started.",
    )
    end_ns: int | None = Field(
        default=None,
        description="The end time of the credit phase in nanoseconds. If None, the phase has not ended.",
    )
    total: int | None = Field(
        default=None,
        description="The total number of expected credits. If None, the phase is not request count based.",
    )
    expected_duration_ns: int | None = Field(
        default=None,
        description="The expected duration of the credit phase in nanoseconds. If None, the phase is not time based.",
    )
    sent: int = Field(default=0, description="The number of sent credits")
    completed: int = Field(
        default=0,
        description="The number of completed credits (returned from the workers)",
    )

    @property
    def is_complete(self) -> bool:
        """Check if the phase is complete."""
        return self.end_ns is not None

    @property
    def is_started(self) -> bool:
        """Check if the phase has started."""
        return self.start_ns is not None

    @property
    def in_flight(self) -> int:
        """Calculate the number of in-flight credits (sent but not completed)."""
        return self.sent - self.completed

    @property
    def progress_percent(self) -> float | None:
        """Calculate the progress percentage of the phase."""
        if not self.is_started:
            return None

        if self.is_complete:
            return 100

        if self.total is not None:
            # Credit count based, so progress is the percentage of credits returned
            return (self.completed / self.total) * 100

        if self.expected_duration_ns is not None:
            # Time based, so progress is the percentage of time elapsed compared to the duration
            return (
                (time.time_ns() - self.start_ns) / self.expected_duration_ns  # type: ignore
            ) * 100

        # We don't know the progress
        return None


class PhaseProcessingStats(AIPerfBaseModel):
    """Model for phase processing stats. How many requests were processed and
    how many errors were encountered."""

    processed: int = Field(default=0, description="The number of records processed")
    errors: int = Field(
        default=0, description="The number of record errors encountered"
    )


# class ProfileProgress(AIPerfBaseModel):
#     """State of the profile progress."""

#     profile_id: str = Field(..., description="The ID of the profile")

#     profile_completion_trigger: ProfileCompletionTrigger = Field(
#         default=ProfileCompletionTrigger.REQUEST_COUNT,
#         description="The trigger of profile completion",
#     )

#     start_time_ns: int | None = Field(
#         default=None,
#         description="The start time of the profile run in nanoseconds. "
#         "If it has not been started, this will be None.",
#     )
#     measurement_start_time_ns: int | None = Field(
#         default=None,
#         description="The start time for steady-state measurement in nanoseconds (after ramp-up). "
#         "If None, falls back to start_time_ns.",
#     )
#     end_time_ns: int | None = Field(
#         default=None,
#         description="The end time of the profile run in nanoseconds. "
#         "If it has not been completed, this will be None.",
#     )
#     phase_credits: dict[CreditPhase, CreditPhaseStats] = Field(
#         default_factory=dict,
#         description="The stats for each credit phase how many credits were dropped and how many were returned. "
#         "If None, the phase has not started.",
#     )

#     total_expected_requests: int | None = Field(
#         default=None,
#         description="The total number of inference requests to be made. "
#         "This will be None if the profile completion trigger is not request-based.",
#     )
#     requests_completed: int = Field(
#         default=0,
#         description="The number of inference requests completed during the profile run",
#     )
#     ramp_up_completed: int = Field(
#         default=0,
#         description="The number of inference requests completed during ramp-up phase",
#     )
#     request_errors: int = Field(
#         default=0,
#         description="The total number of request errors encountered during the profile run",
#     )
#     successful_requests: int = Field(
#         default=0,
#         description="The total number of successful requests completed during the profile run",
#     )
#     requests_processed: int = Field(
#         default=0,
#         description="The total number of requests processed by the records manager "
#         "during the profile run. This can be less than the requests_completed if "
#         "the records manager processing requests is slower than the inference requests "
#         "are being made.",
#     )
#     requests_per_second: float | None = Field(
#         default=None,
#         description="The number of requests completed per second during the profile run",
#     )
#     processed_per_second: float | None = Field(
#         default=None,
#         description="The number of requests processed by the records manager per second during the profile run",
#     )
#     worker_completed: dict[str, int] = Field(
#         default_factory=dict,
#         description="Per-worker request completion counts, keyed by worker service_id during the profile run",
#     )
#     worker_errors: dict[str, int] = Field(
#         default_factory=dict,
#         description="Per-worker error counts, keyed by worker service_id during the profile run",
#     )
#     was_cancelled: bool = Field(
#         default=False,
#         description="Whether the profile run was cancelled early",
#     )
#     elapsed_time: float = Field(
#         default=0,
#         description="The elapsed time of the profile run in seconds",
#     )
#     eta: float | None = Field(
#         default=None,
#         description="The estimated time remaining for the profile run in seconds",
#     )
#     processing_eta: float | None = Field(
#         default=None,
#         description="The estimated time remaining for processing the records in seconds",
#     )
#     records: SerializeAsAny[list[MetricResult]] = Field(
#         default_factory=list, description="The records of the profile results"
#     )
#     errors_by_type: list[ErrorDetailsCount] = Field(
#         default_factory=list,
#         description="A list of the unique error details and their counts",
#     )
#     is_complete: bool = Field(
#         default=False,
#         description="Whether the profile run is complete",
#     )
#     credit_phase: CreditPhase = Field(
#         default=CreditPhase.UNKNOWN,
#         description="The type of credit phase (either warmup or profiling)",
#     )

#     @property
#     def steady_state_completed(self) -> int:
#         """Calculate the number of requests completed during steady-state (after ramp-up)."""
#         return max(0, self.requests_completed - self.ramp_up_completed)


class ProfileResultsMessage(BaseServiceMessage):
    """Message for profile results."""

    message_type: Literal[MessageType.PROFILE_RESULTS] = MessageType.PROFILE_RESULTS

    records: SerializeAsAny[list[MetricResult]] = Field(
        ..., description="The records of the profile results"
    )
    total: int = Field(
        ...,
        description="The total number of inference requests expected to be made (if known)",
    )
    completed: int = Field(
        ..., description="The number of inference requests completed"
    )
    start_ns: int = Field(
        ..., description="The start time of the profile run in nanoseconds"
    )
    end_ns: int = Field(
        ..., description="The end time of the profile run in nanoseconds"
    )
    was_cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled early",
    )
    errors_by_type: list[ErrorDetailsCount] = Field(
        default_factory=list,
        description="A list of the unique error details and their counts",
    )


class CreditPhaseProgressMessage(BaseServiceMessage):
    """Message for credit phase stats. Sent by the TimingManager to report the stats of a credit phase."""

    message_type: Literal[MessageType.CREDIT_PHASE_PROGRESS] = (
        MessageType.CREDIT_PHASE_PROGRESS
    )
    request_ns: int = Field(  # type: ignore
        default_factory=time.time_ns,
        description="The timestamp of the request in nanoseconds",
    )
    phase: CreditPhaseStats = Field(
        ...,
        description="The credit phase stats for the phase that has started",
    )


# class ProfileProgressMessage(BaseServiceMessage):
#     """Message for profile progress. Sent by the timing manager to the system controller
#     to report the progress of the profile run."""

#     message_type: Literal[MessageType.PROFILE_PROGRESS] = MessageType.PROFILE_PROGRESS

#     profile_id: str | None = Field(
#         default=None, description="The ID of the current profile"
#     )
#     start_ns: int = Field(
#         ..., description="The start time of the profile run in nanoseconds"
#     )
#     measurement_start_ns: int = Field(
#         ...,
#         description="The start time for steady-state measurement in nanoseconds (after ramp-up)",
#     )
#     end_ns: int | None = Field(
#         default=None, description="The end time of the profile run in nanoseconds"
#     )
#     phase_credits: dict[CreditPhase, CreditPhaseStats] = Field(
#         default_factory=dict,
#         description="The stats for each credit phase how many credits were dropped and how many were returned",
#     )
#     total: int = Field(
#         ..., description="The total number of inference requests to be made (if known)"
#     )
#     completed: int = Field(
#         ..., description="The number of inference requests completed"
#     )
#     ramp_up_completed: int = Field(
#         default=0,
#         description="The number of inference requests completed during ramp-up phase",
#     )
#     credit_phase: CreditPhase = Field(
#         default=CreditPhase.STEADY_STATE,
#         description="The type of credit phase (either warmup or profiling)",
#     )

#     @property
#     def steady_state_completed(self) -> int:
#         """Calculate the number of requests completed during steady-state (after ramp-up)."""
#         return max(0, self.completed - self.ramp_up_completed)


class RecordsProcessingStatsMessage(BaseServiceMessage):
    """Message for processing stats. Sent by the RecordsManager to report the stats of the profile run.
    This contains the stats for a single credit phase only."""

    message_type: Literal[MessageType.PROCESSING_STATS] = MessageType.PROCESSING_STATS

    request_ns: int = Field(  # type: ignore
        default_factory=time.time_ns,
        description="The timestamp of the request in nanoseconds",
    )

    current_phase: CreditPhase = Field(
        ...,
        description="The current credit phase (either warmup, ramp-up, stabilizing, or steady-state)",
    )

    phase_stats: PhaseProcessingStats = Field(
        ...,
        description="The stats for the current credit phase, how many requests were processed "
        "and how many errors were encountered",
    )

    worker_stats: dict[str, PhaseProcessingStats] = Field(
        default_factory=dict,
        description="The stats for each worker how many requests were processed and how many errors were "
        "encountered, keyed by worker service_id",
    )


class CreditPhaseStartMessage(BaseServiceMessage):
    """Message for credit phase start. Sent by the TimingManager to report that a credit phase has started."""

    message_type: Literal[MessageType.CREDIT_PHASE_START] = (
        MessageType.CREDIT_PHASE_START
    )
    request_ns: int = Field(  # type: ignore
        default_factory=time.time_ns,
        description="The timestamp of the request in nanoseconds",
    )

    phase: CreditPhaseStats = Field(
        ...,
        description="The credit phase stats for the phase that has started",
    )


class CreditPhaseCompleteMessage(BaseServiceMessage):
    """Message for credit phase complete. Sent by the TimingManager to report that a credit phase has completed."""

    message_type: Literal[MessageType.CREDIT_PHASE_COMPLETE] = (
        MessageType.CREDIT_PHASE_COMPLETE
    )
    request_ns: int = Field(  # type: ignore
        default_factory=time.time_ns,
        description="The timestamp of the request in nanoseconds",
    )
    phase: CreditPhaseStats = Field(
        ...,
        description="The credit phase stats for the phase that was just completed",
    )
