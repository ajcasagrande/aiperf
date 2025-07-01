# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, SerializeAsAny

from aiperf.common.enums import (
    BenchmarkSuiteCompletionTrigger,
    BenchmarkSuiteType,
    ProfileCompletionTrigger,
    SweepCompletionTrigger,
)
from aiperf.common.record_models import ErrorDetailsCount, MetricResult

################################################################################
# Progress Models
################################################################################


class ProfileProgress(BaseModel):
    """State of the profile progress."""

    profile_id: str = Field(..., description="The ID of the profile")

    profile_completion_trigger: ProfileCompletionTrigger = Field(
        default=ProfileCompletionTrigger.REQUEST_COUNT,
        description="The trigger of profile completion",
    )

    start_time_ns: int | None = Field(
        default=None,
        description="The start time of the profile run in nanoseconds. If it has not been started, this will be None.",
    )
    end_time_ns: int | None = Field(
        default=None,
        description="The end time of the profile run in nanoseconds. If it has not been completed, this will be None.",
    )

    total_expected_requests: int | None = Field(
        default=None,
        description="The total number of inference requests to be made. This will be None if the profile completion trigger is not request-based.",
    )
    requests_completed: int = Field(
        default=0,
        description="The number of inference requests completed during the profile run",
    )
    request_errors: int = Field(
        default=0,
        description="The total number of request errors encountered during the profile run",
    )
    successful_requests: int = Field(
        default=0,
        description="The total number of successful requests completed during the profile run",
    )
    requests_processed: int = Field(
        default=0,
        description="The total number of requests processed by the records manager "
        "during the profile run. This can be less than the requests_completed if "
        "the records manager processing requests is slower than the inference requests "
        "are being made.",
    )
    requests_per_second: float | None = Field(
        default=None,
        description="The number of requests completed per second during the profile run",
    )
    processed_per_second: float | None = Field(
        default=None,
        description="The number of requests processed by the records manager per second during the profile run",
    )
    worker_completed: dict[str, int] = Field(
        default_factory=dict,
        description="Per-worker request completion counts, keyed by worker service_id during the profile run",
    )
    worker_errors: dict[str, int] = Field(
        default_factory=dict,
        description="Per-worker error counts, keyed by worker service_id during the profile run",
    )
    was_cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled early",
    )
    elapsed_time: float = Field(
        default=0,
        description="The elapsed time of the profile run in seconds",
    )
    eta: float | None = Field(
        default=None,
        description="The estimated time remaining for the profile run in seconds",
    )
    processing_eta: float | None = Field(
        default=None,
        description="The estimated time remaining for processing the records in seconds",
    )
    records: SerializeAsAny[list[MetricResult]] = Field(
        default_factory=list, description="The records of the profile results"
    )
    errors_by_type: list[ErrorDetailsCount] = Field(
        default_factory=list,
        description="A list of the unique error details and their counts",
    )
    is_complete: bool = Field(
        default=False,
        description="Whether the profile run is complete",
    )


class SweepProgress(BaseModel):
    """State of the sweep progress."""

    sweep_id: str = Field(..., description="The ID of the current sweep")
    sweep_completion_trigger: SweepCompletionTrigger = Field(
        default=SweepCompletionTrigger.COMPLETED_PROFILES,
        description="The trigger of sweep completion",
    )
    profiles: list[ProfileProgress] = Field(
        default_factory=list, description="The state of the profiles in the sweep"
    )
    current_profile_idx: int | None = Field(
        default=None,
        description="The index of the current profile. If it has not been started, this will be None.",
    )
    completed_profiles: int = Field(
        default=0, description="The number of completed profiles in the sweep"
    )
    start_time_ns: int | None = Field(
        default=None,
        description="The start time of the sweep in nanoseconds. If it has not been started, this will be None.",
    )
    end_time_ns: int | None = Field(
        default=None,
        description="The end time of the sweep in nanoseconds. If it has not been completed, this will be None.",
    )
    was_cancelled: bool = Field(
        default=False,
        description="Whether the sweep was cancelled early",
    )

    @property
    def current_profile(self) -> ProfileProgress | None:
        if self.current_profile_idx is None:
            return None
        return self.profiles[self.current_profile_idx]

    def next_profile(self) -> ProfileProgress | None:
        if self.current_profile_idx is None or self.current_profile_idx >= len(
            self.profiles
        ):
            return None
        self.current_profile_idx += 1
        return self.profiles[self.current_profile_idx - 1]


class BenchmarkSuiteProgress(BaseModel, ABC):
    """State of the suite progress."""

    suite_type: BenchmarkSuiteType = Field(
        default=BenchmarkSuiteType.SINGLE_PROFILE,
        description="The type of suite. Default is SINGLE_PROFILE.",
    )
    suite_completion_trigger: BenchmarkSuiteCompletionTrigger = Field(
        default=BenchmarkSuiteCompletionTrigger.COMPLETED_PROFILES,
        description="The trigger of suite completion",
    )
    start_time_ns: int | None = Field(
        default=None,
        description="The overall start time of the suite in nanoseconds. If it has not been started, this will be None.",
    )
    end_time_ns: int | None = Field(
        default=None,
        description="The overall end time of the suite in nanoseconds. If it has not been completed, this will be None.",
    )
    was_cancelled: bool = Field(
        default=False,
        description="Whether the suite was cancelled early",
    )

    @property
    def current_sweep(self) -> SweepProgress | None:
        if not isinstance(self, SweepSuiteProgress) or self.current_sweep_idx is None:
            return None
        return self.sweeps[self.current_sweep_idx]

    @property
    def current_profile(self) -> ProfileProgress | None:
        if isinstance(self, ProfileSuiteProgress):
            if self.current_profile_idx is None or self.current_profile_idx >= len(
                self.profiles
            ):
                return None
            return self.profiles[self.current_profile_idx]

        elif isinstance(self, SweepSuiteProgress):
            if self.current_sweep is None:
                return None
            return self.current_sweep.current_profile

        return None

    @abstractmethod
    def next_profile(self) -> ProfileProgress | None: ...


class ProfileSuiteProgress(BenchmarkSuiteProgress):
    """State of a profile based suite with 1 or more profile runs."""

    profiles: list[ProfileProgress] = Field(
        default_factory=list, description="The state of the profiles in the suite"
    )
    total_profiles: int = Field(default=0, description="The total number of profiles")
    completed_profiles: int = Field(
        default=0, description="The number of completed profiles"
    )
    current_profile_idx: int | None = Field(
        default=None,
        description="The index of the current profile run. If it has not been started, this will be None.",
    )

    def next_profile(self) -> ProfileProgress | None:
        if self.current_profile_idx is None:
            self.current_profile_idx = 0
        else:
            self.current_profile_idx += 1

        if self.current_profile_idx >= len(self.profiles):
            return None

        return self.profiles[self.current_profile_idx]


class SweepSuiteProgress(BenchmarkSuiteProgress):
    """State of a sweep based suite with 1 or more sweep runs."""

    sweeps: list[SweepProgress] = Field(
        default_factory=list, description="The state of the sweeps in the suite"
    )
    total_sweeps: int = Field(default=0, description="The total number of sweeps")
    completed_sweeps: int = Field(
        default=0, description="The number of completed sweeps"
    )
    current_sweep_idx: int | None = Field(
        default=None,
        description="The index of the current sweep. If it has not been started, this will be None.",
    )

    def next_profile(self) -> ProfileProgress | None:
        """Get the next profile to run.

        Returns:
            The next profile to run, or None if there are no more profiles to run.
        """
        if self.current_sweep is None or self.current_sweep.current_profile_idx is None:
            next_sweep = self.next_sweep()
            if next_sweep is None:
                return None
            return next_sweep.next_profile()

        next_profile = self.current_sweep.next_profile()
        if next_profile is not None:
            return next_profile
        next_sweep = self.next_sweep()
        if next_sweep is None:
            return None
        return next_sweep.next_profile()

        if (
            self.current_sweep.current_profile_idx
            >= len(self.current_sweep.profiles) - 1
        ):
            return self.next_sweep()

        return self.current_sweep.profiles[self.current_sweep.current_profile_idx + 1]

    def next_sweep(self) -> SweepProgress | None:
        """Get the next sweep to run.

        Returns:
            The next sweep to run, or None if there are no more sweeps to run.
        """
        if self.current_sweep_idx is None:
            self.current_sweep_idx = 0
            return self.sweeps[0]
        if self.current_sweep_idx >= len(self.sweeps) - 1:
            return None
        self.current_sweep_idx += 1
        return self.sweeps[self.current_sweep_idx]
